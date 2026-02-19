"""
Model Registry for Version Tracking and Rollback

Tracks model versions, training data, hyperparameters, and performance.
Supports rollback to previous versions if a new model underperforms.

All model artifacts remain as joblib files on disk. The registry stores
metadata (hyperparameters, metrics, data hash) in PostgreSQL so that
the backend API can query model history without touching the filesystem.

Author: nabavkidata.com
"""

import json
import logging
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Archive directory for storing old model versions
ARCHIVE_DIR = MODELS_DIR / "archive"
ARCHIVE_DIR.mkdir(exist_ok=True)


class ModelRegistry:
    """
    Registry for corruption detection model versions.

    Stores metadata in the model_registry PostgreSQL table and keeps
    model artifacts (joblib) on disk. Supports:
    - Registering new model versions with metrics
    - Activating/deactivating models
    - Rollback to previous versions
    - Version comparison and history
    """

    async def register_model(
        self,
        pool,
        model_name: str,
        model_path: str,
        hyperparameters: dict,
        metrics: dict,
        training_data_hash: str,
        training_samples: int = 0,
        training_duration_seconds: float = 0.0,
        notes: str = None,
        activate: bool = True,
    ) -> str:
        """
        Register a new model version.

        Archives the previous active model and optionally activates the new one.

        Args:
            pool: asyncpg connection pool
            model_name: e.g. 'xgboost', 'random_forest'
            model_path: path to the joblib file
            hyperparameters: dict of model hyperparameters
            metrics: {auc_roc, precision, recall, f1, accuracy, ...}
            training_data_hash: hash of the training data
            training_samples: number of samples used for training
            training_duration_seconds: wall-clock training time
            notes: optional human-readable notes
            activate: whether to set this as the active model

        Returns:
            version_id (str)
        """
        version_id = f"{model_name}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

        # Archive current model file if it exists
        model_file = Path(model_path)
        if model_file.exists() and activate:
            archive_path = ARCHIVE_DIR / f"{version_id}_{model_file.name}"
            try:
                shutil.copy2(str(model_file), str(archive_path))
                logger.info(f"Archived model to {archive_path}")
            except Exception as e:
                logger.warning(f"Failed to archive model file: {e}")

        async with pool.acquire() as conn:
            async with conn.transaction():
                # Deactivate previous active model for this model_name
                if activate:
                    await conn.execute("""
                        UPDATE model_registry
                        SET is_active = FALSE
                        WHERE model_name = $1 AND is_active = TRUE
                    """, model_name)

                # Insert new version
                await conn.execute("""
                    INSERT INTO model_registry
                        (version_id, model_name, model_path, hyperparameters,
                         metrics, training_data_hash, training_samples,
                         training_duration_seconds, is_active, notes)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7, $8, $9, $10)
                """,
                    version_id,
                    model_name,
                    str(model_path),
                    json.dumps(hyperparameters),
                    json.dumps(metrics),
                    training_data_hash,
                    training_samples,
                    training_duration_seconds,
                    activate,
                    notes,
                )

        logger.info(
            f"Registered model {version_id} "
            f"(active={activate}, AUC-ROC={metrics.get('auc_roc', 'N/A')})"
        )
        return version_id

    async def get_active_model(self, pool, model_name: str) -> Optional[dict]:
        """
        Get the currently active model version and its metadata.

        Args:
            pool: asyncpg connection pool
            model_name: e.g. 'xgboost', 'random_forest'

        Returns:
            dict with version_id, model_path, hyperparameters, metrics, etc.
            or None if no active model exists.
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT version_id, model_name, model_path, hyperparameters,
                       metrics, training_data_hash, training_samples,
                       training_duration_seconds, is_active, created_at, notes
                FROM model_registry
                WHERE model_name = $1 AND is_active = TRUE
                LIMIT 1
            """, model_name)

        if not row:
            return None

        return self._row_to_dict(row)

    async def rollback(
        self, pool, model_name: str, version_id: str = None
    ) -> dict:
        """
        Rollback to a previous model version.

        If version_id is provided, activates that specific version.
        Otherwise, activates the most recent non-active version.

        Also restores the archived joblib file if it exists.

        Args:
            pool: asyncpg connection pool
            model_name: model name to rollback
            version_id: specific version to restore (optional)

        Returns:
            dict with the newly activated model metadata and rollback details.
        """
        async with pool.acquire() as conn:
            if version_id:
                # Activate specific version
                target = await conn.fetchrow("""
                    SELECT * FROM model_registry
                    WHERE version_id = $1 AND model_name = $2
                """, version_id, model_name)
            else:
                # Get most recent non-active version
                target = await conn.fetchrow("""
                    SELECT * FROM model_registry
                    WHERE model_name = $1 AND is_active = FALSE
                    ORDER BY created_at DESC
                    LIMIT 1
                """, model_name)

            if not target:
                raise ValueError(
                    f"No rollback target found for {model_name}"
                    + (f" version {version_id}" if version_id else "")
                )

            target_version = target['version_id']

            async with conn.transaction():
                # Deactivate current
                await conn.execute("""
                    UPDATE model_registry
                    SET is_active = FALSE
                    WHERE model_name = $1 AND is_active = TRUE
                """, model_name)

                # Activate target
                await conn.execute("""
                    UPDATE model_registry
                    SET is_active = TRUE
                    WHERE version_id = $1
                """, target_version)

        # Attempt to restore archived model file
        restored_file = None
        archive_files = list(ARCHIVE_DIR.glob(f"{target_version}_*"))
        if archive_files:
            source = archive_files[0]
            dest_name = source.name.split('_', 1)[-1] if '_' in source.name else source.name
            dest = MODELS_DIR / dest_name
            try:
                shutil.copy2(str(source), str(dest))
                restored_file = str(dest)
                logger.info(f"Restored model file from {source} to {dest}")
            except Exception as e:
                logger.warning(f"Failed to restore archived model file: {e}")

        logger.info(f"Rolled back {model_name} to version {target_version}")
        return {
            'model_name': model_name,
            'rolled_back_to': target_version,
            'restored_file': restored_file,
            'metrics': json.loads(target['metrics']) if isinstance(target['metrics'], str) else target['metrics'],
            'created_at': target['created_at'].isoformat() if target['created_at'] else None,
        }

    async def get_model_history(
        self, pool, model_name: str, limit: int = 10
    ) -> list:
        """
        Get training history for a model, ordered by creation date descending.

        Args:
            pool: asyncpg connection pool
            model_name: model name to query
            limit: max number of versions to return

        Returns:
            list of dicts with version metadata and metrics
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT version_id, model_name, model_path, hyperparameters,
                       metrics, training_data_hash, training_samples,
                       training_duration_seconds, is_active, created_at, notes
                FROM model_registry
                WHERE model_name = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, model_name, limit)

        return [self._row_to_dict(r) for r in rows]

    async def compare_versions(
        self, pool, model_name: str, v1: str, v2: str
    ) -> dict:
        """
        Compare metrics between two model versions side by side.

        Args:
            pool: asyncpg connection pool
            model_name: model name (for validation)
            v1: first version_id
            v2: second version_id

        Returns:
            {version_a: {...}, version_b: {...}, metric_diffs: {metric: diff}}
        """
        async with pool.acquire() as conn:
            row_a = await conn.fetchrow("""
                SELECT version_id, metrics, hyperparameters, training_samples,
                       training_duration_seconds, created_at
                FROM model_registry
                WHERE version_id = $1 AND model_name = $2
            """, v1, model_name)

            row_b = await conn.fetchrow("""
                SELECT version_id, metrics, hyperparameters, training_samples,
                       training_duration_seconds, created_at
                FROM model_registry
                WHERE version_id = $1 AND model_name = $2
            """, v2, model_name)

        if not row_a:
            raise ValueError(f"Version {v1} not found for model {model_name}")
        if not row_b:
            raise ValueError(f"Version {v2} not found for model {model_name}")

        metrics_a = json.loads(row_a['metrics']) if isinstance(row_a['metrics'], str) else row_a['metrics']
        metrics_b = json.loads(row_b['metrics']) if isinstance(row_b['metrics'], str) else row_b['metrics']

        # Compute diffs for numeric metrics
        metric_diffs = {}
        for key in metrics_a:
            val_a = metrics_a.get(key)
            val_b = metrics_b.get(key)
            if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                metric_diffs[key] = round(val_b - val_a, 4)

        return {
            'version_a': {
                'version_id': v1,
                'metrics': metrics_a,
                'training_samples': row_a['training_samples'],
                'created_at': row_a['created_at'].isoformat() if row_a['created_at'] else None,
            },
            'version_b': {
                'version_id': v2,
                'metrics': metrics_b,
                'training_samples': row_b['training_samples'],
                'created_at': row_b['created_at'].isoformat() if row_b['created_at'] else None,
            },
            'metric_diffs': metric_diffs,
            'better_version': (
                v2 if metric_diffs.get('auc_roc', 0) > 0 else
                v1 if metric_diffs.get('auc_roc', 0) < 0 else
                'tie'
            ),
        }

    async def list_all_models(self, pool) -> list:
        """
        List all registered models with their active version.

        Returns:
            list of {model_name, active_version, total_versions, best_auc_roc}
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    model_name,
                    COUNT(*) AS total_versions,
                    MAX(CASE WHEN is_active THEN version_id END) AS active_version,
                    MAX((metrics->>'auc_roc')::float) AS best_auc_roc,
                    MAX(created_at) AS last_trained
                FROM model_registry
                GROUP BY model_name
                ORDER BY model_name
            """)

        return [
            {
                'model_name': r['model_name'],
                'active_version': r['active_version'],
                'total_versions': r['total_versions'],
                'best_auc_roc': round(float(r['best_auc_roc']), 4) if r['best_auc_roc'] else None,
                'last_trained': r['last_trained'].isoformat() if r['last_trained'] else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert an asyncpg Record to a JSON-safe dict."""
        hp = row['hyperparameters']
        if isinstance(hp, str):
            hp = json.loads(hp)

        metrics = row['metrics']
        if isinstance(metrics, str):
            metrics = json.loads(metrics)

        return {
            'version_id': row['version_id'],
            'model_name': row['model_name'],
            'model_path': row['model_path'],
            'hyperparameters': hp,
            'metrics': metrics,
            'training_data_hash': row['training_data_hash'],
            'training_samples': row['training_samples'],
            'training_duration_seconds': row['training_duration_seconds'],
            'is_active': row['is_active'],
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'notes': row['notes'],
        }

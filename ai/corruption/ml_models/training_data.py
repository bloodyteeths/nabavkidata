"""
Training Data Extraction for ML Corruption Detection

This module handles:
1. Extracting training data from PostgreSQL database
2. Using existing corruption_flags as labels
3. Joining with feature_extractor to get ML features
4. Handling missing values appropriately
5. Train/test split with stratification

The training data uses the 70k+ tenders that have corruption flags as positive examples,
and randomly samples from tenders without flags as negative examples.

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import asyncpg
import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.impute import SimpleImputer
import os
import json

# Import feature extractor
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from ai.corruption.features.feature_extractor import FeatureExtractor, FeatureVector

logger = logging.getLogger(__name__)


@dataclass
class TrainingDataset:
    """
    Container for training dataset with metadata.

    Attributes:
        X_train: Training features
        X_test: Test features
        y_train: Training labels
        y_test: Test labels
        feature_names: List of feature names
        tender_ids_train: Tender IDs for training set
        tender_ids_test: Tender IDs for test set
        class_weights: Computed class weights for imbalanced learning
        metadata: Additional metadata about the dataset
    """
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: List[str]
    tender_ids_train: List[str]
    tender_ids_test: List[str]
    class_weights: Dict[int, float]
    scaler: Optional[StandardScaler]
    imputer: Optional[SimpleImputer]
    metadata: Dict[str, Any]

    def get_pos_weight(self) -> float:
        """Get positive class weight for XGBoost scale_pos_weight"""
        if 0 not in self.class_weights or 1 not in self.class_weights:
            return 1.0
        return self.class_weights[0] / self.class_weights[1]

    def get_class_weight_dict(self) -> Dict[int, float]:
        """Get class weights dict for sklearn class_weight parameter"""
        return self.class_weights


class TrainingDataExtractor:
    """
    Extracts and prepares training data for ML models.

    This class:
    1. Queries tenders with corruption flags (positive examples)
    2. Samples tenders without flags (negative examples)
    3. Extracts features using FeatureExtractor
    4. Handles missing values and scaling
    5. Creates train/test splits with stratification
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        feature_extractor: Optional[FeatureExtractor] = None
    ):
        """
        Initialize training data extractor.

        Args:
            pool: AsyncPG connection pool
            feature_extractor: Optional pre-initialized FeatureExtractor
        """
        self.pool = pool
        self.feature_extractor = feature_extractor or FeatureExtractor(pool)
        logger.info("TrainingDataExtractor initialized")

    async def get_flagged_tenders(
        self,
        min_flags: int = 1,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Get tender IDs that have corruption flags (positive examples).

        Args:
            min_flags: Minimum number of flags to consider as positive
            limit: Optional limit on number of tenders

        Returns:
            List of tender IDs with corruption flags
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT DISTINCT cf.tender_id
                FROM corruption_flags cf
                JOIN tenders t ON cf.tender_id = t.tender_id
                WHERE cf.false_positive = FALSE
                GROUP BY cf.tender_id
                HAVING COUNT(*) >= $1
            """
            if limit:
                query += f" LIMIT {limit}"

            rows = await conn.fetch(query, min_flags)
            tender_ids = [row['tender_id'] for row in rows]

            logger.info(f"Found {len(tender_ids)} tenders with >= {min_flags} corruption flags")
            return tender_ids

    async def get_clean_tenders(
        self,
        limit: int,
        exclude_tender_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get tender IDs without corruption flags (negative examples).

        Args:
            limit: Number of clean tenders to sample
            exclude_tender_ids: Tender IDs to exclude

        Returns:
            List of tender IDs without corruption flags
        """
        exclude = exclude_tender_ids or []

        async with self.pool.acquire() as conn:
            # Get tenders that have no flags or only false positive flags
            # Also require awarded status for better quality data
            query = """
                SELECT t.tender_id
                FROM tenders t
                WHERE t.status = 'awarded'
                  AND t.winner IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM corruption_flags cf
                      WHERE cf.tender_id = t.tender_id
                        AND cf.false_positive = FALSE
                  )
                ORDER BY RANDOM()
                LIMIT $1
            """

            rows = await conn.fetch(query, limit + len(exclude))

            # Filter out excluded IDs
            tender_ids = [
                row['tender_id'] for row in rows
                if row['tender_id'] not in exclude
            ][:limit]

            logger.info(f"Sampled {len(tender_ids)} clean tenders")
            return tender_ids

    async def get_corruption_severity(self, tender_id: str) -> Dict[str, Any]:
        """
        Get corruption severity for a tender based on its flags.

        Args:
            tender_id: Tender ID

        Returns:
            Dict with severity info
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as flag_count,
                    MAX(CASE severity
                        WHEN 'critical' THEN 4
                        WHEN 'high' THEN 3
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 1
                        ELSE 0
                    END) as max_severity,
                    AVG(score) as avg_score,
                    array_agg(DISTINCT flag_type) as flag_types
                FROM corruption_flags
                WHERE tender_id = $1
                  AND false_positive = FALSE
            """, tender_id)

            if row:
                return {
                    'flag_count': int(row['flag_count'] or 0),
                    'max_severity': int(row['max_severity'] or 0),
                    'avg_score': float(row['avg_score'] or 0),
                    'flag_types': row['flag_types'] or []
                }
            return {'flag_count': 0, 'max_severity': 0, 'avg_score': 0, 'flag_types': []}

    async def extract_features_for_tenders(
        self,
        tender_ids: List[str],
        show_progress: bool = True
    ) -> Tuple[np.ndarray, List[str], List[str]]:
        """
        Extract features for a list of tenders.

        Args:
            tender_ids: List of tender IDs
            show_progress: Whether to log progress

        Returns:
            Tuple of (feature_matrix, feature_names, successful_tender_ids)
        """
        features_list = []
        successful_ids = []
        failed_count = 0

        total = len(tender_ids)
        for i, tender_id in enumerate(tender_ids):
            if show_progress and (i + 1) % 100 == 0:
                logger.info(f"Extracting features: {i + 1}/{total} ({(i+1)/total*100:.1f}%)")

            try:
                feature_vector = await self.feature_extractor.extract_features(
                    tender_id, include_metadata=False
                )
                features_list.append(feature_vector.feature_array)
                successful_ids.append(tender_id)
            except Exception as e:
                failed_count += 1
                if failed_count <= 5:
                    logger.warning(f"Failed to extract features for {tender_id}: {e}")

        if failed_count > 5:
            logger.warning(f"... and {failed_count - 5} more failures")

        if not features_list:
            raise ValueError("Failed to extract features for any tender")

        feature_matrix = np.vstack(features_list)
        feature_names = self.feature_extractor.feature_names

        logger.info(
            f"Extracted features for {len(successful_ids)}/{total} tenders "
            f"({len(features_list[0])} features each)"
        )

        return feature_matrix, feature_names, successful_ids

    def _compute_class_weights(
        self,
        y: np.ndarray
    ) -> Dict[int, float]:
        """
        Compute class weights for imbalanced classification.

        Uses balanced class weighting: n_samples / (n_classes * class_count)

        Args:
            y: Label array

        Returns:
            Dict mapping class -> weight
        """
        classes, counts = np.unique(y, return_counts=True)
        n_samples = len(y)
        n_classes = len(classes)

        weights = {}
        for cls, count in zip(classes, counts):
            weights[int(cls)] = n_samples / (n_classes * count)

        logger.info(f"Class distribution: {dict(zip(classes, counts))}")
        logger.info(f"Computed class weights: {weights}")

        return weights

    def _handle_missing_values(
        self,
        X: np.ndarray,
        fit: bool = True,
        imputer: Optional[SimpleImputer] = None
    ) -> Tuple[np.ndarray, SimpleImputer]:
        """
        Handle missing values in feature matrix.

        Args:
            X: Feature matrix
            fit: Whether to fit the imputer
            imputer: Optional pre-fitted imputer

        Returns:
            Tuple of (imputed_matrix, imputer)
        """
        # Replace infinities with NaN
        X = np.where(np.isinf(X), np.nan, X)

        if imputer is None:
            imputer = SimpleImputer(strategy='median')

        if fit:
            X_imputed = imputer.fit_transform(X)
        else:
            X_imputed = imputer.transform(X)

        nan_count = np.isnan(X).sum()
        if nan_count > 0:
            logger.info(f"Imputed {nan_count} missing values")

        return X_imputed, imputer

    def _scale_features(
        self,
        X: np.ndarray,
        fit: bool = True,
        scaler: Optional[StandardScaler] = None
    ) -> Tuple[np.ndarray, StandardScaler]:
        """
        Scale features using StandardScaler.

        Args:
            X: Feature matrix
            fit: Whether to fit the scaler
            scaler: Optional pre-fitted scaler

        Returns:
            Tuple of (scaled_matrix, scaler)
        """
        if scaler is None:
            scaler = StandardScaler()

        if fit:
            X_scaled = scaler.fit_transform(X)
        else:
            X_scaled = scaler.transform(X)

        return X_scaled, scaler

    async def prepare_training_data(
        self,
        positive_limit: Optional[int] = None,
        negative_ratio: float = 1.0,
        test_size: float = 0.2,
        min_flags: int = 1,
        scale_features: bool = True,
        random_state: int = 42
    ) -> TrainingDataset:
        """
        Prepare complete training dataset.

        Args:
            positive_limit: Max number of positive examples (None = all)
            negative_ratio: Ratio of negative to positive examples
            test_size: Fraction of data for testing
            min_flags: Minimum flags for positive classification
            scale_features: Whether to standardize features
            random_state: Random seed for reproducibility

        Returns:
            TrainingDataset with all training data
        """
        logger.info("Preparing training data...")

        # 1. Get positive examples (flagged tenders)
        flagged_ids = await self.get_flagged_tenders(min_flags=min_flags, limit=positive_limit)
        n_positive = len(flagged_ids)

        if n_positive == 0:
            raise ValueError("No flagged tenders found")

        # 2. Get negative examples (clean tenders)
        n_negative = int(n_positive * negative_ratio)
        clean_ids = await self.get_clean_tenders(n_negative, exclude_tender_ids=flagged_ids)

        # 3. Combine and create labels
        all_tender_ids = flagged_ids + clean_ids
        y = np.array([1] * len(flagged_ids) + [0] * len(clean_ids), dtype=np.int32)

        logger.info(f"Dataset: {len(flagged_ids)} positive, {len(clean_ids)} negative")

        # 4. Extract features
        X, feature_names, successful_ids = await self.extract_features_for_tenders(all_tender_ids)

        # Filter labels to match successful extractions
        id_to_label = dict(zip(all_tender_ids, y))
        y = np.array([id_to_label[tid] for tid in successful_ids], dtype=np.int32)

        # 5. Handle missing values
        X, imputer = self._handle_missing_values(X)

        # 6. Train/test split with stratification
        (X_train, X_test, y_train, y_test,
         ids_train, ids_test) = train_test_split(
            X, y, successful_ids,
            test_size=test_size,
            stratify=y,
            random_state=random_state
        )

        # 7. Scale features (fit on train only)
        scaler = None
        if scale_features:
            X_train, scaler = self._scale_features(X_train, fit=True)
            X_test, _ = self._scale_features(X_test, fit=False, scaler=scaler)

        # 8. Compute class weights
        class_weights = self._compute_class_weights(y_train)

        # 9. Build metadata
        metadata = {
            'total_samples': len(successful_ids),
            'train_samples': len(y_train),
            'test_samples': len(y_test),
            'n_features': len(feature_names),
            'positive_ratio': float(y.mean()),
            'min_flags': min_flags,
            'negative_ratio': negative_ratio,
            'scaled': scale_features,
            'random_state': random_state,
            'created_at': datetime.utcnow().isoformat()
        }

        logger.info(
            f"Training data prepared: "
            f"{metadata['train_samples']} train, {metadata['test_samples']} test, "
            f"{metadata['n_features']} features"
        )

        return TrainingDataset(
            X_train=X_train,
            X_test=X_test,
            y_train=y_train,
            y_test=y_test,
            feature_names=feature_names,
            tender_ids_train=ids_train,
            tender_ids_test=ids_test,
            class_weights=class_weights,
            scaler=scaler,
            imputer=imputer,
            metadata=metadata
        )

    async def prepare_multilabel_training_data(
        self,
        flag_types: List[str],
        positive_limit: Optional[int] = None,
        test_size: float = 0.2,
        scale_features: bool = True,
        random_state: int = 42
    ) -> Dict[str, TrainingDataset]:
        """
        Prepare training data for multi-label classification (one model per flag type).

        Args:
            flag_types: List of flag types to train for
            positive_limit: Max positive examples per flag type
            test_size: Fraction for testing
            scale_features: Whether to standardize features
            random_state: Random seed

        Returns:
            Dict mapping flag_type -> TrainingDataset
        """
        datasets = {}

        for flag_type in flag_types:
            logger.info(f"Preparing data for flag type: {flag_type}")

            # Get tenders with this specific flag type
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT DISTINCT tender_id
                    FROM corruption_flags
                    WHERE flag_type = $1
                      AND false_positive = FALSE
                    LIMIT $2
                """, flag_type, positive_limit or 100000)

                flagged_ids = [row['tender_id'] for row in rows]

            if len(flagged_ids) < 10:
                logger.warning(f"Skipping {flag_type}: only {len(flagged_ids)} examples")
                continue

            # Get clean tenders
            clean_ids = await self.get_clean_tenders(
                len(flagged_ids),
                exclude_tender_ids=flagged_ids
            )

            # Combine
            all_ids = flagged_ids + clean_ids
            y = np.array([1] * len(flagged_ids) + [0] * len(clean_ids))

            # Extract features
            X, feature_names, successful_ids = await self.extract_features_for_tenders(
                all_ids, show_progress=False
            )

            id_to_label = dict(zip(all_ids, y))
            y = np.array([id_to_label[tid] for tid in successful_ids])

            # Handle missing values
            X, imputer = self._handle_missing_values(X)

            # Split
            (X_train, X_test, y_train, y_test,
             ids_train, ids_test) = train_test_split(
                X, y, successful_ids,
                test_size=test_size,
                stratify=y,
                random_state=random_state
            )

            # Scale
            scaler = None
            if scale_features:
                X_train, scaler = self._scale_features(X_train, fit=True)
                X_test, _ = self._scale_features(X_test, fit=False, scaler=scaler)

            class_weights = self._compute_class_weights(y_train)

            datasets[flag_type] = TrainingDataset(
                X_train=X_train,
                X_test=X_test,
                y_train=y_train,
                y_test=y_test,
                feature_names=feature_names,
                tender_ids_train=ids_train,
                tender_ids_test=ids_test,
                class_weights=class_weights,
                scaler=scaler,
                imputer=imputer,
                metadata={
                    'flag_type': flag_type,
                    'train_samples': len(y_train),
                    'test_samples': len(y_test),
                    'created_at': datetime.utcnow().isoformat()
                }
            )

            logger.info(f"  {flag_type}: {len(y_train)} train, {len(y_test)} test")

        return datasets


def save_training_dataset(
    dataset: TrainingDataset,
    filepath: str
) -> None:
    """
    Save training dataset to disk.

    Args:
        dataset: TrainingDataset to save
        filepath: Path to save to (will create .npz and _metadata.json)
    """
    import pickle

    # Save numpy arrays
    np.savez_compressed(
        filepath,
        X_train=dataset.X_train,
        X_test=dataset.X_test,
        y_train=dataset.y_train,
        y_test=dataset.y_test
    )

    # Save metadata and preprocessing objects
    meta_path = filepath.replace('.npz', '') + '_metadata.pkl'
    with open(meta_path, 'wb') as f:
        pickle.dump({
            'feature_names': dataset.feature_names,
            'tender_ids_train': dataset.tender_ids_train,
            'tender_ids_test': dataset.tender_ids_test,
            'class_weights': dataset.class_weights,
            'scaler': dataset.scaler,
            'imputer': dataset.imputer,
            'metadata': dataset.metadata
        }, f)

    logger.info(f"Saved training dataset to {filepath}")


def load_training_dataset(filepath: str) -> TrainingDataset:
    """
    Load training dataset from disk.

    Args:
        filepath: Path to load from (expects .npz and _metadata.pkl)

    Returns:
        TrainingDataset
    """
    import pickle

    # Load arrays
    data = np.load(filepath)

    # Load metadata
    meta_path = filepath.replace('.npz', '') + '_metadata.pkl'
    with open(meta_path, 'rb') as f:
        meta = pickle.load(f)

    dataset = TrainingDataset(
        X_train=data['X_train'],
        X_test=data['X_test'],
        y_train=data['y_train'],
        y_test=data['y_test'],
        feature_names=meta['feature_names'],
        tender_ids_train=meta['tender_ids_train'],
        tender_ids_test=meta['tender_ids_test'],
        class_weights=meta['class_weights'],
        scaler=meta['scaler'],
        imputer=meta['imputer'],
        metadata=meta['metadata']
    )

    logger.info(f"Loaded training dataset from {filepath}")
    return dataset


async def create_connection_pool() -> asyncpg.Pool:
    """Create database connection pool using environment variables or defaults."""
    import os

    host = os.getenv('DB_HOST', 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com')
    database = os.getenv('DB_NAME', 'nabavkidata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '')

    pool = await asyncpg.create_pool(
        host=host,
        database=database,
        user=user,
        password=password,
        min_size=2,
        max_size=10
    )

    return pool


# Convenience function for quick data extraction
async def extract_training_data(
    positive_limit: Optional[int] = None,
    negative_ratio: float = 1.0,
    test_size: float = 0.2,
    random_state: int = 42
) -> TrainingDataset:
    """
    Convenience function to extract training data with minimal setup.

    Args:
        positive_limit: Max positive examples
        negative_ratio: Ratio of negative to positive
        test_size: Test set fraction
        random_state: Random seed

    Returns:
        TrainingDataset ready for training
    """
    pool = await create_connection_pool()

    try:
        extractor = TrainingDataExtractor(pool)
        dataset = await extractor.prepare_training_data(
            positive_limit=positive_limit,
            negative_ratio=negative_ratio,
            test_size=test_size,
            random_state=random_state
        )
        return dataset
    finally:
        await pool.close()


if __name__ == "__main__":
    # Example usage
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        print("Extracting training data...")

        # Extract with 10k positive examples for testing
        dataset = await extract_training_data(
            positive_limit=10000,
            negative_ratio=1.0,
            test_size=0.2
        )

        print(f"\nDataset Summary:")
        print(f"  Training samples: {len(dataset.y_train)}")
        print(f"  Test samples: {len(dataset.y_test)}")
        print(f"  Features: {len(dataset.feature_names)}")
        print(f"  Positive ratio (train): {dataset.y_train.mean():.2%}")
        print(f"  Positive ratio (test): {dataset.y_test.mean():.2%}")
        print(f"  Class weights: {dataset.class_weights}")

        # Save for later use
        save_training_dataset(dataset, 'training_data.npz')
        print("\nSaved to training_data.npz")

    asyncio.run(main())

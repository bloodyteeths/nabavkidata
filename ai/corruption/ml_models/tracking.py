"""
MLflow Experiment Tracking for Corruption Detection Models

This module provides MLflow integration for:
- Experiment tracking and versioning
- Hyperparameter logging
- Metric logging (precision, recall, F1, AUC-ROC, AUC-PR)
- Model artifact storage
- Feature importance visualization
- Model registry integration
- Run comparison utilities
- Context managers for clean run handling
- Decorators for easy training function integration
- Cross-validation nested run support

Author: NabavkiData
License: Proprietary
"""

import os
import sys
import json
import logging
import tempfile
import functools
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from datetime import datetime
from dataclasses import dataclass, field
from contextlib import contextmanager

import numpy as np
import mlflow
from mlflow.tracking import MlflowClient
from mlflow.models import infer_signature
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

# Default tracking directory (can be overridden via environment)
DEFAULT_TRACKING_URI = os.environ.get(
    'MLFLOW_TRACKING_URI',
    'file://' + str(Path(__file__).parent.parent.parent.parent / 'mlruns')
)
DEFAULT_EXPERIMENT_NAME = "corruption_detection"


@dataclass
class ModelMetrics:
    """Container for model evaluation metrics."""
    precision: float
    recall: float
    f1: float
    auc_roc: float
    auc_pr: float
    accuracy: float = 0.0
    specificity: float = 0.0
    balanced_accuracy: float = 0.0

    # Threshold-specific metrics
    precision_at_50: float = 0.0  # Precision at 50% recall
    recall_at_80_precision: float = 0.0  # Recall at 80% precision

    # Confusion matrix
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    # Additional metrics
    custom_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for MLflow logging."""
        metrics = {
            'precision': self.precision,
            'recall': self.recall,
            'f1': self.f1,
            'auc_roc': self.auc_roc,
            'auc_pr': self.auc_pr,
            'accuracy': self.accuracy,
            'specificity': self.specificity,
            'balanced_accuracy': self.balanced_accuracy,
            'precision_at_50_recall': self.precision_at_50,
            'recall_at_80_precision': self.recall_at_80_precision,
            'true_positives': self.true_positives,
            'true_negatives': self.true_negatives,
            'false_positives': self.false_positives,
            'false_negatives': self.false_negatives,
        }
        metrics.update(self.custom_metrics)
        return metrics


@dataclass
class TrainingConfig:
    """Configuration for a training run."""
    model_type: str  # 'random_forest', 'xgboost', 'neural_network', 'anomaly', 'ensemble'
    hyperparameters: Dict[str, Any]
    feature_count: int
    training_samples: int
    validation_samples: int
    test_samples: int
    class_weights: Optional[Dict[int, float]] = None
    random_seed: int = 42

    # Training metadata
    data_start_date: Optional[str] = None
    data_end_date: Optional[str] = None
    feature_version: str = "v1"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MLflow logging."""
        params = {
            'model_type': self.model_type,
            'feature_count': self.feature_count,
            'training_samples': self.training_samples,
            'validation_samples': self.validation_samples,
            'test_samples': self.test_samples,
            'random_seed': self.random_seed,
            'feature_version': self.feature_version,
        }

        if self.data_start_date:
            params['data_start_date'] = self.data_start_date
        if self.data_end_date:
            params['data_end_date'] = self.data_end_date

        # Flatten hyperparameters with prefix
        for key, value in self.hyperparameters.items():
            params[f'hp_{key}'] = value

        if self.class_weights:
            params['class_weight_0'] = self.class_weights.get(0, 1.0)
            params['class_weight_1'] = self.class_weights.get(1, 1.0)

        return params


class CorruptionMLflowTracker:
    """
    MLflow experiment tracking for corruption detection models.

    Provides a consistent interface for:
    - Starting and managing experiments
    - Logging parameters, metrics, and artifacts
    - Saving and loading trained models
    - Comparing runs and selecting best models
    """

    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        experiment_name: str = DEFAULT_EXPERIMENT_NAME
    ):
        """
        Initialize the tracker.

        Args:
            tracking_uri: MLflow tracking URI. Defaults to local file store.
            experiment_name: Name of the experiment to use.
        """
        self.tracking_uri = tracking_uri or DEFAULT_TRACKING_URI
        self.experiment_name = experiment_name

        # Setup MLflow
        mlflow.set_tracking_uri(self.tracking_uri)

        # Get or create experiment
        experiment = mlflow.get_experiment_by_name(experiment_name)
        if experiment is None:
            self.experiment_id = mlflow.create_experiment(
                experiment_name,
                tags={
                    "project": "nabavkidata",
                    "domain": "corruption_detection",
                    "version": "2.0"
                }
            )
            logger.info(f"Created new experiment: {experiment_name}")
        else:
            self.experiment_id = experiment.experiment_id

        mlflow.set_experiment(experiment_name)

        self.client = MlflowClient(tracking_uri=self.tracking_uri)
        self.current_run_id = None

        logger.info(f"MLflow tracker initialized. URI: {self.tracking_uri}, Experiment: {experiment_name}")

    def start_run(
        self,
        run_name: str,
        config: TrainingConfig,
        tags: Optional[Dict[str, str]] = None,
        nested: bool = False
    ) -> str:
        """
        Start a new MLflow run.

        Args:
            run_name: Human-readable name for the run
            config: Training configuration with hyperparameters
            tags: Additional tags to attach to the run
            nested: Whether this is a nested run (e.g., CV fold)

        Returns:
            Run ID
        """
        run_tags = {
            "model_type": config.model_type,
            "feature_version": config.feature_version,
            "training_date": datetime.utcnow().isoformat(),
        }
        if tags:
            run_tags.update(tags)

        run = mlflow.start_run(
            run_name=run_name,
            experiment_id=self.experiment_id,
            tags=run_tags,
            nested=nested
        )

        self.current_run_id = run.info.run_id

        # Log parameters
        params = config.to_dict()
        mlflow.log_params(params)

        logger.info(f"Started run: {run_name} (ID: {self.current_run_id})")
        return self.current_run_id

    def end_run(self, status: str = "FINISHED"):
        """
        End the current run.

        Args:
            status: Run status (FINISHED, FAILED, KILLED)
        """
        if self.current_run_id:
            mlflow.end_run(status=status)
            logger.info(f"Ended run: {self.current_run_id} with status: {status}")
            self.current_run_id = None

    def log_metrics(
        self,
        metrics: Union[ModelMetrics, Dict[str, float]],
        step: Optional[int] = None,
        prefix: str = ""
    ):
        """
        Log metrics to the current run.

        Args:
            metrics: ModelMetrics object or dictionary of metrics
            step: Optional step number for time-series metrics
            prefix: Optional prefix for metric names (e.g., 'val_', 'test_')
        """
        if isinstance(metrics, ModelMetrics):
            metrics_dict = metrics.to_dict()
        else:
            metrics_dict = metrics

        # Add prefix if specified
        if prefix:
            metrics_dict = {f"{prefix}{k}": v for k, v in metrics_dict.items()}

        mlflow.log_metrics(metrics_dict, step=step)

        logger.debug(f"Logged metrics: {list(metrics_dict.keys())}")

    def log_feature_importance(
        self,
        feature_names: List[str],
        importance_scores: np.ndarray,
        importance_type: str = "gain",
        top_n: int = 30
    ):
        """
        Log feature importance as artifact and plot.

        Args:
            feature_names: List of feature names
            importance_scores: Array of importance scores
            importance_type: Type of importance (gain, weight, shap)
            top_n: Number of top features to display in plot
        """
        # Sort by importance
        indices = np.argsort(importance_scores)[::-1]

        # Save full importance to JSON
        importance_dict = {
            name: float(importance_scores[i])
            for i, name in enumerate(feature_names)
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(importance_dict, f, indent=2)
            json_path = f.name

        mlflow.log_artifact(json_path, "feature_importance")
        os.unlink(json_path)

        # Create and save plot
        top_indices = indices[:top_n]
        top_names = [feature_names[i] for i in top_indices]
        top_scores = importance_scores[top_indices]

        fig, ax = plt.subplots(figsize=(10, 8))
        y_pos = np.arange(len(top_names))

        ax.barh(y_pos, top_scores, align='center')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(top_names, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel(f'Importance ({importance_type})')
        ax.set_title(f'Top {top_n} Feature Importance')
        plt.tight_layout()

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            plt.savefig(f.name, dpi=150, bbox_inches='tight')
            plot_path = f.name

        plt.close(fig)

        mlflow.log_artifact(plot_path, "plots")
        os.unlink(plot_path)

        logger.info(f"Logged feature importance ({importance_type}) for {len(feature_names)} features")

    def log_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        labels: Optional[List[str]] = None,
        normalize: bool = True
    ):
        """
        Log confusion matrix as artifact.

        Args:
            y_true: True labels
            y_pred: Predicted labels
            labels: Optional class labels
            normalize: Whether to normalize the matrix
        """
        from sklearn.metrics import confusion_matrix

        cm = confusion_matrix(y_true, y_pred)
        if normalize:
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]

        if labels is None:
            labels = ['Clean', 'Corrupt']

        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        ax.figure.colorbar(im, ax=ax)

        ax.set(
            xticks=np.arange(cm.shape[1]),
            yticks=np.arange(cm.shape[0]),
            xticklabels=labels,
            yticklabels=labels,
            ylabel='True label',
            xlabel='Predicted label'
        )

        # Add text annotations
        fmt = '.2f' if normalize else 'd'
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, format(cm[i, j], fmt),
                       ha="center", va="center",
                       color="white" if cm[i, j] > thresh else "black")

        plt.title('Confusion Matrix')
        plt.tight_layout()

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            plt.savefig(f.name, dpi=150, bbox_inches='tight')
            plot_path = f.name

        plt.close(fig)

        mlflow.log_artifact(plot_path, "plots")
        os.unlink(plot_path)

        logger.info("Logged confusion matrix")

    def log_roc_curve(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray
    ):
        """
        Log ROC curve as artifact.

        Args:
            y_true: True labels
            y_scores: Prediction scores/probabilities
        """
        from sklearn.metrics import roc_curve, auc

        fpr, tpr, thresholds = roc_curve(y_true, y_scores)
        roc_auc = auc(fpr, tpr)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(fpr, tpr, color='darkorange', lw=2,
                label=f'ROC curve (AUC = {roc_auc:.3f})')
        ax.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('False Positive Rate')
        ax.set_ylabel('True Positive Rate')
        ax.set_title('Receiver Operating Characteristic (ROC) Curve')
        ax.legend(loc="lower right")
        plt.tight_layout()

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            plt.savefig(f.name, dpi=150, bbox_inches='tight')
            plot_path = f.name

        plt.close(fig)

        mlflow.log_artifact(plot_path, "plots")
        os.unlink(plot_path)

        # Also save the curve data
        curve_data = {
            'fpr': fpr.tolist(),
            'tpr': tpr.tolist(),
            'thresholds': thresholds.tolist(),
            'auc': roc_auc
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(curve_data, f)
            json_path = f.name

        mlflow.log_artifact(json_path, "curves")
        os.unlink(json_path)

        logger.info(f"Logged ROC curve (AUC: {roc_auc:.3f})")

    def log_precision_recall_curve(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray
    ):
        """
        Log Precision-Recall curve as artifact.

        Args:
            y_true: True labels
            y_scores: Prediction scores/probabilities
        """
        from sklearn.metrics import precision_recall_curve, auc

        precision, recall, thresholds = precision_recall_curve(y_true, y_scores)
        pr_auc = auc(recall, precision)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(recall, precision, color='darkorange', lw=2,
                label=f'PR curve (AUC = {pr_auc:.3f})')

        # Baseline (random classifier)
        no_skill = y_true.sum() / len(y_true)
        ax.plot([0, 1], [no_skill, no_skill], linestyle='--', color='navy',
                label=f'No Skill ({no_skill:.2f})')

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('Recall')
        ax.set_ylabel('Precision')
        ax.set_title('Precision-Recall Curve')
        ax.legend(loc="lower left")
        plt.tight_layout()

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            plt.savefig(f.name, dpi=150, bbox_inches='tight')
            plot_path = f.name

        plt.close(fig)

        mlflow.log_artifact(plot_path, "plots")
        os.unlink(plot_path)

        logger.info(f"Logged Precision-Recall curve (AUC: {pr_auc:.3f})")

    def log_model(
        self,
        model: Any,
        model_name: str,
        signature_input: Optional[np.ndarray] = None,
        signature_output: Optional[np.ndarray] = None,
        register: bool = False,
        registered_model_name: Optional[str] = None
    ):
        """
        Log trained model as artifact.

        Args:
            model: Trained model object
            model_name: Name for the model artifact
            signature_input: Sample input for signature inference
            signature_output: Sample output for signature inference
            register: Whether to register the model in MLflow registry
            registered_model_name: Name for registered model
        """
        # Infer signature if samples provided
        signature = None
        if signature_input is not None and signature_output is not None:
            signature = infer_signature(signature_input, signature_output)

        # Determine model flavor based on type
        model_type = type(model).__module__.split('.')[0]

        if model_type == 'sklearn':
            mlflow.sklearn.log_model(
                model,
                model_name,
                signature=signature,
                registered_model_name=registered_model_name if register else None
            )
        elif model_type == 'xgboost':
            mlflow.xgboost.log_model(
                model,
                model_name,
                signature=signature,
                registered_model_name=registered_model_name if register else None
            )
        elif model_type == 'torch':
            mlflow.pytorch.log_model(
                model,
                model_name,
                signature=signature,
                registered_model_name=registered_model_name if register else None
            )
        else:
            # Generic pickle-based logging
            mlflow.pyfunc.log_model(
                model_name,
                python_model=model,
                signature=signature,
                registered_model_name=registered_model_name if register else None
            )

        logger.info(f"Logged model: {model_name}")

        if register and registered_model_name:
            logger.info(f"Registered model: {registered_model_name}")

    def log_training_report(
        self,
        report: Dict[str, Any],
        filename: str = "training_report.json"
    ):
        """
        Log a comprehensive training report as artifact.

        Args:
            report: Dictionary containing training details
            filename: Name for the report file
        """
        # Ensure all values are JSON serializable
        def make_serializable(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, (np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(v) for v in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        serializable_report = make_serializable(report)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(serializable_report, f, indent=2)
            report_path = f.name

        mlflow.log_artifact(report_path, "reports")
        os.unlink(report_path)

        logger.info(f"Logged training report: {filename}")

    def get_best_run(
        self,
        metric: str = "f1",
        maximize: bool = True,
        model_type: Optional[str] = None,
        top_n: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get the best run(s) based on a metric.

        Args:
            metric: Metric name to optimize
            maximize: Whether to maximize the metric
            model_type: Optional filter by model type
            top_n: Number of top runs to return

        Returns:
            List of run info dictionaries
        """
        order = "DESC" if maximize else "ASC"

        filter_string = ""
        if model_type:
            filter_string = f"tags.model_type = '{model_type}'"

        runs = self.client.search_runs(
            experiment_ids=[self.experiment_id],
            filter_string=filter_string,
            order_by=[f"metrics.{metric} {order}"],
            max_results=top_n
        )

        result = []
        for run in runs:
            result.append({
                'run_id': run.info.run_id,
                'run_name': run.info.run_name,
                'status': run.info.status,
                'start_time': datetime.fromtimestamp(run.info.start_time / 1000),
                'metrics': run.data.metrics,
                'params': run.data.params,
                'tags': run.data.tags
            })

        return result

    def compare_runs(
        self,
        run_ids: List[str],
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare multiple runs side by side.

        Args:
            run_ids: List of run IDs to compare
            metrics: Specific metrics to compare (all if None)

        Returns:
            Dictionary with run comparisons
        """
        if metrics is None:
            metrics = ['precision', 'recall', 'f1', 'auc_roc', 'auc_pr']

        comparison = {}

        for run_id in run_ids:
            run = self.client.get_run(run_id)

            comparison[run_id] = {
                'run_name': run.info.run_name,
                'model_type': run.data.tags.get('model_type', 'unknown'),
                'start_time': datetime.fromtimestamp(run.info.start_time / 1000),
                'metrics': {m: run.data.metrics.get(m) for m in metrics if m in run.data.metrics},
                'params': run.data.params
            }

        return comparison

    def transition_model_stage(
        self,
        model_name: str,
        version: int,
        stage: str
    ):
        """
        Transition a registered model to a new stage.

        Args:
            model_name: Name of the registered model
            version: Model version number
            stage: Target stage (Staging, Production, Archived)
        """
        self.client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage=stage
        )

        logger.info(f"Transitioned {model_name} v{version} to {stage}")

    def load_model(
        self,
        run_id: str,
        model_name: str
    ) -> Any:
        """
        Load a model from a specific run.

        Args:
            run_id: Run ID containing the model
            model_name: Name of the model artifact

        Returns:
            Loaded model object
        """
        model_uri = f"runs:/{run_id}/{model_name}"

        # Try different model flavors
        try:
            return mlflow.sklearn.load_model(model_uri)
        except Exception:
            pass

        try:
            return mlflow.xgboost.load_model(model_uri)
        except Exception:
            pass

        try:
            return mlflow.pytorch.load_model(model_uri)
        except Exception:
            pass

        # Fall back to pyfunc
        return mlflow.pyfunc.load_model(model_uri)

    def load_production_model(
        self,
        model_name: str
    ) -> Any:
        """
        Load the production version of a registered model.

        Args:
            model_name: Name of the registered model

        Returns:
            Loaded model object
        """
        model_uri = f"models:/{model_name}/Production"
        return mlflow.pyfunc.load_model(model_uri)

    def get_run_artifacts(
        self,
        run_id: str
    ) -> List[Dict[str, str]]:
        """
        List all artifacts for a run.

        Args:
            run_id: Run ID

        Returns:
            List of artifact info dictionaries
        """
        artifacts = self.client.list_artifacts(run_id)
        return [{'path': a.path, 'is_dir': a.is_dir} for a in artifacts]

    def cleanup_old_runs(
        self,
        days_to_keep: int = 30,
        keep_best_n: int = 5
    ):
        """
        Clean up old runs, keeping best performers.

        Args:
            days_to_keep: Delete runs older than this
            keep_best_n: Always keep the best N runs by F1
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        cutoff_ms = int(cutoff_time.timestamp() * 1000)

        # Get best runs to preserve
        best_runs = self.get_best_run(metric="f1", top_n=keep_best_n)
        best_run_ids = {r['run_id'] for r in best_runs}

        # Find old runs
        runs = self.client.search_runs(
            experiment_ids=[self.experiment_id],
            filter_string=f"attributes.start_time < {cutoff_ms}",
            max_results=1000
        )

        deleted = 0
        for run in runs:
            if run.info.run_id not in best_run_ids:
                self.client.delete_run(run.info.run_id)
                deleted += 1

        logger.info(f"Cleaned up {deleted} old runs (kept {len(best_run_ids)} best)")


# Convenience function for quick initialization
def get_tracker(
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    tracking_uri: Optional[str] = None
) -> CorruptionMLflowTracker:
    """
    Get or create an MLflow tracker.

    Args:
        experiment_name: Experiment name
        tracking_uri: Optional tracking URI

    Returns:
        CorruptionMLflowTracker instance
    """
    return CorruptionMLflowTracker(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name
    )


def calculate_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_scores: Optional[np.ndarray] = None
) -> ModelMetrics:
    """
    Calculate all standard metrics from predictions.

    Args:
        y_true: True labels
        y_pred: Predicted labels
        y_scores: Prediction probabilities (for ROC/PR)

    Returns:
        ModelMetrics object
    """
    from sklearn.metrics import (
        precision_score, recall_score, f1_score,
        accuracy_score, roc_auc_score, average_precision_score,
        confusion_matrix
    )

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    accuracy = accuracy_score(y_true, y_pred)

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    balanced_acc = (recall + specificity) / 2

    # ROC and PR AUC (require probability scores)
    if y_scores is not None:
        auc_roc = roc_auc_score(y_true, y_scores)
        auc_pr = average_precision_score(y_true, y_scores)
    else:
        auc_roc = 0.0
        auc_pr = 0.0

    return ModelMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        auc_roc=auc_roc,
        auc_pr=auc_pr,
        accuracy=accuracy,
        specificity=specificity,
        balanced_accuracy=balanced_acc,
        true_positives=int(tp),
        true_negatives=int(tn),
        false_positives=int(fp),
        false_negatives=int(fn)
    )


# =============================================================================
# Context Managers for Clean Run Handling
# =============================================================================

@contextmanager
def mlflow_run(
    run_name: str,
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    tracking_uri: Optional[str] = None,
    config: Optional[TrainingConfig] = None,
    tags: Optional[Dict[str, str]] = None,
    nested: bool = False
):
    """
    Context manager for MLflow runs.

    Provides clean run management with automatic cleanup, error handling,
    and status tracking.

    Usage:
        with mlflow_run("my_experiment", config=config) as run:
            # Training code here
            mlflow.log_metric("accuracy", 0.95)
            # Run is automatically ended when exiting context

    Args:
        run_name: Name for this run
        experiment_name: Experiment name
        tracking_uri: Optional tracking URI override
        config: Optional TrainingConfig for automatic parameter logging
        tags: Additional tags
        nested: Whether this is a nested run (for CV folds)

    Yields:
        mlflow.ActiveRun: The active run object
    """
    uri = tracking_uri or DEFAULT_TRACKING_URI
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(experiment_name)

    run_tags = {
        "run_started": datetime.utcnow().isoformat(),
    }
    if tags:
        run_tags.update(tags)
    if config:
        run_tags["model_type"] = config.model_type
        run_tags["feature_version"] = config.feature_version

    run = None
    start_time = time.time()

    try:
        run = mlflow.start_run(run_name=run_name, tags=run_tags, nested=nested)

        # Log parameters if config provided
        if config:
            mlflow.log_params(config.to_dict())

        yield run

        # Log training duration
        duration = time.time() - start_time
        mlflow.log_metric("training_duration_seconds", duration)
        mlflow.end_run(status="FINISHED")

    except Exception as e:
        logger.error(f"MLflow run failed: {e}")
        if run:
            mlflow.log_param("error_message", str(e)[:500])  # Truncate long errors
            mlflow.end_run(status="FAILED")
        raise


@contextmanager
def cv_nested_run(
    fold: int,
    parent_run_id: Optional[str] = None
):
    """
    Context manager for cross-validation fold runs (nested within parent).

    Usage:
        with mlflow_run("rf_training", config=config) as parent:
            for fold in range(5):
                with cv_nested_run(fold) as fold_run:
                    # Train and evaluate fold
                    mlflow.log_metric("fold_f1", f1_score)

    Args:
        fold: Fold number (0-indexed)
        parent_run_id: Parent run ID (auto-detected if not provided)

    Yields:
        mlflow.ActiveRun: The nested fold run
    """
    try:
        run = mlflow.start_run(
            run_name=f"fold_{fold}",
            nested=True,
            tags={"fold": str(fold)}
        )
        yield run
        mlflow.end_run(status="FINISHED")
    except Exception as e:
        logger.error(f"CV fold {fold} run failed: {e}")
        mlflow.end_run(status="FAILED")
        raise


# =============================================================================
# Decorators for Training Functions
# =============================================================================

def track_training(
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    tracking_uri: Optional[str] = None,
    log_model: bool = True,
    model_name: Optional[str] = None
):
    """
    Decorator for tracking training functions with MLflow.

    Automatically logs:
    - Function parameters as MLflow params
    - Training duration
    - Return values (if dict with metrics)
    - Model artifact (if enabled)

    Usage:
        @track_training(experiment_name="corruption_rf")
        def train_random_forest(
            X_train, y_train, X_test, y_test,
            n_estimators=100, max_depth=10
        ):
            # Training logic
            model = RandomForestClassifier(n_estimators=n_estimators)
            model.fit(X_train, y_train)
            accuracy = model.score(X_test, y_test)
            return {"model": model, "accuracy": accuracy}

    Args:
        experiment_name: MLflow experiment name
        tracking_uri: Optional tracking URI
        log_model: Whether to log model artifact
        model_name: Name for the model artifact

    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            uri = tracking_uri or DEFAULT_TRACKING_URI
            mlflow.set_tracking_uri(uri)
            mlflow.set_experiment(experiment_name)

            run_name = f"{func.__name__}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            with mlflow.start_run(run_name=run_name):
                start_time = time.time()

                # Log function kwargs as parameters
                for key, value in kwargs.items():
                    if isinstance(value, (int, float, str, bool)):
                        mlflow.log_param(key, value)
                    elif isinstance(value, (list, tuple)) and len(value) <= 10:
                        mlflow.log_param(key, str(value))

                # Execute training function
                result = func(*args, **kwargs)

                # Log duration
                duration = time.time() - start_time
                mlflow.log_metric("training_duration_seconds", duration)

                # Log metrics if result is dict
                if isinstance(result, dict):
                    metrics_to_log = {}
                    model_to_log = None

                    for key, value in result.items():
                        if key == 'model':
                            model_to_log = value
                        elif key == 'metrics' and isinstance(value, ModelMetrics):
                            metrics_to_log.update(value.to_dict())
                        elif isinstance(value, (int, float)) and not np.isnan(value):
                            metrics_to_log[key] = value

                    if metrics_to_log:
                        mlflow.log_metrics(metrics_to_log)

                    # Log model if requested
                    if log_model and model_to_log is not None:
                        artifact_name = model_name or func.__name__
                        _log_model_by_type(model_to_log, artifact_name)

                return result

        return wrapper
    return decorator


def _log_model_by_type(model: Any, model_name: str):
    """Helper to log model by detecting its type."""
    model_type = type(model).__module__.split('.')[0]

    try:
        if model_type == 'sklearn':
            mlflow.sklearn.log_model(model, model_name)
        elif model_type == 'xgboost':
            mlflow.xgboost.log_model(model, model_name)
        elif model_type == 'torch':
            mlflow.pytorch.log_model(model, model_name)
        else:
            # Fallback: save as pickle artifact
            import pickle
            with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
                pickle.dump(model, f)
                temp_path = f.name
            mlflow.log_artifact(temp_path, "models")
            os.unlink(temp_path)
            logger.info(f"Logged model as pickle artifact: {model_name}")
    except Exception as e:
        logger.warning(f"Failed to log model: {e}")


def track_cv_fold(fold_metric: str = "f1"):
    """
    Decorator for tracking individual CV folds.

    Usage:
        @track_cv_fold(fold_metric="f1")
        def train_fold(X_train, y_train, X_val, y_val, fold_idx):
            model = RandomForestClassifier()
            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)
            return {"f1": f1_score(y_val, y_pred), "model": model}

    Args:
        fold_metric: Primary metric to track across folds

    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, fold_idx: int = 0, **kwargs):
            with cv_nested_run(fold_idx):
                result = func(*args, fold_idx=fold_idx, **kwargs)

                if isinstance(result, dict):
                    metrics = {k: v for k, v in result.items()
                              if isinstance(v, (int, float)) and k != 'model'}
                    if metrics:
                        mlflow.log_metrics(metrics)

                return result

        return wrapper
    return decorator


# =============================================================================
# Additional Helper Functions
# =============================================================================

def log_cv_summary(
    fold_metrics: List[Dict[str, float]],
    primary_metric: str = "f1"
):
    """
    Log cross-validation summary metrics.

    Args:
        fold_metrics: List of metric dictionaries from each fold
        primary_metric: Metric to use for computing mean/std
    """
    if not fold_metrics:
        return

    # Compute aggregate statistics
    all_metrics = {}
    for fold_result in fold_metrics:
        for key, value in fold_result.items():
            if isinstance(value, (int, float)):
                if key not in all_metrics:
                    all_metrics[key] = []
                all_metrics[key].append(value)

    # Log mean and std for each metric
    summary = {}
    for key, values in all_metrics.items():
        arr = np.array(values)
        summary[f"cv_mean_{key}"] = float(arr.mean())
        summary[f"cv_std_{key}"] = float(arr.std())

    mlflow.log_metrics(summary)

    # Log detailed fold results as artifact
    fold_data = {
        "folds": fold_metrics,
        "summary": summary
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(fold_data, f, indent=2)
        temp_path = f.name

    mlflow.log_artifact(temp_path, "cv_results")
    os.unlink(temp_path)

    logger.info(f"CV Summary - {primary_metric}: "
                f"{summary.get(f'cv_mean_{primary_metric}', 0):.4f} "
                f"(+/- {summary.get(f'cv_std_{primary_metric}', 0):.4f})")


def log_hyperparameter_search(
    search_results: Dict[str, Any],
    best_params: Dict[str, Any],
    best_score: float,
    metric_name: str = "score"
):
    """
    Log hyperparameter search results.

    Args:
        search_results: Full search results (e.g., from GridSearchCV.cv_results_)
        best_params: Best hyperparameters found
        best_score: Best score achieved
        metric_name: Name of the optimization metric
    """
    # Log best parameters
    for key, value in best_params.items():
        mlflow.log_param(f"best_{key}", value)

    mlflow.log_metric(f"best_{metric_name}", best_score)

    # Log search results as artifact
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        # Make serializable
        serializable = {}
        for key, value in search_results.items():
            if isinstance(value, np.ndarray):
                serializable[key] = value.tolist()
            elif isinstance(value, (int, float, str, list, dict)):
                serializable[key] = value

        json.dump({
            "best_params": best_params,
            "best_score": best_score,
            "search_results": serializable
        }, f, indent=2)
        temp_path = f.name

    mlflow.log_artifact(temp_path, "hyperparameter_search")
    os.unlink(temp_path)


def log_dataset_info(
    train_size: int,
    val_size: int,
    test_size: int,
    n_features: int,
    positive_rate: float,
    feature_names: Optional[List[str]] = None
):
    """
    Log dataset information as parameters.

    Args:
        train_size: Number of training samples
        val_size: Number of validation samples
        test_size: Number of test samples
        n_features: Number of features
        positive_rate: Rate of positive class
        feature_names: Optional list of feature names
    """
    mlflow.log_params({
        "train_size": train_size,
        "val_size": val_size,
        "test_size": test_size,
        "total_size": train_size + val_size + test_size,
        "n_features": n_features,
        "positive_rate": round(positive_rate, 4)
    })

    if feature_names:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(feature_names, f)
            temp_path = f.name
        mlflow.log_artifact(temp_path, "dataset_info")
        os.unlink(temp_path)


def log_model_comparison(
    model_results: Dict[str, Dict[str, float]],
    comparison_metric: str = "test_f1"
):
    """
    Log comparison of multiple models.

    Args:
        model_results: Dict mapping model name to metrics dict
        comparison_metric: Metric to use for ranking
    """
    # Create comparison table
    comparison = []
    for model_name, metrics in model_results.items():
        comparison.append({
            "model": model_name,
            **metrics
        })

    # Sort by comparison metric
    comparison.sort(
        key=lambda x: x.get(comparison_metric, 0),
        reverse=True
    )

    # Log as artifact
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "comparison_metric": comparison_metric,
            "models": comparison,
            "best_model": comparison[0]["model"] if comparison else None
        }, f, indent=2)
        temp_path = f.name

    mlflow.log_artifact(temp_path, "model_comparison")
    os.unlink(temp_path)

    # Log best model info
    if comparison:
        best = comparison[0]
        mlflow.log_param("best_model_name", best["model"])
        mlflow.log_metric(f"best_{comparison_metric}", best.get(comparison_metric, 0))


def get_or_create_experiment(
    experiment_name: str,
    tracking_uri: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None
) -> str:
    """
    Get or create an MLflow experiment.

    Args:
        experiment_name: Name of the experiment
        tracking_uri: Optional tracking URI
        tags: Optional experiment tags

    Returns:
        Experiment ID
    """
    uri = tracking_uri or DEFAULT_TRACKING_URI
    mlflow.set_tracking_uri(uri)

    experiment = mlflow.get_experiment_by_name(experiment_name)

    if experiment is None:
        default_tags = {
            "project": "nabavkidata",
            "domain": "corruption_detection",
            "created": datetime.utcnow().isoformat()
        }
        if tags:
            default_tags.update(tags)

        experiment_id = mlflow.create_experiment(experiment_name, tags=default_tags)
        logger.info(f"Created experiment: {experiment_name} (ID: {experiment_id})")
    else:
        experiment_id = experiment.experiment_id

    return experiment_id


# =============================================================================
# Quick Setup Function
# =============================================================================

def setup_mlflow(
    experiment_name: str = DEFAULT_EXPERIMENT_NAME,
    tracking_uri: Optional[str] = None,
    use_sqlite: bool = True
) -> CorruptionMLflowTracker:
    """
    Quick setup for MLflow tracking.

    Creates necessary directories, configures SQLite backend (optional),
    and returns a configured tracker.

    Args:
        experiment_name: Experiment name
        tracking_uri: Optional tracking URI (auto-configured if None)
        use_sqlite: Use SQLite backend for better querying (default: True)

    Returns:
        Configured CorruptionMLflowTracker

    Example:
        tracker = setup_mlflow("corruption_detection")
        with mlflow_run("training", config=config) as run:
            # Training code
            tracker.log_metrics(metrics)
    """
    if tracking_uri is None:
        # Create mlruns directory in project root
        project_root = Path(__file__).parent.parent.parent.parent
        mlruns_dir = project_root / "mlruns"
        mlruns_dir.mkdir(exist_ok=True)

        if use_sqlite:
            # Use SQLite backend for better query performance
            db_path = mlruns_dir / "mlflow.db"
            tracking_uri = f"sqlite:///{db_path}"
            artifacts_dir = mlruns_dir / "artifacts"
            artifacts_dir.mkdir(exist_ok=True)
            os.environ["MLFLOW_ARTIFACT_ROOT"] = str(artifacts_dir)
        else:
            tracking_uri = f"file://{mlruns_dir}"

    os.environ["MLFLOW_TRACKING_URI"] = tracking_uri
    mlflow.set_tracking_uri(tracking_uri)

    logger.info(f"MLflow configured with tracking URI: {tracking_uri}")

    return CorruptionMLflowTracker(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name
    )

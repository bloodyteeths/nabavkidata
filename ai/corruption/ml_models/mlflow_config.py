"""
MLflow Configuration for Corruption Detection Pipeline

This module provides centralized configuration for MLflow experiment tracking,
including environment-specific settings and model registry configuration.

Configuration priority:
1. Environment variables
2. Config file settings
3. Default values

Usage:
    from ai.corruption.ml_models.mlflow_config import MLflowConfig, get_config

    # Get configuration (auto-detects environment)
    config = get_config()

    # Initialize MLflow with config
    config.initialize()

    # Use in training
    with mlflow.start_run(run_name="my_training"):
        ...

Author: NabavkiData
License: Proprietary
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Deployment environment."""
    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class MLflowConfig:
    """
    MLflow configuration for corruption detection experiments.

    Attributes:
        environment: Deployment environment (local, development, staging, production)
        tracking_uri: MLflow tracking server URI
        artifact_root: Root directory for artifact storage
        experiment_name: Default experiment name
        registry_uri: Model registry URI (can differ from tracking)
        backend_store_uri: Backend store for run metadata
        default_artifact_root: Default artifact location

    Model-specific settings:
        random_forest_experiment: Experiment for RF models
        xgboost_experiment: Experiment for XGBoost models
        neural_network_experiment: Experiment for NN models
        gnn_experiment: Experiment for GNN models
        ensemble_experiment: Experiment for ensemble models
    """

    # Core settings
    environment: Environment = Environment.LOCAL
    tracking_uri: str = ""
    artifact_root: str = ""
    experiment_name: str = "corruption_detection"
    registry_uri: Optional[str] = None
    backend_store_uri: Optional[str] = None

    # Model-specific experiments
    random_forest_experiment: str = "corruption_detection_rf"
    xgboost_experiment: str = "corruption_detection_xgb"
    neural_network_experiment: str = "corruption_detection_nn"
    gnn_experiment: str = "corruption_detection_gnn"
    ensemble_experiment: str = "corruption_detection_ensemble"

    # Logging settings
    log_system_metrics: bool = True
    log_git_info: bool = True
    autolog_enabled: bool = False  # sklearn/pytorch autolog

    # Artifact settings
    log_models: bool = True
    log_feature_importance: bool = True
    log_confusion_matrix: bool = True
    log_roc_curve: bool = True
    log_pr_curve: bool = True

    # Run settings
    nested_runs_enabled: bool = True
    run_name_prefix: str = ""

    # Model registry settings
    auto_register_best: bool = True
    promotion_metric: str = "test_f1"
    promotion_threshold: float = 0.7

    # Cleanup settings
    cleanup_after_days: int = 30
    keep_best_n_runs: int = 10

    def __post_init__(self):
        """Set defaults based on environment if not specified."""
        if not self.tracking_uri:
            self.tracking_uri = self._get_default_tracking_uri()
        if not self.artifact_root:
            self.artifact_root = self._get_default_artifact_root()

    def _get_default_tracking_uri(self) -> str:
        """Get default tracking URI based on environment."""
        project_root = Path(__file__).parent.parent.parent.parent
        mlruns_dir = project_root / "mlruns"
        mlruns_dir.mkdir(exist_ok=True)

        if self.environment == Environment.LOCAL:
            # Local SQLite for development
            db_path = mlruns_dir / "mlflow.db"
            return f"sqlite:///{db_path}"
        elif self.environment == Environment.DEVELOPMENT:
            # File-based for dev server
            return f"file://{mlruns_dir}"
        elif self.environment in (Environment.STAGING, Environment.PRODUCTION):
            # Would typically be a remote tracking server
            # For now, use file-based
            return f"file://{mlruns_dir}"

        return f"file://{mlruns_dir}"

    def _get_default_artifact_root(self) -> str:
        """Get default artifact root based on environment."""
        project_root = Path(__file__).parent.parent.parent.parent
        artifacts_dir = project_root / "mlruns" / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        return str(artifacts_dir)

    def initialize(self):
        """
        Initialize MLflow with this configuration.

        Sets tracking URI, creates experiment if needed, and configures
        environment variables.
        """
        import mlflow

        # Set tracking URI
        mlflow.set_tracking_uri(self.tracking_uri)

        # Set environment variables
        os.environ["MLFLOW_TRACKING_URI"] = self.tracking_uri
        if self.artifact_root:
            os.environ["MLFLOW_ARTIFACT_ROOT"] = self.artifact_root

        # Create default experiment if it doesn't exist
        experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            mlflow.create_experiment(
                self.experiment_name,
                tags={
                    "project": "nabavkidata",
                    "domain": "corruption_detection",
                    "environment": self.environment.value
                }
            )
            logger.info(f"Created experiment: {self.experiment_name}")

        mlflow.set_experiment(self.experiment_name)

        logger.info(f"MLflow initialized: {self.tracking_uri}")
        logger.info(f"Default experiment: {self.experiment_name}")

    def get_experiment_for_model(self, model_type: str) -> str:
        """
        Get the experiment name for a specific model type.

        Args:
            model_type: Type of model (random_forest, xgboost, neural_network, gnn, ensemble)

        Returns:
            Experiment name for that model type
        """
        mapping = {
            "random_forest": self.random_forest_experiment,
            "rf": self.random_forest_experiment,
            "xgboost": self.xgboost_experiment,
            "xgb": self.xgboost_experiment,
            "neural_network": self.neural_network_experiment,
            "nn": self.neural_network_experiment,
            "gnn": self.gnn_experiment,
            "graph": self.gnn_experiment,
            "ensemble": self.ensemble_experiment,
            "stacking": self.ensemble_experiment,
        }
        return mapping.get(model_type.lower(), self.experiment_name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "environment": self.environment.value,
            "tracking_uri": self.tracking_uri,
            "artifact_root": self.artifact_root,
            "experiment_name": self.experiment_name,
            "registry_uri": self.registry_uri,
            "random_forest_experiment": self.random_forest_experiment,
            "xgboost_experiment": self.xgboost_experiment,
            "neural_network_experiment": self.neural_network_experiment,
            "gnn_experiment": self.gnn_experiment,
            "ensemble_experiment": self.ensemble_experiment,
            "log_models": self.log_models,
            "log_feature_importance": self.log_feature_importance,
            "auto_register_best": self.auto_register_best,
            "promotion_metric": self.promotion_metric,
            "promotion_threshold": self.promotion_threshold,
        }

    def save(self, path: str):
        """Save configuration to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Configuration saved to {path}")

    @classmethod
    def load(cls, path: str) -> 'MLflowConfig':
        """Load configuration from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)

        # Convert environment string to enum
        if 'environment' in data:
            data['environment'] = Environment(data['environment'])

        return cls(**data)


# =============================================================================
# Default Configurations for Different Environments
# =============================================================================

def get_local_config() -> MLflowConfig:
    """Get configuration for local development."""
    return MLflowConfig(
        environment=Environment.LOCAL,
        experiment_name="corruption_detection_local",
        autolog_enabled=False,
        log_system_metrics=True,
        cleanup_after_days=7,
        keep_best_n_runs=5,
    )


def get_development_config() -> MLflowConfig:
    """Get configuration for development server."""
    return MLflowConfig(
        environment=Environment.DEVELOPMENT,
        experiment_name="corruption_detection_dev",
        autolog_enabled=True,
        log_system_metrics=True,
        cleanup_after_days=14,
        keep_best_n_runs=10,
    )


def get_production_config() -> MLflowConfig:
    """Get configuration for production."""
    return MLflowConfig(
        environment=Environment.PRODUCTION,
        experiment_name="corruption_detection",
        autolog_enabled=False,  # Explicit logging in production
        log_system_metrics=True,
        log_git_info=True,
        auto_register_best=True,
        promotion_threshold=0.75,
        cleanup_after_days=90,
        keep_best_n_runs=20,
    )


def get_config(environment: Optional[str] = None) -> MLflowConfig:
    """
    Get MLflow configuration based on environment.

    Priority:
    1. Explicit environment parameter
    2. MLFLOW_ENV environment variable
    3. ENVIRONMENT environment variable
    4. Default to LOCAL

    Args:
        environment: Optional environment name override

    Returns:
        MLflowConfig for the detected environment
    """
    if environment is None:
        environment = os.environ.get(
            "MLFLOW_ENV",
            os.environ.get("ENVIRONMENT", "local")
        ).lower()

    env_configs = {
        "local": get_local_config,
        "development": get_development_config,
        "dev": get_development_config,
        "staging": get_production_config,  # Use production config for staging
        "production": get_production_config,
        "prod": get_production_config,
    }

    config_func = env_configs.get(environment, get_local_config)
    config = config_func()

    logger.info(f"Loaded MLflow config for environment: {config.environment.value}")
    return config


# =============================================================================
# Model Registry Configuration
# =============================================================================

@dataclass
class ModelRegistryConfig:
    """Configuration for model registry and model lifecycle management."""

    # Registry settings
    model_name_prefix: str = "corruption_detector"
    version_description_template: str = "Trained on {date} with {n_samples} samples. F1: {f1:.4f}"

    # Stage transitions
    staging_min_f1: float = 0.65
    production_min_f1: float = 0.75
    auto_transition_to_staging: bool = True
    require_approval_for_production: bool = True

    # Model comparison
    compare_with_production: bool = True
    production_improvement_threshold: float = 0.02  # Must be 2% better

    # Archival
    archive_replaced_models: bool = True
    keep_archived_versions: int = 5

    def get_model_name(self, model_type: str) -> str:
        """Get registry model name for a model type."""
        return f"{self.model_name_prefix}_{model_type}"


# =============================================================================
# Hyperparameter Search Configuration
# =============================================================================

@dataclass
class HyperparameterConfig:
    """Default hyperparameter search spaces for each model type."""

    random_forest: Dict[str, Any] = field(default_factory=lambda: {
        "n_estimators": [100, 200, 300, 500],
        "max_depth": [10, 20, 30, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", "log2", 0.3, 0.5],
    })

    xgboost: Dict[str, Any] = field(default_factory=lambda: {
        "n_estimators": [100, 200, 300, 500],
        "max_depth": [4, 6, 8, 10],
        "learning_rate": [0.01, 0.05, 0.1, 0.2],
        "subsample": [0.6, 0.8, 1.0],
        "colsample_bytree": [0.6, 0.8, 1.0],
        "min_child_weight": [1, 3, 5, 7],
        "reg_alpha": [0, 0.1, 0.5],
        "reg_lambda": [0.5, 1.0, 2.0],
    })

    neural_network: Dict[str, Any] = field(default_factory=lambda: {
        "hidden_dims": [(128, 64), (256, 128, 64), (128, 64, 32)],
        "dropout_rate": [0.2, 0.3, 0.4],
        "learning_rate": [0.001, 0.0005, 0.0001],
        "batch_size": [32, 64, 128],
    })

    gnn: Dict[str, Any] = field(default_factory=lambda: {
        "hidden_dim": [32, 64, 128],
        "output_dim": [16, 32, 64],
        "num_layers": [2, 3, 4],
        "num_heads": [2, 4, 8],
        "dropout": [0.2, 0.3, 0.4],
        "learning_rate": [0.001, 0.0005],
    })

    def get_search_space(self, model_type: str) -> Dict[str, Any]:
        """Get hyperparameter search space for a model type."""
        spaces = {
            "random_forest": self.random_forest,
            "rf": self.random_forest,
            "xgboost": self.xgboost,
            "xgb": self.xgboost,
            "neural_network": self.neural_network,
            "nn": self.neural_network,
            "gnn": self.gnn,
            "graph": self.gnn,
        }
        return spaces.get(model_type.lower(), {})


# =============================================================================
# Global Configuration Instance
# =============================================================================

# Lazy-loaded global config
_global_config: Optional[MLflowConfig] = None


def init_config(environment: Optional[str] = None) -> MLflowConfig:
    """
    Initialize the global MLflow configuration.

    Args:
        environment: Optional environment name

    Returns:
        Initialized MLflowConfig
    """
    global _global_config
    _global_config = get_config(environment)
    _global_config.initialize()
    return _global_config


def get_global_config() -> MLflowConfig:
    """
    Get the global MLflow configuration, initializing if needed.

    Returns:
        MLflowConfig instance
    """
    global _global_config
    if _global_config is None:
        _global_config = get_config()
        _global_config.initialize()
    return _global_config


# =============================================================================
# Convenience Functions
# =============================================================================

def quick_setup(
    experiment_name: Optional[str] = None,
    environment: str = "local"
) -> MLflowConfig:
    """
    Quick setup for MLflow tracking.

    Args:
        experiment_name: Optional custom experiment name
        environment: Environment name (local, development, production)

    Returns:
        Configured and initialized MLflowConfig

    Example:
        config = quick_setup("my_experiment")
        # MLflow is now configured and ready to use
    """
    config = get_config(environment)
    if experiment_name:
        config.experiment_name = experiment_name
    config.initialize()
    return config


if __name__ == "__main__":
    # Test configuration
    logging.basicConfig(level=logging.INFO)

    print("Testing MLflow Configuration")
    print("=" * 50)

    # Test local config
    config = get_local_config()
    print(f"\nLocal config:")
    print(f"  Tracking URI: {config.tracking_uri}")
    print(f"  Artifact Root: {config.artifact_root}")
    print(f"  Experiment: {config.experiment_name}")

    # Test initialization
    config.initialize()
    print("\nMLflow initialized successfully!")

    # Test model experiment mapping
    print("\nModel experiment mapping:")
    for model_type in ["random_forest", "xgboost", "neural_network", "gnn", "ensemble"]:
        exp = config.get_experiment_for_model(model_type)
        print(f"  {model_type}: {exp}")

    # Test hyperparameter config
    hp_config = HyperparameterConfig()
    print("\nHyperparameter search space for XGBoost:")
    for param, values in hp_config.get_search_space("xgboost").items():
        print(f"  {param}: {values}")

    print("\nConfiguration test complete!")

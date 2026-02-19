"""
ML Models for Corruption Detection

Ensemble approach exceeding Dozorro's performance:
- Random Forest: Robust baseline classifier
- XGBoost: Gradient boosting for tabular data
- Neural Network: Deep learning for complex patterns
- Ensemble: Stacking meta-learner combining all models

Specialized Models:
- GNN (GraphSAGE + GAT): Collusion network detection via graph neural networks
- Graph Builder: Construct bidder-tender graphs from database
- Collusion Detector: Community detection and pattern-based collusion detection
- Hybrid Anomaly: Isolation Forest + Autoencoder + LOF + One-Class SVM

All models are tracked via MLflow for versioning and performance monitoring.

Usage:
    from ai.corruption.ml_models import (
        CorruptionNeuralNetwork,
        CorruptionEnsemble,
        create_neural_network,
        create_ensemble,
        HybridAnomalyDetector,
        AnomalyExplainer
    )

    # Neural Network
    nn_model = CorruptionNeuralNetwork(input_dim=113)
    nn_model.fit(X_train, y_train, X_val, y_val)
    predictions = nn_model.predict_proba(X_test)

    # Ensemble with stacking
    ensemble = create_ensemble({
        'rf': RandomForestClassifier(n_estimators=100),
        'xgb': XGBClassifier(n_estimators=100),
        'nn': nn_model
    })
    ensemble.fit(X_train, y_train)
    ensemble_predictions = ensemble.predict_proba(X_test)

    # Hybrid Anomaly Detection (Unsupervised)
    detector = HybridAnomalyDetector(contamination=0.05)
    detector.fit(X_normal, feature_names=feature_names)
    scores = detector.anomaly_score(X_test)
    results = detector.score_tenders(X_test, tender_ids)

    # Explain anomalies
    explainer = AnomalyExplainer()
    explainer.fit(X_normal, tender_ids_normal, feature_names)
    explanation = explainer.explain(tender_id, features, anomaly_score)
"""

# Neural Network
try:
    from ai.corruption.ml_models.neural_network import (
        CorruptionNeuralNetwork,
        CorruptionMLP,
        create_neural_network
    )
    _NEURAL_NETWORK_AVAILABLE = True
except ImportError as e:
    _NEURAL_NETWORK_AVAILABLE = False
    CorruptionNeuralNetwork = None
    CorruptionMLP = None
    create_neural_network = None

# Ensemble
try:
    from ai.corruption.ml_models.ensemble import (
        CorruptionEnsemble,
        MetaLearner,
        SimpleWeightedEnsemble,
        create_ensemble,
        BaseModel
    )
    _ENSEMBLE_AVAILABLE = True
except ImportError as e:
    _ENSEMBLE_AVAILABLE = False
    CorruptionEnsemble = None
    MetaLearner = None
    SimpleWeightedEnsemble = None
    create_ensemble = None
    BaseModel = None

# Hybrid Anomaly Detection
try:
    from ai.corruption.ml_models.hybrid_anomaly import (
        HybridAnomalyDetector,
        TenderAutoencoder,
        AnomalyScore,
        detect_anomalies
    )
    _HYBRID_ANOMALY_AVAILABLE = True
except ImportError as e:
    _HYBRID_ANOMALY_AVAILABLE = False
    HybridAnomalyDetector = None
    TenderAutoencoder = None
    AnomalyScore = None
    detect_anomalies = None

# Anomaly Explainer
try:
    from ai.corruption.ml_models.anomaly_explainer import (
        AnomalyExplainer,
        AnomalyExplanation,
        FeatureAnomaly,
        SimilarTender,
        create_risk_report,
        FEATURE_CATEGORIES,
        FEATURE_DESCRIPTIONS,
        RISK_PATTERNS
    )
    _ANOMALY_EXPLAINER_AVAILABLE = True
except ImportError as e:
    _ANOMALY_EXPLAINER_AVAILABLE = False
    AnomalyExplainer = None
    AnomalyExplanation = None
    FeatureAnomaly = None
    SimilarTender = None
    create_risk_report = None
    FEATURE_CATEGORIES = None
    FEATURE_DESCRIPTIONS = None
    RISK_PATTERNS = None

# Random Forest (Phase 2)
try:
    from ai.corruption.ml_models.random_forest import (
        CorruptionRandomForest,
        ModelMetrics,
        FeatureImportance,
        quick_train_random_forest
    )
    _RANDOM_FOREST_AVAILABLE = True
except ImportError as e:
    _RANDOM_FOREST_AVAILABLE = False
    CorruptionRandomForest = None
    ModelMetrics = None
    FeatureImportance = None
    quick_train_random_forest = None

# XGBoost (Phase 2)
try:
    from ai.corruption.ml_models.xgboost_model import (
        CorruptionXGBoost,
        XGBModelMetrics,
        XGBFeatureImportance,
        quick_train_xgboost
    )
    _XGBOOST_AVAILABLE = True
except ImportError as e:
    _XGBOOST_AVAILABLE = False
    CorruptionXGBoost = None
    XGBModelMetrics = None
    XGBFeatureImportance = None
    quick_train_xgboost = None

# Training Data Extraction (Phase 2)
try:
    from ai.corruption.ml_models.training_data import (
        TrainingDataExtractor,
        TrainingDataset,
        extract_training_data,
        save_training_dataset,
        load_training_dataset
    )
    _TRAINING_DATA_AVAILABLE = True
except ImportError as e:
    _TRAINING_DATA_AVAILABLE = False
    TrainingDataExtractor = None
    TrainingDataset = None
    extract_training_data = None
    save_training_dataset = None
    load_training_dataset = None

# Graph Builder for GNN (Phase 2)
try:
    from ai.corruption.ml_models.graph_builder import (
        GraphBuilder,
        BidderGraph,
        GraphNode,
        GraphEdge,
        build_graph_from_db,
        save_graph,
        load_graph
    )
    _GRAPH_BUILDER_AVAILABLE = True
except ImportError as e:
    _GRAPH_BUILDER_AVAILABLE = False
    GraphBuilder = None
    BidderGraph = None
    GraphNode = None
    GraphEdge = None
    build_graph_from_db = None
    save_graph = None
    load_graph = None

# GNN Collusion Model (Phase 2)
try:
    from ai.corruption.ml_models.gnn_collusion import (
        CollusionGNN,
        CollusionGNNTrainer,
        GNNConfig,
        GraphFeatureExtractor,
        build_collusion_gnn,
        create_train_val_masks,
        augment_node_features
    )
    _GNN_AVAILABLE = True
except ImportError as e:
    _GNN_AVAILABLE = False
    CollusionGNN = None
    CollusionGNNTrainer = None
    GNNConfig = None
    GraphFeatureExtractor = None
    build_collusion_gnn = None
    create_train_val_masks = None
    augment_node_features = None

# Collusion Cluster Detector (Phase 2)
try:
    from ai.corruption.ml_models.collusion_detector import (
        CollusionClusterDetector,
        CollusionCluster,
        CollusionEvidence,
        detect_collusion_clusters,
        export_clusters_to_json
    )
    _COLLUSION_DETECTOR_AVAILABLE = True
except ImportError as e:
    _COLLUSION_DETECTOR_AVAILABLE = False
    CollusionClusterDetector = None
    CollusionCluster = None
    CollusionEvidence = None
    detect_collusion_clusters = None
    export_clusters_to_json = None

# MLflow Tracking (Phase 2)
try:
    from ai.corruption.ml_models.tracking import (
        CorruptionMLflowTracker,
        TrainingConfig,
        ModelMetrics as TrackingModelMetrics,
        get_tracker,
        calculate_metrics,
        # New context managers and decorators
        mlflow_run,
        cv_nested_run,
        track_training,
        track_cv_fold,
        # New helper functions
        setup_mlflow,
        log_cv_summary,
        log_hyperparameter_search,
        log_dataset_info,
        log_model_comparison,
        get_or_create_experiment
    )
    _TRACKING_AVAILABLE = True
except ImportError as e:
    _TRACKING_AVAILABLE = False
    CorruptionMLflowTracker = None
    TrainingConfig = None
    TrackingModelMetrics = None
    get_tracker = None
    calculate_metrics = None
    mlflow_run = None
    cv_nested_run = None
    track_training = None
    track_cv_fold = None
    setup_mlflow = None
    log_cv_summary = None
    log_hyperparameter_search = None
    log_dataset_info = None
    log_model_comparison = None
    get_or_create_experiment = None

# MLflow Configuration (Phase 2)
try:
    from ai.corruption.ml_models.mlflow_config import (
        MLflowConfig,
        Environment,
        ModelRegistryConfig,
        HyperparameterConfig,
        get_config,
        get_local_config,
        get_production_config,
        quick_setup,
        init_config,
        get_global_config
    )
    _MLFLOW_CONFIG_AVAILABLE = True
except ImportError as e:
    _MLFLOW_CONFIG_AVAILABLE = False
    MLflowConfig = None
    Environment = None
    ModelRegistryConfig = None
    HyperparameterConfig = None
    get_config = None
    get_local_config = None
    get_production_config = None
    quick_setup = None
    init_config = None
    get_global_config = None

# Training Pipeline (Phase 2)
try:
    from ai.corruption.ml_models.train_pipeline import (
        CorruptionTrainingPipeline,
        TrainingData,
        TrainingResult
    )
    _TRAIN_PIPELINE_AVAILABLE = True
except ImportError as e:
    _TRAIN_PIPELINE_AVAILABLE = False
    CorruptionTrainingPipeline = None
    TrainingData = None
    TrainingResult = None

# Prediction Pipeline (Phase 2)
try:
    from ai.corruption.ml_models.predict_pipeline import (
        CorruptionPredictor,
        PredictionResult
    )
    _PREDICT_PIPELINE_AVAILABLE = True
except ImportError as e:
    _PREDICT_PIPELINE_AVAILABLE = False
    CorruptionPredictor = None
    PredictionResult = None

# Causal Inference (Phase 3.2)
try:
    from ai.corruption.ml_models.causal_analyzer import CausalAnalyzer
    _CAUSAL_ANALYZER_AVAILABLE = True
except ImportError as e:
    _CAUSAL_ANALYZER_AVAILABLE = False
    CausalAnalyzer = None

# AutoML Pipeline (Phase 3.4)
try:
    from ai.corruption.ml_models.automl import AutoMLPipeline
    _AUTOML_AVAILABLE = True
except ImportError as e:
    _AUTOML_AVAILABLE = False
    AutoMLPipeline = None

# Model Registry (Phase 3.4)
try:
    from ai.corruption.ml_models.model_registry import ModelRegistry
    _MODEL_REGISTRY_AVAILABLE = True
except ImportError as e:
    _MODEL_REGISTRY_AVAILABLE = False
    ModelRegistry = None

# Adversarial Robustness (Phase 3.3)
try:
    from ai.corruption.ml_models.adversarial import AdversarialAnalyzer
    _ADVERSARIAL_AVAILABLE = True
except ImportError as e:
    _ADVERSARIAL_AVAILABLE = False
    AdversarialAnalyzer = None

# Adversarial Training (Phase 3.3)
try:
    from ai.corruption.ml_models.adversarial_training import AdversarialTrainer
    _ADVERSARIAL_TRAINING_AVAILABLE = True
except ImportError as e:
    _ADVERSARIAL_TRAINING_AVAILABLE = False
    AdversarialTrainer = None


def check_dependencies() -> dict:
    """
    Check which ML dependencies are available.

    Returns:
        Dictionary with availability status of each component
    """
    status = {
        'neural_network': _NEURAL_NETWORK_AVAILABLE,
        'ensemble': _ENSEMBLE_AVAILABLE,
        'hybrid_anomaly': _HYBRID_ANOMALY_AVAILABLE,
        'anomaly_explainer': _ANOMALY_EXPLAINER_AVAILABLE,
        'random_forest': _RANDOM_FOREST_AVAILABLE,
        'xgboost': _XGBOOST_AVAILABLE,
        'training_data': _TRAINING_DATA_AVAILABLE,
        'graph_builder': _GRAPH_BUILDER_AVAILABLE,
        'gnn': _GNN_AVAILABLE,
        'collusion_detector': _COLLUSION_DETECTOR_AVAILABLE,
        'tracking': _TRACKING_AVAILABLE,
        'mlflow_config': _MLFLOW_CONFIG_AVAILABLE,
        'train_pipeline': _TRAIN_PIPELINE_AVAILABLE,
        'predict_pipeline': _PREDICT_PIPELINE_AVAILABLE,
        'causal_analyzer': _CAUSAL_ANALYZER_AVAILABLE,
        'automl': _AUTOML_AVAILABLE,
        'model_registry': _MODEL_REGISTRY_AVAILABLE,
        'adversarial': _ADVERSARIAL_AVAILABLE,
        'adversarial_training': _ADVERSARIAL_TRAINING_AVAILABLE,
        'pytorch': False,
        'pytorch_geometric': False,
        'sklearn': False,
        'networkx': False,
        'xgboost_lib': False,
        'mlflow': False
    }

    try:
        import torch
        status['pytorch'] = True
    except ImportError:
        pass

    try:
        import torch_geometric
        status['pytorch_geometric'] = True
    except ImportError:
        pass

    try:
        import sklearn
        status['sklearn'] = True
    except ImportError:
        pass

    try:
        import networkx
        status['networkx'] = True
    except ImportError:
        pass

    try:
        import xgboost
        status['xgboost_lib'] = True
    except ImportError:
        pass

    try:
        import mlflow
        status['mlflow'] = True
    except ImportError:
        pass

    try:
        import optuna
        status['optuna'] = True
    except ImportError:
        status['optuna'] = False

    return status


__all__ = [
    # Neural Network
    'CorruptionNeuralNetwork',
    'CorruptionMLP',
    'create_neural_network',
    # Ensemble
    'CorruptionEnsemble',
    'MetaLearner',
    'SimpleWeightedEnsemble',
    'create_ensemble',
    'BaseModel',
    # Hybrid Anomaly Detection
    'HybridAnomalyDetector',
    'TenderAutoencoder',
    'AnomalyScore',
    'detect_anomalies',
    # Anomaly Explainer
    'AnomalyExplainer',
    'AnomalyExplanation',
    'FeatureAnomaly',
    'SimilarTender',
    'create_risk_report',
    'FEATURE_CATEGORIES',
    'FEATURE_DESCRIPTIONS',
    'RISK_PATTERNS',
    # Random Forest (Phase 2)
    'CorruptionRandomForest',
    'ModelMetrics',
    'FeatureImportance',
    'quick_train_random_forest',
    # XGBoost (Phase 2)
    'CorruptionXGBoost',
    'XGBModelMetrics',
    'XGBFeatureImportance',
    'quick_train_xgboost',
    # Training Data (Phase 2)
    'TrainingDataExtractor',
    'TrainingDataset',
    'extract_training_data',
    'save_training_dataset',
    'load_training_dataset',
    # Graph Builder
    'GraphBuilder',
    'BidderGraph',
    'GraphNode',
    'GraphEdge',
    'build_graph_from_db',
    'save_graph',
    'load_graph',
    # GNN Collusion Model
    'CollusionGNN',
    'CollusionGNNTrainer',
    'GNNConfig',
    'GraphFeatureExtractor',
    'build_collusion_gnn',
    'create_train_val_masks',
    'augment_node_features',
    # Collusion Detector
    'CollusionClusterDetector',
    'CollusionCluster',
    'CollusionEvidence',
    'detect_collusion_clusters',
    'export_clusters_to_json',
    # MLflow Tracking
    'CorruptionMLflowTracker',
    'TrainingConfig',
    'TrackingModelMetrics',
    'get_tracker',
    'calculate_metrics',
    # MLflow Context Managers and Decorators
    'mlflow_run',
    'cv_nested_run',
    'track_training',
    'track_cv_fold',
    # MLflow Helper Functions
    'setup_mlflow',
    'log_cv_summary',
    'log_hyperparameter_search',
    'log_dataset_info',
    'log_model_comparison',
    'get_or_create_experiment',
    # MLflow Configuration
    'MLflowConfig',
    'Environment',
    'ModelRegistryConfig',
    'HyperparameterConfig',
    'get_config',
    'get_local_config',
    'get_production_config',
    'quick_setup',
    'init_config',
    'get_global_config',
    # Training Pipeline
    'CorruptionTrainingPipeline',
    'TrainingData',
    'TrainingResult',
    # Prediction Pipeline
    'CorruptionPredictor',
    'PredictionResult',
    # Causal Inference (Phase 3.2)
    'CausalAnalyzer',
    # AutoML Pipeline (Phase 3.4)
    'AutoMLPipeline',
    # Model Registry (Phase 3.4)
    'ModelRegistry',
    # Adversarial Robustness (Phase 3.3)
    'AdversarialAnalyzer',
    'AdversarialTrainer',
    # Utilities
    'check_dependencies'
]

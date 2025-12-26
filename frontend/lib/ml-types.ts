/**
 * Type definitions for ML/Corruption Detection features
 */

// Risk Information
export interface RiskInfo {
  probability: number;
  level: 'critical' | 'high' | 'medium' | 'low' | 'minimal';
  color: string;
}

// Feature Contribution (SHAP/LIME)
export interface FeatureContribution {
  name: string;
  display_name: string;
  value: number;
  contribution: number;
  direction: 'increases_risk' | 'decreases_risk';
  importance_rank: number;
  description?: string;
  category?: string;
}

// Tender Explanation
export interface TenderExplanation {
  tender_id: string;
  risk: RiskInfo;
  method: 'shap' | 'lime' | 'combined' | 'flags';
  factors: FeatureContribution[];
  summary: string;
  recommendations?: string[];
  counterfactuals?: string[];
  model_fidelity?: number;
  cached: boolean;
  generated_at: string;
}

// Feature Importance (Global)
export interface FeatureImportance {
  name: string;
  importance: number;
  rank: number;
  category?: string;
  description?: string;
}

// Model Performance Metrics
export interface ModelPerformance {
  model_name: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number;
  average_precision?: number;
  optimal_threshold?: number;
  confusion_matrix?: number[][];
  cv_mean?: number;
  cv_std?: number;
  top_features: FeatureImportance[];
  trained_at: string;
}

// Model Comparison
export interface ModelInfo {
  name: string;
  type: string;
  accuracy: number;
  roc_auc?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  num_nodes?: number;
  num_edges?: number;
  training_samples?: number;
  trained_at: string;
}

export interface ModelComparison {
  models: ModelInfo[];
  best_model: string | null;
  total_models: number;
}

// Collusion Cluster
export interface ClusterEvidence {
  evidence_type: string;
  description: string;
  score: number;
  details?: Record<string, any>;
}

export interface CollusionClusterSummary {
  cluster_id: string;
  num_companies: number;
  confidence: number;
  risk_level: string;
  pattern_type: string;
  top_companies: string[];
}

export interface CollusionCluster extends CollusionClusterSummary {
  companies: string[];
  detection_method: string;
  evidence: ClusterEvidence[];
  common_tenders?: string[];
  common_institutions?: string[];
  metadata?: Record<string, any>;
}

// Company Risk
export interface CompanyRisk {
  company_name: string;
  prediction: number; // 0 = normal, 1 = suspicious
  probability: number;
  risk_level: string;
}

// Company Collusion Profile
export interface CompanyCollusionProfile {
  company_name: string;
  risk_prediction: CompanyRisk | null;
  clusters: {
    cluster_id: string;
    confidence: number;
    pattern_type: string;
    num_companies: number;
    other_companies: string[];
  }[];
  total_clusters: number;
  database_relationships: {
    related_company: string;
    relationship_type: string;
    confidence: number;
    source: string;
    evidence?: Record<string, any>;
  }[];
  is_suspicious: boolean;
}

// Network Visualization
export interface NetworkNode {
  id: string;
  name: string;
  type: 'company' | 'tender' | 'institution';
  risk_score?: number;
  risk_level?: string;
  metadata?: Record<string, any>;
}

export interface NetworkEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
  metadata?: Record<string, any>;
}

export interface NetworkData {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  cluster_id?: string;
  center_node?: string;
}

// Collusion Statistics
export interface CollusionStats {
  total_clusters: number;
  high_confidence_clusters: number;
  total_suspicious_companies: number;
  avg_cluster_size: number;
  largest_cluster_size: number;
  most_common_pattern: string;
  generated_at: string;
}

// Pattern Type Info
export interface PatternTypeInfo {
  pattern_type: string;
  count: number;
  avg_confidence: number;
  total_companies: number;
}

// Risk level colors for UI
export const RISK_COLORS: Record<string, string> = {
  critical: '#ef4444', // red-500
  high: '#f97316',     // orange-500
  medium: '#eab308',   // yellow-500
  low: '#3b82f6',      // blue-500
  minimal: '#22c55e',  // green-500
};

// Risk level labels in Macedonian
export const RISK_LABELS_MK: Record<string, string> = {
  critical: 'Критичен',
  high: 'Висок',
  medium: 'Среден',
  low: 'Низок',
  minimal: 'Минимален',
};

// Pattern type labels
export const PATTERN_LABELS: Record<string, string> = {
  bid_clustering: 'Групирање на понуди',
  clique_detection: 'Детекција на клика',
  community_detection: 'Детекција на заедница',
  price_manipulation: 'Манипулација со цени',
  repeat_bidding: 'Повторувачко понудување',
  unknown: 'Непознат образец',
};

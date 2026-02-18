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

// Corruption Risk Index (CRI) Flag Types - all 15 indicators
export const CRI_FLAG_TYPES = [
  'single_bidder',
  'repeat_winner',
  'price_anomaly',
  'bid_clustering',
  'short_deadline',
  'procedure_type',
  'identical_bids',
  'professional_loser',
  'contract_splitting',
  'short_decision',
  'strategic_disqualification',
  'contract_value_growth',
  'bid_rotation',
  'threshold_manipulation',
  'late_amendment',
] as const;

export type CRIFlagType = typeof CRI_FLAG_TYPES[number];

// CRI Flag type labels in Macedonian
export const CRI_FLAG_LABELS_MK: Record<string, string> = {
  single_bidder: 'Еден понудувач',
  repeat_winner: 'Повторлив победник',
  price_anomaly: 'Ценовна аномалија',
  bid_clustering: 'Кластер понуди',
  short_deadline: 'Краток рок',
  procedure_type: 'Ризична постапка',
  identical_bids: 'Идентични понуди',
  professional_loser: 'Покривач понудувач',
  contract_splitting: 'Делење договори',
  short_decision: 'Брза одлука',
  strategic_disqualification: 'Стратешка дисквалификација',
  contract_value_growth: 'Раст на вредност',
  bid_rotation: 'Ротација понуди',
  threshold_manipulation: 'Манипулација на праг',
  late_amendment: 'Доцен амандман',
};

// CRI Flag type labels in English (for admin pages)
export const CRI_FLAG_LABELS_EN: Record<string, string> = {
  single_bidder: 'Single Bidder',
  repeat_winner: 'Repeat Winner',
  price_anomaly: 'Price Anomaly',
  bid_clustering: 'Bid Clustering',
  short_deadline: 'Short Deadline',
  procedure_type: 'Risky Procedure',
  identical_bids: 'Identical Bids',
  professional_loser: 'Cover Bidder',
  contract_splitting: 'Contract Splitting',
  short_decision: 'Fast Decision',
  strategic_disqualification: 'Strategic Disqualification',
  contract_value_growth: 'Cost Overrun',
  bid_rotation: 'Bid Rotation',
  threshold_manipulation: 'Threshold Gaming',
  late_amendment: 'Late Amendment',
};

// CRI Flag type colors (Tailwind classes)
export const CRI_FLAG_COLORS: Record<string, string> = {
  single_bidder: '#f59e0b',    // amber-500
  repeat_winner: '#ef4444',     // red-500
  price_anomaly: '#a855f7',     // purple-500
  bid_clustering: '#6366f1',    // indigo-500
  short_deadline: '#ca8a04',    // yellow-600
  procedure_type: '#64748b',    // slate-500
  identical_bids: '#e11d48',    // rose-600
  professional_loser: '#71717a', // zinc-500
  contract_splitting: '#059669', // emerald-600
  short_decision: '#06b6d4',    // cyan-500
  strategic_disqualification: '#dc2626', // red-600
  contract_value_growth: '#ea580c', // orange-600
  bid_rotation: '#8b5cf6',      // violet-500
  threshold_manipulation: '#14b8a6', // teal-500
  late_amendment: '#d97706',    // amber-600
};

// CRI Score utility
export function getCRILevel(score: number): { level: string; label_mk: string; label_en: string; color: string } {
  if (score >= 80) return { level: 'critical', label_mk: 'Критичен', label_en: 'Critical', color: '#ef4444' };
  if (score >= 60) return { level: 'high', label_mk: 'Висок', label_en: 'High', color: '#f97316' };
  if (score >= 40) return { level: 'medium', label_mk: 'Среден', label_en: 'Medium', color: '#eab308' };
  if (score >= 20) return { level: 'low', label_mk: 'Низок', label_en: 'Low', color: '#3b82f6' };
  return { level: 'minimal', label_mk: 'Минимален', label_en: 'Minimal', color: '#22c55e' };
}

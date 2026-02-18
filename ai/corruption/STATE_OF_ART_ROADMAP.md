# NabavkiData Corruption Detection System
# State-of-the-Art Technical Roadmap

**Document Version:** 2.0
**Last Updated:** February 2026
**Classification:** Internal Technical Strategy
**Authors:** NabavkiData Engineering Team
**Contact:** team@nabavkidata.com

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#current-state-assessment)
3. [Phase 1: Integration & Calibration (Month 1-2)](#phase-1-integration--calibration-month-1-2)
4. [Phase 2: NLP & Document Analysis (Month 3-4)](#phase-2-nlp--document-analysis-month-3-4)
5. [Phase 3: Advanced ML (Month 5-6)](#phase-3-advanced-ml-month-5-6)
6. [Phase 4: Network Intelligence (Month 7-8)](#phase-4-network-intelligence-month-7-8)
7. [Phase 5: Cross-Country & Scale (Month 9-12)](#phase-5-cross-country--scale-month-9-12)
8. [Risk Assessment & Mitigation](#risk-assessment--mitigation)
9. [Resource Requirements Summary](#resource-requirements-summary)
10. [Academic & Institutional References](#academic--institutional-references)
11. [Appendix A: DOZORRO Indicator Coverage Map](#appendix-a-dozorro-indicator-coverage-map)
12. [Appendix B: Glossary](#appendix-b-glossary)

---

## Executive Summary

NabavkiData operates a procurement fraud detection system for North Macedonia's public procurement market (e-nabavki.gov.mk), covering approximately 80,000+ tenders across 15+ years of historical data. The system currently achieves a **B+ maturity rating** -- strong statistical foundations and a working ML pipeline, but not yet at the frontier of what modern research enables.

This roadmap charts a 12-month path from our current rule-based + ensemble ML architecture to a fully integrated, multi-modal, network-aware detection platform that would place NabavkiData among the top procurement integrity systems globally -- alongside DOZORRO (Ukraine), OpenTender (EU), and the World Bank's Integrity Vice Presidency tooling.

**Key metrics targeted by end of roadmap:**

| Metric | Current | Phase 2 Target | Phase 5 Target |
|--------|---------|----------------|----------------|
| DOZORRO indicator coverage | ~13/40 core | 25/40 | 38/40 |
| Rule-based detectors | 15 | 15 + NLP-augmented | 20+ |
| ML features | 112 | 150+ (with NLP) | 200+ (with network) |
| Explainability | Feature importance | Real SHAP | SHAP + counterfactual |
| GNN collusion | Trained, offline | Live API | Real-time streaming |
| False positive rate | Unknown (no ground truth) | < 30% (estimated) | < 15% (calibrated) |
| Countries covered | 1 (MK) | 1 | 4 (MK, XK, AL, RS) |

**Total estimated investment:** 52-66 person-weeks across all phases.

---

## Current State Assessment

### Overall Grade: B+

The system demonstrates strong engineering in several areas while having identifiable gaps that this roadmap addresses. Below is an honest evaluation.

### Architecture Overview

```
                    +---------------------------+
                    |     Frontend (Next.js)     |
                    |  Risk Dashboard, Profiles  |
                    +------------+--------------+
                                 |
                    +------------+--------------+
                    |     FastAPI Backend        |
                    | /api/corruption/*          |
                    | /api/corruption/collusion  |
                    | /api/corruption/explain    |
                    +---+--------+----------+---+
                        |        |          |
              +---------+  +----+----+  +---+--------+
              |  15 Rule |  | ML      |  | GNN        |
              |  Based   |  | Ensemble|  | Collusion  |
              | Detectors|  | RF+XGB  |  | (OFFLINE)  |
              +----+-----+  +----+----+  +-----+------+
                   |              |              |
              +----+--------------+--------------+-----+
              |            PostgreSQL (RDS)             |
              | tenders | tender_bidders | documents    |
              | corruption_flags | ml_predictions       |
              +--------------------------------------------+
```

### What Works Well

| Component | Assessment | Details |
|-----------|-----------|---------|
| **15 Rule-Based Detectors** | Strong | Uses Z-scores, HHI, coefficient of variation, data-driven percentiles. Statistically rigorous implementations. |
| **CRI Scoring** | Solid | Weighted average across 15 flags with multi-indicator bonus. Weights manually tuned by domain experts. |
| **112 ML Features** | Comprehensive | 7 categories: competition (14), price (30), timing (16), relationship (19), procedural (16), document (9), historical (9). Real database queries, not synthetic data. |
| **ML Ensemble** | Good | Random Forest + XGBoost with stacking meta-learner (Logistic Regression). Out-of-fold predictions prevent data leakage. Probability calibration via isotonic regression. |
| **GNN Architecture** | Promising | GraphSAGE(64) + GAT(32, 4 heads) for collusion detection. Supports node classification, link prediction, and embedding extraction. Uses LayerNorm, gradient clipping, early stopping. |
| **Feature Extraction Pipeline** | Production-quality | Async/await with asyncpg, batch processing, ordered feature vectors, proper NULL handling. |
| **Graph Builder** | Functional | Builds bipartite (bidder-tender) and unipartite (co-bidding) graphs from real DB data. NetworkX integration for centrality features. |
| **Bilingual Search** | Excellent | Latin-to-Cyrillic transliteration for Macedonian text search. Essential for this market. |
| **False Positive Review** | Exists | Admin workflow for reviewing flagged tenders. Audit logged. |

### What Is Placeholder or Incomplete

| Component | Issue | Impact |
|-----------|-------|--------|
| **GNN Not in Live API** | The CollusionGNN model is trained but results are served from static JSON files (`collusion_clusters.json`, `node_predictions.json`). No real-time inference. | Collusion detection is stale between retraining runs. |
| **Explainability: No Real SHAP** | The `/api/corruption/explain` endpoint returns feature importance rankings, not actual SHAP values. Feature contributions are approximated, not computed via KernelSHAP or TreeSHAP. | Cannot tell users *why* a specific tender was flagged with mathematical precision. |
| **DOZORRO Relationship Indicators: Stubs** | 6 of 10 relationship indicators and all 10 procedural indicators are stubs (return placeholder values). Marked as "implemented" but functionally no-ops. | Overstates indicator coverage. True coverage is closer to 13/40 core DOZORRO indicators with full logic. |
| **No Confidence Intervals on CRI** | CRI outputs a single number (0-100). No uncertainty quantification, no confidence bands. | Users cannot distinguish "definitely corrupt" from "might be corrupt." |
| **No Labeled Ground Truth** | No verified corruption cases in the database. ML models are trained on proxy labels (rule-based flags), not adjudicated outcomes. | Cannot measure true precision/recall. Circular dependency risk. |
| **No NLP on Document Content** | 32K+ documents extracted but text is only used for search (RAG). No analysis for specification rigging, copy-paste detection, or NER. | Missing an entire class of DOZORRO indicators (R005-R010). |
| **No Temporal Models** | All models treat each tender independently. No sequence modeling of bidder behavior over time. | Cannot detect escalating patterns or regime changes. |
| **No Ownership/Beneficial Network** | GNN uses co-bidding graph only. No company-to-person-to-company ownership links. | Cannot detect shell company networks or hidden beneficial owners. |

### DOZORRO Coverage Analysis

The DOZORRO system (developed by Transparency International Ukraine for ProZorro) defines ~40 core indicators across competition, pricing, timing, relationships, and procedures. Our honest mapping:

| DOZORRO Category | Total Indicators | Fully Implemented | Partial/Stub | Not Started |
|-----------------|-----------------|-------------------|--------------|-------------|
| Competition (C001-C010) | 10 | 7 | 3 | 0 |
| Pricing (P001-P010) | 10 | 6 | 2 | 2 |
| Timing (T001-T008) | 8 | 5 | 2 | 1 |
| Relationship (R001-R007) | 7 | 1 | 4 | 2 |
| Procedural (PR001-PR005) | 5 | 0 | 3 | 2 |
| **Total** | **40** | **19** | **14** | **7** |

**Effective coverage: ~13/40** (counting only indicators with full statistical logic, excluding stubs that return default values).

### Comparison with Leading Systems

| Capability | NabavkiData (Current) | DOZORRO (Ukraine) | OpenTender (EU) | Red Flags (World Bank) |
|------------|----------------------|-------------------|-----------------|----------------------|
| Rule-based indicators | 15 | 40+ | 30+ | 25+ |
| ML ensemble | Yes (RF + XGB) | Yes (gradient boosting) | Yes (various) | No (rules only) |
| GNN/network analysis | Trained, not live | No | Research only | No |
| NLP on documents | No | Yes (Ukrainian NLP) | Partial | No |
| SHAP explainability | No (placeholder) | Yes | Partial | N/A |
| Labeled ground truth | No | Yes (~5,000 cases) | Partial | No |
| Cross-country | No | No (Ukraine only) | Yes (28 EU countries) | Yes (50+ countries) |
| Real-time detection | No (batch) | Near real-time | Batch | Batch |
| Beneficial ownership | No | Partial | Yes (via OpenOwnership) | Yes |

---

## Phase 1: Integration & Calibration (Month 1-2)

### Objective
Make the existing ML components production-grade by connecting the trained GNN model to live API endpoints, replacing placeholder explainability with real SHAP values, and establishing feedback loops for continuous improvement.

### 1.1 GNN Collusion Model: Live API Integration

**Current State:** The `CollusionGNN` model is trained and serialized to `.pt` checkpoint files. The `/api/corruption/collusion/*` endpoints read from static JSON files that were generated during the last training run.

**Target State:** Load the trained GNN model at API startup, perform inference on-demand when collusion endpoints are called, and cache results with configurable TTL.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| `GNNInferenceService` class | Singleton service that loads the PyTorch model at startup, manages GPU/CPU device selection, and exposes `predict_node_risk()` and `predict_link_risk()` methods. | 1.5 weeks |
| Graph materialization cron | Scheduled job (daily at 4 AM UTC, before corruption views refresh at 5 AM) that rebuilds the co-bidding graph from `tender_bidders` and caches it in Redis or a PostgreSQL `JSONB` column. | 1 week |
| API endpoint refactor | Modify `/api/corruption/collusion/clusters`, `/api/corruption/collusion/company/{name}`, and `/api/corruption/collusion/network` to call `GNNInferenceService` instead of reading JSON files. Add `?force_refresh=true` parameter for admin use. | 1 week |
| Fallback mechanism | If PyTorch/PyG is not available on the server (3.8GB RAM constraint), fall back to pre-computed JSON files. Log a warning and expose a `/api/corruption/collusion/status` health endpoint. | 0.5 weeks |
| Performance optimization | Batch inference for top-N queries. Model quantization (INT8) to reduce memory footprint from ~500MB to ~125MB. Consider ONNX export for faster CPU inference. | 1 week |

**Memory constraint note:** The EC2 instance has 3.8GB RAM. A full PyTorch Geometric runtime may require 1-2GB. Options:
1. **ONNX Runtime** (recommended): Export GNN to ONNX format, run inference without full PyTorch. ~200MB memory.
2. **Separate inference container**: Run GNN inference in a dedicated lightweight container, communicate via HTTP.
3. **Pre-compute on schedule**: Keep the current approach but run inference hourly instead of at training time.

#### Required Data Sources
- `tender_bidders` table (existing)
- `company_relationships` table (existing, needs enrichment)
- Pre-trained model checkpoint: `ai/corruption/ml_models/models/*.pt`

#### Expected Impact
- Collusion detection moves from stale (days-old) to fresh (hours-old at worst)
- New tenders are analyzed for collusion within 24 hours of scraping
- API response latency: < 200ms for cached, < 2s for fresh inference

#### Dependencies
- None (uses existing trained model)

---

### 1.2 Real SHAP Values for Production Explainability

**Current State:** The `/api/corruption/explain/{tender_id}` endpoint returns a list of `FeatureContribution` objects with `contribution` values that are derived from global feature importance rankings, not from actual SHAP (SHapley Additive exPlanations) computations for the specific tender.

**Target State:** Compute per-tender SHAP values using TreeSHAP (for RF and XGBoost) and return genuine feature-level attributions that sum to the model's prediction.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| SHAP computation module | `ai/corruption/ml_models/shap_explainer.py` -- wraps `shap.TreeExplainer` for RF and XGBoost. Caches background dataset (100-sample summary) for KernelSHAP fallback. | 1 week |
| Per-tender SHAP endpoint | Modify `/api/corruption/explain/{tender_id}` to call `shap_explainer.explain(tender_id)`, returning real SHAP values. Cache results in `ml_shap_cache` table (tender_id, model_name, shap_values JSONB, computed_at). | 1 week |
| SHAP waterfall visualization data | Return SHAP values in a format consumable by the frontend for waterfall plots: base value, feature contributions (positive/negative), final prediction. | 0.5 weeks |
| Batch SHAP pre-computation | Nightly cron job that pre-computes SHAP values for all newly flagged tenders (typically 50-200/day). Stores in cache table. | 0.5 weeks |
| Counterfactual explanations | "What would need to change for this tender to be low-risk?" -- generate counterfactual feature vectors using DiCE (Diverse Counterfactual Explanations) library. | 1 week |

#### Implementation Notes

```python
# TreeSHAP for XGBoost (fast, exact)
import shap
explainer = shap.TreeExplainer(xgb_model)
shap_values = explainer.shap_values(feature_vector)  # O(TLD) complexity

# KernelSHAP fallback for ensemble meta-learner
background = shap.sample(X_train, 100)
kernel_explainer = shap.KernelExplainer(ensemble.predict_proba, background)
shap_values = kernel_explainer.shap_values(feature_vector)
```

**Reference:** Lundberg & Lee (2017). "A Unified Approach to Interpreting Model Predictions." *NeurIPS*.

#### Expected Impact
- Explainability moves from "this feature is generally important" to "this feature pushed *this tender's* risk score up by 0.12"
- Enables regulatory defensibility: explanations are mathematically grounded
- Counterfactuals enable actionable recommendations for procurement officers

---

### 1.3 CRI Weight Calibration via Active Learning

**Current State:** CRI weights are manually set constants in `backend/api/corruption.py`:

```python
CRI_WEIGHTS = {
    'single_bidder': 1.0,
    'procedure_type': 1.2,
    'contract_splitting': 1.3,
    'identical_bids': 1.5,
    ...
}
```

These were set by domain expertise but have never been validated against outcomes.

**Target State:** Continuously adjust CRI weights based on analyst feedback from the false positive review workflow.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Feedback data model | Extend `corruption_flag_reviews` table with `analyst_verdict` (confirmed_fraud, likely_fraud, uncertain, false_positive, not_reviewed), `confidence` (1-5), and `evidence_notes`. | 0.5 weeks |
| Weight learning algorithm | Implement Bayesian logistic regression over review verdicts to learn optimal flag weights. Use PyMC or a lightweight Bayesian approach. Prior: current weights. Posterior: updated weights after each batch of reviews. | 1.5 weeks |
| Active learning sampler | Instead of random tenders for review, select the most informative ones: (a) tenders near the decision boundary (CRI ~ 50), (b) tenders where rule-based and ML disagree, (c) tenders with novel flag combinations. | 1 week |
| Weight update pipeline | Weekly cron that recomputes CRI weights from accumulated reviews. Logs weight changes. Requires minimum 50 reviews before first update. Caps weight change at +/-20% per cycle to prevent instability. | 0.5 weeks |
| A/B testing framework | Serve old weights to 50% of API calls, new weights to 50%. Compare analyst agreement rates. | 0.5 weeks |

#### Required Data Sources
- `corruption_flag_reviews` table (existing, needs schema extension)
- Analyst review data (requires human labeling effort: target 200 reviews in Month 1-2)

#### Expected Impact
- CRI weights converge toward empirically validated values
- Estimated 15-25% reduction in false positive rate within 3 months of feedback accumulation
- Enables the system to adapt to Macedonian procurement patterns specifically, rather than relying on generic assumptions

**Reference:** Settles, B. (2012). "Active Learning." *Synthesis Lectures on AI and ML*. Morgan & Claypool.

---

### 1.4 Confidence Intervals and Uncertainty Quantification

**Current State:** CRI score is a point estimate (e.g., "Risk: 73/100"). No indication of how confident the system is.

**Target State:** Every CRI score accompanied by a 90% confidence interval and an epistemic uncertainty score.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Bootstrap CRI confidence intervals | Compute CRI 1,000 times with bootstrapped flag scores (varying within their own confidence ranges). Report 5th and 95th percentile as the 90% CI. | 0.5 weeks |
| MC Dropout for ensemble uncertainty | Add Monte Carlo Dropout to the Neural Network model in the ensemble. Run 50 forward passes with dropout enabled at inference time. Variance of outputs = epistemic uncertainty. | 1 week |
| Prediction interval API response | Modify `/api/corruption/risk/{tender_id}` to return `{ score: 73, confidence_interval: [61, 82], uncertainty: "medium", data_completeness: 0.85 }`. | 0.5 weeks |
| Data completeness score | Measure what fraction of the 112 features have real (non-default) values for this tender. Missing data = higher uncertainty. | 0.5 weeks |

#### Expected Impact
- Users can distinguish "definitely risky (CI: 85-95)" from "uncertain (CI: 40-90)"
- Prevents overconfidence in sparse-data situations (old tenders, missing bidder data)
- Aligns with OECD recommendations on uncertainty reporting in public integrity tools

**Reference:** Gal, Y. & Ghahramani, Z. (2016). "Dropout as a Bayesian Approximation." *ICML*.

---

### Phase 1 Summary

| Deliverable | Effort (person-weeks) | Priority |
|-------------|----------------------|----------|
| GNN live API integration | 5.0 | P0 - Critical |
| Real SHAP values | 4.0 | P0 - Critical |
| CRI weight calibration | 4.0 | P1 - High |
| Confidence intervals | 2.5 | P1 - High |
| **Phase 1 Total** | **15.5** | |

---

## Phase 2: NLP & Document Analysis (Month 3-4)

### Objective
Unlock the 32,000+ extracted tender documents for corruption detection by applying natural language processing techniques to detect specification rigging, entity extraction, cross-tender plagiarism, and document anomalies. This phase addresses DOZORRO indicators R005-R010 (specification manipulation) which currently have zero coverage.

### 2.1 Specification Text Analysis for Rigging Patterns

**Current State:** Tender specifications are extracted from PDFs and stored in `documents.content_text`. This text is indexed for RAG search but never analyzed for corruption patterns.

**Target State:** Detect specification rigging patterns including tailored requirements, brand-name specifications, copy-paste from previous winning bids, and unnecessarily restrictive qualification criteria.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Specification rigging classifier | Fine-tune a multilingual BERT model (or Gemini API) on a labeled dataset of rigged vs. clean specifications. Labels bootstrapped from tenders already flagged by rule-based detectors. Binary classification + confidence score. | 2 weeks |
| Brand-name detector | Regex + NER pipeline that identifies product brand names, model numbers, and proprietary references in specifications. Cross-reference against known product databases. Flag when specification mentions only one brand. | 1 week |
| Restrictive qualification extractor | Extract qualification requirements (turnover thresholds, experience years, specific certifications) from specification text. Flag when requirements exceed typical values for the CPV category by > 2 standard deviations. | 1.5 weeks |
| Specification complexity score | Compute readability metrics (Flesch-Kincaid adapted for Macedonian/Cyrillic), vocabulary richness, and technical density. Unusually simple or unusually complex specifications may indicate rigging. | 0.5 weeks |

#### Required Data Sources
- `documents` table (`content_text` column where `extraction_status = 'success'`)
- CPV code to category mapping (existing)
- Manually labeled rigged specifications: target 200 examples (can be bootstrapped from flagged tenders)

#### Expected Impact
- Enables detection of specification tailoring, the most common form of procurement fraud according to OECD (2016)
- Adds coverage for DOZORRO indicators R005 (specification manipulation), R006 (brand-name specifications), R007 (restrictive requirements)
- Estimated 10-15% increase in overall detection rate for high-value tenders where specifications are available

#### Macedonian Language Considerations
- Primary specification language: Macedonian (Cyrillic)
- Some tenders include Albanian-language specifications
- Strategy: Use multilingual models (mBERT, XLM-R) or Gemini API which handles Macedonian natively
- Transliteration pipeline (existing `latin_to_cyrillic`) will be extended for NLP preprocessing

---

### 2.2 Named Entity Recognition (NER)

**Current State:** Entity extraction from documents is limited to structured fields scraped from the procurement portal (company names, institution names). No NER on document body text.

**Target State:** Extract people, organizations, locations, monetary amounts, dates, and legal references from tender document text. Build entity co-occurrence networks.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Macedonian NER model | Fine-tune SpaCy or Stanza NER on Macedonian text. Entity types: PERSON, ORG, MONEY, DATE, GPE, LEGAL_REF. Training data: 500 manually annotated sentences from tender documents + bootstrapping from structured fields. | 2 weeks |
| Entity resolution pipeline | Deduplicate extracted entities across documents (e.g., "Alkaloid AD Skopje" = "АЛКАЛОИД АД" = "Alkaloid"). Use fuzzy matching + tax ID resolution. | 1 week |
| Entity co-occurrence database | Store extracted entity pairs (person, organization) in a new `entity_mentions` table. Enable queries like "which people are mentioned in tenders won by Company X?" | 1 week |
| Conflict-of-interest detector | Cross-reference extracted person names with public official registries and company ownership records. Flag when a person appears in both the buyer's decision committee and the winner's corporate records. | 1.5 weeks |

#### Required Data Sources
- `documents.content_text` (existing, 32K+ documents)
- Central Registry of North Macedonia (company records, if API available)
- Public official declarations of interest (if published)

#### Expected Impact
- Enables detection of undisclosed conflicts of interest (DOZORRO R003)
- Builds the foundation for beneficial ownership analysis (Phase 4)
- Estimated 5-10% improvement in relationship-based detection by discovering hidden entity connections

**Reference:** Honnibal, M. & Montani, I. (2017). "spaCy 2: Natural language understanding with Bloom embeddings, convolutional neural networks and incremental parsing." (Applied to procurement: Fazekas & Kocsis, 2020, "Uncovering High-Level Corruption," *Government Transparency Institute*.)

---

### 2.3 Cross-Tender Specification Similarity Analysis

**Current State:** No comparison of specification text across tenders.

**Target State:** Detect when specifications from different tenders (especially from the same institution) are copy-pasted or suspiciously similar, potentially indicating that specifications were written by or for a specific supplier.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Specification embedding pipeline | Generate embeddings for each specification document using the existing Gemini embedding pipeline. Store in `specification_embeddings` table. | 1 week |
| Similarity search index | Build HNSW vector index (pgvector or FAISS) over specification embeddings. For each new tender, find top-5 most similar past specifications. | 0.5 weeks |
| Copy-paste detector | For high-similarity pairs (cosine > 0.92), perform detailed text diff to identify copied sections. Flag when > 60% of specification text is identical to a previous tender won by the same company. | 1 week |
| Cross-institution similarity alerts | Flag when specifications from different institutions are nearly identical (cosine > 0.95), suggesting the same entity authored both. This can indicate supplier-authored specifications. | 0.5 weeks |

#### Expected Impact
- Detects specification rigging via "copy-paste" from supplier proposals
- Addresses DOZORRO R008 (identical specifications across tenders)
- Particularly effective for detecting cartels that provide pre-written specifications to corrupt procurement officers

---

### 2.4 Document Anomaly Detection

**Current State:** Document features are limited to count-based metrics (number of documents, extraction success rate, content length).

**Target State:** Detect anomalous document characteristics that may indicate manipulation.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Document structure analyzer | Parse PDF metadata (creation date, modification date, author, software used). Flag documents created or modified after the tender deadline. | 1 week |
| Formatting anomaly detector | Detect unusual formatting: hidden text, white-on-white text, extremely small font sizes, watermarked content. These can indicate document tampering. | 0.5 weeks |
| Completeness checker | Verify that required document types are present (specification, evaluation criteria, financial bid form). Flag tenders missing expected documents for their procedure type. | 0.5 weeks |
| Bid document timing analysis | Compare creation timestamps of bid documents from different bidders. Flag when multiple bid PDFs have creation dates within minutes of each other (indicating coordination). | 0.5 weeks |

#### Expected Impact
- Adds a new detection dimension not covered by any current indicator
- Document-level anomalies are hard for fraudsters to avoid if they are producing coordinated fake bids
- Estimated 3-5% incremental detection improvement

---

### Phase 2 Summary

| Deliverable | Effort (person-weeks) | Priority |
|-------------|----------------------|----------|
| Specification rigging analysis | 5.0 | P0 - Critical |
| Named Entity Recognition | 5.5 | P1 - High |
| Cross-tender similarity | 3.0 | P1 - High |
| Document anomaly detection | 2.5 | P2 - Medium |
| **Phase 2 Total** | **16.0** | |

---

## Phase 3: Advanced ML (Month 5-6)

### Objective
Upgrade the ML backbone from static ensemble classifiers to temporal-aware, causally-grounded, and adversarially-robust models. This phase represents the transition from "good ML practice" to "research-grade detection."

### 3.1 Temporal Sequence Models

**Current State:** Each tender is scored independently. The model has no concept of "this bidder's behavior has changed over the last 6 months" or "this institution's procurement pattern is escalating."

**Target State:** Deploy LSTM or Transformer-based models that process sequences of tenders per institution or per company over time, detecting behavioral shifts and escalating patterns.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Sequence data pipeline | For each institution and company, construct ordered sequences of tender feature vectors (sorted by date). Window size: 20 tenders. Stride: 1. | 1 week |
| Temporal Transformer model | Implement a Transformer encoder (4 layers, 8 heads, d_model=128) that processes tender sequences and outputs a risk trajectory. Use positional encoding based on actual dates (not positions) for irregular time series. | 2 weeks |
| Behavioral change-point detection | Apply CUSUM or Bayesian Online Change Point Detection on the temporal risk trajectory. Alert when a company's or institution's risk profile significantly shifts. | 1 week |
| Time-aware features | Add 15 temporal features: rolling average CRI (30/90/365 days), trend slope, volatility, seasonality component, time since last flag, flag acceleration. | 0.5 weeks |

#### Required Data Sources
- `tenders` table (ordered by `publication_date`)
- `corruption_flags` table (historical flags)
- `tender_bidders` table (historical participation)

#### Expected Impact
- Enables detection of "regime changes" -- e.g., a clean institution that suddenly starts showing corruption patterns after a personnel change
- Catches gradual escalation that point-in-time models miss
- Estimated 8-12% improvement in early detection (flagging tenders before patterns become obvious)

**Reference:** Vaswani et al. (2017). "Attention Is All You Need." *NeurIPS*. Applied to procurement: Wachs et al. (2021). "Corruption Risk in Contracting Markets." *Science Advances*.

---

### 3.2 Causal Inference for Feature Importance

**Current State:** Feature importance is correlational (SHAP values from Phase 1). We know "single_bidder is associated with higher risk" but not "restricting competition *causes* higher corruption probability."

**Target State:** Estimate causal effects of key procurement design choices (deadline length, procedure type, publication timing) on corruption risk using causal forests and instrumental variables.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Causal forest model | Implement Generalized Random Forests (GRF) using the `econml` library. Treatment: procurement design choice (e.g., short deadline). Outcome: corruption flag probability. Confounders: institution size, tender value, CPV category. | 2 weeks |
| Instrumental variable analysis | Use regulatory threshold changes as natural experiments (e.g., changes in the mandatory competitive threshold amount). Estimate the causal effect of procedure type on corruption. | 1 week |
| Policy recommendation engine | Based on causal estimates, generate actionable recommendations: "If this institution extended deadlines by 5 days, we estimate corruption risk would decrease by 15% (+/- 8%)." | 1 week |
| Causal feature importance report | Generate a report comparing correlational (SHAP) vs. causal (GRF) feature importance. Identify features that are correlated with corruption but not causal (confounders) vs. genuinely causal factors. | 0.5 weeks |

#### Expected Impact
- Transforms the system from "detection" to "prevention" -- we can recommend policy changes
- Distinguishes spurious correlations from genuine risk factors
- Highly valuable for government stakeholders and OECD reporting

**Reference:** Athey & Imbens (2019). "Machine Learning Methods That Economists Should Know About." *Annual Review of Economics*. Wager & Athey (2018). "Estimation and Inference of Heterogeneous Treatment Effects using Random Forests." *JASA*.

---

### 3.3 Adversarial Robustness

**Current State:** No adversarial testing. Models may be vulnerable to manipulation by sophisticated actors who understand the feature space.

**Target State:** Harden models against adversarial manipulation where corrupt actors adjust observable features to avoid detection.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Adversarial attack simulation | Generate adversarial examples using FGSM and PGD attacks adapted for tabular data. Identify features that, when perturbed by small amounts, cause the largest change in risk score. | 1 week |
| Adversarial training | Retrain ensemble models with adversarial examples injected into the training set (adversarial augmentation). This teaches models to be robust to small feature perturbations. | 1 week |
| Feature sensitivity analysis | For each tender, compute the minimum perturbation required to flip the prediction. Alert when a tender is "close to the boundary" -- small changes could make it appear clean. | 0.5 weeks |
| Robustness certification | Implement randomized smoothing to provide certified robustness bounds: "This tender's risk classification is guaranteed stable under perturbations of magnitude epsilon." | 0.5 weeks |

#### Expected Impact
- Prevents sophisticated actors from gaming the system by, e.g., adding one more dummy bidder or slightly adjusting bid amounts
- Essential for deployment in adversarial environments (which procurement fraud inherently is)
- Estimated 5-8% reduction in evasion rate by sophisticated actors

**Reference:** Goodfellow et al. (2015). "Explaining and Harnessing Adversarial Examples." *ICLR*. Ballet et al. (2019). "Imperceptible Adversarial Attacks on Tabular Data." *NeurIPS Workshop*.

---

### 3.4 AutoML and Model Selection

**Current State:** Hyperparameters for RF and XGBoost are manually tuned. Model selection is manual.

**Target State:** Automated hyperparameter optimization and model selection pipeline.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Optuna integration | Implement Bayesian hyperparameter optimization using Optuna. Search space: RF (n_estimators, max_depth, min_samples_split, class_weight), XGBoost (n_estimators, max_depth, learning_rate, subsample, colsample_bytree, scale_pos_weight). | 1 week |
| Model comparison framework | Standardized evaluation pipeline: 5-fold stratified CV, metrics (AUC-ROC, precision@k, recall@k, F1), statistical significance tests (paired t-test on fold scores). | 0.5 weeks |
| Automated retraining pipeline | Monthly retraining trigger: (a) new labeled data exceeds threshold, (b) data drift detected (PSI > 0.1 on key features), (c) manual trigger via admin API. | 1 week |
| Model registry | Track model versions, training data hashes, hyperparameters, and performance metrics. Rollback capability if new model underperforms. | 0.5 weeks |

#### Expected Impact
- Removes human bottleneck from model tuning
- Ensures models stay current as data distribution shifts over time
- Estimated 3-5% improvement in model performance from better hyperparameters

---

### 3.5 Conformal Prediction for Risk Score Calibration

**Current State:** CRI scores are on a 0-100 scale but the relationship between score and actual corruption probability is unknown.

**Target State:** Calibrate risk scores so that "CRI = 80" means "80% probability of actual corruption" with statistical guarantees.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Conformal prediction wrapper | Implement split conformal prediction: hold out a calibration set, compute nonconformity scores, and convert model outputs to prediction sets with coverage guarantees. | 1 week |
| Adaptive conformal prediction | Extend to Adaptive Conformal Inference (ACI) that adjusts prediction intervals based on local data density. Tenders in sparse feature regions get wider intervals. | 0.5 weeks |
| Calibration monitoring | Track calibration over time using reliability diagrams (Platt scaling). Alert when calibration degrades beyond a threshold. | 0.5 weeks |

#### Expected Impact
- Statistically guaranteed coverage: "90% of truly corrupt tenders fall within our flagged set"
- Enables principled threshold setting for alerts
- Essential for regulatory acceptance

**Reference:** Vovk et al. (2005). "Algorithmic Learning in a Random World." Springer. Romano et al. (2019). "Conformalized Quantile Regression." *NeurIPS*.

---

### Phase 3 Summary

| Deliverable | Effort (person-weeks) | Priority |
|-------------|----------------------|----------|
| Temporal sequence models | 4.5 | P0 - Critical |
| Causal inference | 4.5 | P1 - High |
| Adversarial robustness | 3.0 | P2 - Medium |
| AutoML & model selection | 3.0 | P1 - High |
| Conformal prediction | 2.0 | P2 - Medium |
| **Phase 3 Total** | **17.0** | |

---

## Phase 4: Network Intelligence (Month 7-8)

### Objective
Evolve the GNN collusion detection from a static, batch-processed system into a real-time, multi-relational network intelligence platform that maps beneficial ownership, tracks temporal evolution, and detects cross-institutional cartel operations.

### 4.1 Real-Time GNN Updates

**Current State:** The GNN is retrained periodically (manually triggered). New tenders between retraining cycles are not reflected in collusion scores.

**Target State:** Incrementally update the graph and re-run localized GNN inference when new bids arrive.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Incremental graph update service | When a new tender is scraped (via the 3-hourly cron), add new nodes and edges to the cached graph. Update only the affected subgraph (k-hop neighborhood of new nodes). | 1.5 weeks |
| Localized GNN inference | Re-run forward pass only on the affected subgraph (using NeighborLoader from PyTorch Geometric). Avoid full-graph re-inference. | 1 week |
| Change detection alerts | When a company's collusion risk score changes by > 15 points after a graph update, trigger an alert. Store alert in `collusion_alerts` table. | 0.5 weeks |
| Graph versioning | Store graph snapshots (weekly) for temporal analysis. Enable "what did the collusion network look like 6 months ago?" queries. | 0.5 weeks |

#### Expected Impact
- Collusion detection latency drops from days to hours
- New cartels can be detected within 1-2 tender cycles instead of waiting for monthly retraining

---

### 4.2 Beneficial Ownership Network Analysis

**Current State:** The co-bidding graph connects companies that bid on the same tenders. No company-to-person-to-company ownership links.

**Target State:** Build a multi-relational knowledge graph: Company -[owned_by]-> Person -[owns]-> Company, Company -[shares_address_with]-> Company, Company -[shares_director_with]-> Company.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Ownership data integration | Import company ownership data from the Central Registry of North Macedonia (CRRNM). Parse director names, shareholders, registered addresses. | 2 weeks |
| Multi-relational graph schema | Extend the graph to support heterogeneous edges: `co_bid`, `owns`, `directs`, `shares_address`, `shares_bank_account`, `subcontracts_to`. Use PyTorch Geometric `HeteroData`. | 1.5 weeks |
| Shell company detector | Flag companies with: (a) registration date < 6 months before first tender, (b) no employees, (c) registered at a known "mailbox" address shared by 5+ companies, (d) director who directs 10+ other companies. | 1 week |
| Hidden relationship discovery | Use GNN link prediction to identify likely but undisclosed relationships between companies. Predict missing `owns` and `directs` edges. | 1 week |

#### Required Data Sources
- Central Registry of North Macedonia (CRRNM) -- company records, directors, shareholders
- CompanyWall data (already partially scraped via `companywall_spider.py`)
- Tax authority public records (if available)
- Public official asset declarations

#### Expected Impact
- Detects shell company networks used for bid rigging
- Identifies undisclosed conflicts of interest between procurement officers and bidders
- Addresses DOZORRO R001 (beneficial ownership) and R002 (conflict of interest)
- This is the single highest-impact capability gap in the current system

**Reference:** Global Witness (2024). "The Companies We Keep: Beneficial Ownership Transparency in Public Procurement." Fazekas, M. et al. (2018). "Objective Corruption Proxies." *European Journal on Criminal Policy and Research*.

---

### 4.3 Cross-Institution Pattern Detection

**Current State:** Each institution's tenders are analyzed independently. No detection of the same cartel operating across multiple agencies.

**Target State:** Detect cartels that spread their activity across institutions to avoid per-institution detection thresholds.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Cross-institution co-bidding graph | Build a graph where institutions are connected if they share > 3 common bidders. Weight edges by number of shared bidders and shared winners. | 0.5 weeks |
| Cartel fingerprinting | For each detected collusion cluster, compute a "fingerprint" (set of companies + their co-bidding patterns). Search for this fingerprint across all institutions. | 1 week |
| Multi-institution anomaly score | For each company, compute an anomaly score based on how many institutions they show suspicious patterns at simultaneously. Single-institution patterns might be chance; multi-institution patterns are almost certainly deliberate. | 0.5 weeks |
| Geographic cluster analysis | Map institution-company clusters geographically. Detect when a cartel operates in a specific region across multiple municipalities. | 0.5 weeks |

#### Expected Impact
- Detects sophisticated cartels that deliberately spread activity to stay under radar
- Enables prosecution-grade evidence by showing the same pattern across multiple agencies
- Estimated 10-15% increase in cartel detection rate

---

### 4.4 Subcontractor Chain Analysis

**Current State:** No subcontractor data is captured or analyzed.

**Target State:** Track subcontracting relationships and detect when the losing bidder becomes the winner's subcontractor (a classic bid-rigging pattern).

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Subcontractor data scraper | Extend the nabavki spider to extract subcontractor information from contract notices. Store in `contract_subcontractors` table. | 1 week |
| Loser-to-subcontractor detector | Flag when a losing bidder on tender T subsequently appears as a subcontractor on the winning contract for T. This is a strong indicator of bid rotation / cover bidding. | 0.5 weeks |
| Subcontractor network graph | Add `subcontracts_to` edges to the knowledge graph. Analyze subcontracting chains for circular patterns. | 0.5 weeks |

#### Expected Impact
- Detects the "complementary bidding" pattern where losers are compensated via subcontracts
- Addresses DOZORRO R004 (subcontracting anomalies)
- Novel capability not present in most procurement integrity systems

---

### 4.5 Temporal Network Evolution

**Current State:** Graph analysis is a snapshot. No tracking of how the network evolves.

**Target State:** Track how the collusion network changes over time, detecting formation and dissolution of cartels.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Temporal graph snapshots | Build monthly graph snapshots from historical data (2008-present). Store as a sequence of graphs. | 0.5 weeks |
| Network evolution metrics | For each company, track: degree growth rate, clustering coefficient trend, community membership changes, centrality trajectory. | 0.5 weeks |
| Cartel lifecycle detection | Detect the four phases of a cartel: formation (new edges appearing), operation (stable dense subgraph), expansion (new members joining), dissolution (edges disappearing). | 1 week |
| Temporal GNN (T-GNN) | Implement a Temporal Graph Network (TGN) that processes the event stream of new bids as a continuous-time dynamic graph. | 2 weeks |

#### Expected Impact
- Enables prediction of future collusion (detecting formation before damage is done)
- Provides timeline evidence for investigations
- Places NabavkiData at the research frontier of procurement network analysis

**Reference:** Rossi et al. (2020). "Temporal Graph Networks for Deep Learning on Dynamic Graphs." *ICML Workshop on Graph Representation Learning*.

---

### Phase 4 Summary

| Deliverable | Effort (person-weeks) | Priority |
|-------------|----------------------|----------|
| Real-time GNN updates | 3.5 | P0 - Critical |
| Beneficial ownership network | 5.5 | P0 - Critical |
| Cross-institution pattern detection | 2.5 | P1 - High |
| Subcontractor chain analysis | 2.0 | P1 - High |
| Temporal network evolution | 4.0 | P2 - Medium |
| **Phase 4 Total** | **17.5** | |

---

## Phase 5: Cross-Country & Scale (Month 9-12)

### Objective
Scale the corruption detection system beyond North Macedonia to cover Kosovo, Albania, and Serbia procurement systems, while implementing enterprise-grade infrastructure for real-time monitoring, privacy-preserving collaboration, and configurable alerting.

### 5.1 Transfer Learning from DOZORRO Labeled Dataset

**Current State:** No labeled ground truth. Models are trained on proxy labels.

**Target State:** Use DOZORRO's labeled dataset (~5,000 Ukrainian procurement cases with confirmed/rejected corruption labels) to pre-train models, then fine-tune on Macedonian data.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| DOZORRO data acquisition | Negotiate data sharing agreement with Transparency International Ukraine. Obtain labeled dataset with feature mappings. | 1 week (coordination) |
| Feature alignment layer | Map DOZORRO features to NabavkiData features. Handle schema differences (different field names, different procurement laws, different currencies). Build a "universal procurement feature vector." | 2 weeks |
| Pre-training on DOZORRO labels | Train RF, XGBoost, and Transformer models on DOZORRO labeled data. Evaluate cross-country transfer accuracy. | 1 week |
| Fine-tuning on MK data | Fine-tune pre-trained models on NabavkiData proxy labels + any accumulated analyst reviews (from Phase 1 active learning). Evaluate lift vs. training from scratch. | 1 week |
| Domain adaptation module | Implement DANN (Domain-Adversarial Neural Network) for unsupervised domain adaptation: learn features that are predictive of corruption but invariant to the source country. | 1.5 weeks |

#### Expected Impact
- Access to ~5,000 labeled examples dramatically improves model quality
- Estimated 15-20% improvement in precision from real labels vs. proxy labels
- Establishes a framework for cross-country model sharing

**Reference:** Ganin et al. (2016). "Domain-Adversarial Training of Neural Networks." *JMLR*. DOZORRO: Transparency International Ukraine, https://dozorro.org.

---

### 5.2 Multi-Country Deployment

**Current State:** System is hardcoded for North Macedonia's e-nabavki.gov.mk portal.

**Target State:** Support procurement data from Kosovo (e-prokurimi.rks-gov.net), Albania (app.gov.al/prokurimet), and Serbia (portal.ujn.gov.rs).

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Country abstraction layer | Refactor the data model to support `country_code` on all tables. Abstract procurement-law-specific logic (thresholds, procedure types, legal requirements) into per-country configuration files. | 2 weeks |
| Kosovo scraper | Develop Scrapy spider for Kosovo's e-procurement portal. Map Kosovo's data schema to the universal model. | 2 weeks |
| Albania scraper | Develop Scrapy spider for Albania's procurement portal. | 2 weeks |
| Serbia scraper | Develop Scrapy spider for Serbia's PORTAL UJN. | 2 weeks |
| Cross-country analytics | Build dashboards comparing corruption patterns across countries. Identify companies that operate in multiple countries (a strong cartel indicator). | 1 week |
| Country-specific CRI calibration | Each country gets its own CRI weight vector, calibrated to local procurement patterns. Shared base model, country-specific fine-tuning. | 1 week |

#### Required Data Sources
- Kosovo: e-prokurimi.rks-gov.net (public portal)
- Albania: app.gov.al (public portal)
- Serbia: portal.ujn.gov.rs (public portal)
- OCDS (Open Contracting Data Standard) feeds where available

#### Expected Impact
- 4x increase in data coverage, enabling stronger models via more training data
- Cross-border cartel detection (companies operating across Balkan markets)
- Positions NabavkiData as the regional procurement integrity platform

---

### 5.3 Federated Learning for Privacy-Preserving Collaboration

**Current State:** No mechanism for collaboration with other procurement agencies or anti-corruption bodies.

**Target State:** Enable multiple agencies to collaboratively train shared corruption detection models without sharing raw tender data.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Federated learning framework | Implement Federated Averaging (FedAvg) using the Flower framework. Each participating agency trains a local model on their data and shares only model gradients. | 2 weeks |
| Differential privacy integration | Add DP-SGD (Differentially Private Stochastic Gradient Descent) to federated training. Guarantee that no individual tender's data can be reconstructed from shared gradients. Privacy budget: epsilon = 1.0. | 1.5 weeks |
| Secure aggregation server | Deploy a central aggregation server that combines model updates from participating agencies without seeing individual updates (using secure multi-party computation or trusted execution environments). | 1.5 weeks |
| Federation protocol specification | Document the data format, communication protocol, and participation requirements for agencies wanting to join the federation. | 0.5 weeks |

#### Expected Impact
- Enables collaboration between procurement agencies that cannot legally share raw data (GDPR, national data protection laws)
- Collective intelligence: each agency benefits from patterns learned across all agencies
- Novel contribution to the procurement integrity field

**Reference:** McMahan et al. (2017). "Communication-Efficient Learning of Deep Networks from Decentralized Data." *AISTATS*. Abadi et al. (2016). "Deep Learning with Differential Privacy." *CCS*.

---

### 5.4 Real-Time Event Streaming

**Current State:** Batch processing. The spider runs every 3 hours, scrapes 10 pages, and inserts into PostgreSQL. Corruption analysis runs as daily cron jobs.

**Target State:** Real-time event-driven architecture where new tenders, bids, and awards trigger immediate analysis.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Event bus (Kafka/Redis Streams) | Deploy Apache Kafka or Redis Streams as a message broker. Events: `tender_created`, `bid_submitted`, `tender_awarded`, `contract_signed`. | 1.5 weeks |
| Stream processing pipeline | Build a stream processor (Faust or custom asyncio consumer) that listens for events and triggers: (a) rule-based flag evaluation, (b) ML prediction, (c) GNN graph update, (d) alert evaluation. | 2 weeks |
| Real-time dashboard | WebSocket-based live updates to the frontend dashboard. New flags appear within seconds of scraping. | 1 week |
| Event replay capability | Store all events in a persistent log. Enable replay for debugging, backtesting new models on historical event streams, and disaster recovery. | 0.5 weeks |

#### Infrastructure Notes
- The current EC2 instance (3.8GB RAM) cannot run Kafka. Options:
  1. **Amazon MSK Serverless** (managed Kafka, pay-per-use): recommended for production
  2. **Redis Streams** (lightweight, can run on current instance): recommended for initial implementation
  3. **AWS SQS + Lambda**: serverless alternative, simpler but less flexible

#### Expected Impact
- Detection latency drops from 24+ hours to minutes
- Enables intervention before contract signing (currently, many flags arrive too late)
- Positions the system for live monitoring use cases requested by government users

---

### 5.5 Configurable Alert System

**Current State:** Flagged tenders appear in the dashboard. No push notifications, no per-institution thresholds, no escalation rules.

**Target State:** Comprehensive alert system with configurable rules, escalation paths, and delivery channels.

#### Technical Deliverables

| Deliverable | Description | Effort |
|-------------|-------------|--------|
| Alert rule engine | JSON-based rule definitions: "If institution X has CRI > 70 and flag_type = 'single_bidder', send email to [analyst@agency.mk]". Support AND/OR/NOT logic, value thresholds, and time windows. | 1.5 weeks |
| Delivery channels | Email (via existing SES), SMS (via AWS SNS), Slack/webhook, and in-app notification. Per-user channel preferences. | 1 week |
| Escalation rules | If an alert is not acknowledged within 48 hours, escalate to the next level. Configurable escalation chain per institution. | 0.5 weeks |
| Alert deduplication and batching | Prevent alert fatigue: batch similar alerts, suppress duplicates within a time window, and provide daily digest summaries. | 0.5 weeks |
| Per-institution threshold configuration | Admin UI for procurement oversight bodies to set custom alert thresholds per institution. "Flag municipality X only if CRI > 60, but flag ministry Y if CRI > 40." | 1 week |

#### Expected Impact
- Transforms the system from passive (user queries dashboard) to active (system alerts user)
- Reduces time-to-investigation from days to hours
- Enables oversight bodies to monitor their portfolio of institutions in real time

---

### Phase 5 Summary

| Deliverable | Effort (person-weeks) | Priority |
|-------------|----------------------|----------|
| Transfer learning from DOZORRO | 6.5 | P0 - Critical |
| Multi-country deployment | 10.0 | P1 - High |
| Federated learning | 5.5 | P2 - Medium |
| Real-time event streaming | 5.0 | P1 - High |
| Configurable alert system | 4.5 | P1 - High |
| **Phase 5 Total** | **31.5** | |

---

## Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Insufficient labeled data** | High | High | Phase 1 active learning generates labels incrementally. Phase 5 DOZORRO transfer provides external labels. Use semi-supervised methods as bridge. |
| **Memory constraints on EC2** | High | Medium | Phase 1 addresses with ONNX export and model quantization. Phase 5 event streaming may require infrastructure upgrade (t3.xlarge, 16GB). |
| **Macedonian NLP model quality** | Medium | High | Macedonian is low-resource for NLP. Mitigation: use multilingual models (mBERT, XLM-R), Gemini API (handles Macedonian), and bootstrap training data from structured fields. |
| **Regulatory changes** | Medium | Medium | Country abstraction layer (Phase 5) isolates procurement-law-specific logic. New regulations require config changes, not code changes. |
| **Adversarial adaptation by fraudsters** | Medium | High | Phase 3 adversarial training hardens models. Phase 4 network analysis catches patterns that are harder to game than individual tender features. |
| **Data access for new countries** | Medium | Medium | Kosovo, Albania, Serbia portals are public. However, scraping terms may change. Maintain relationships with national procurement agencies. Pursue official data sharing agreements. |
| **DOZORRO data sharing agreement** | Medium | High | If DOZORRO data is unavailable, fall back to (a) OpenTender EU data (partially labeled), (b) synthetic label generation from expert rules, (c) weak supervision with Snorkel. |
| **Team capacity** | Low | High | Phased approach allows prioritization. Phase 1-2 can be executed by 2 engineers. Phase 3-5 may require hiring 1-2 ML engineers. |

---

## Resource Requirements Summary

### Total Effort by Phase

| Phase | Timeframe | Person-Weeks | Priority Level |
|-------|-----------|-------------|----------------|
| Phase 1: Integration & Calibration | Month 1-2 | 15.5 | P0 - Must have |
| Phase 2: NLP & Document Analysis | Month 3-4 | 16.0 | P0/P1 |
| Phase 3: Advanced ML | Month 5-6 | 17.0 | P1/P2 |
| Phase 4: Network Intelligence | Month 7-8 | 17.5 | P0/P1 |
| Phase 5: Cross-Country & Scale | Month 9-12 | 31.5 | P1/P2 |
| **Total** | **12 months** | **97.5** | |

### Infrastructure Requirements

| Resource | Current | Phase 1-2 | Phase 3-4 | Phase 5 |
|----------|---------|-----------|-----------|---------|
| EC2 Instance | t3.medium (3.8GB) | t3.large (8GB) | t3.xlarge (16GB) | t3.xlarge + inference instance |
| RDS PostgreSQL | db.t3.micro | db.t3.small | db.t3.medium | db.t3.medium + read replica |
| Redis/Cache | None | ElastiCache t3.micro | ElastiCache t3.small | ElastiCache t3.medium |
| Event Streaming | None | None | Redis Streams | Amazon MSK or Redis Streams |
| GPU (optional) | None | None | Spot GPU for retraining | Spot GPU for GNN + Transformer |
| Estimated Monthly Cost | ~$100 | ~$200 | ~$400 | ~$600-800 |

### Team Requirements

| Role | Phase 1-2 | Phase 3-4 | Phase 5 |
|------|-----------|-----------|---------|
| ML Engineer | 1 FTE | 1-2 FTE | 2 FTE |
| Backend Engineer | 0.5 FTE | 0.5 FTE | 1 FTE |
| Data Engineer | 0.25 FTE | 0.5 FTE | 1 FTE |
| Procurement Domain Expert | 0.25 FTE (labeling) | 0.25 FTE | 0.5 FTE |

---

## Academic & Institutional References

### Core References

1. **DOZORRO Indicators Framework**
   Transparency International Ukraine. "Risk Indicators for ProZorro Procurement System." (2019).
   https://dozorro.org
   *Defines 40+ procurement red flag indicators. The gold standard for post-Soviet procurement monitoring.*

2. **OECD Red Flags for Public Procurement**
   OECD (2016). "Preventing Corruption in Public Procurement."
   https://www.oecd.org/governance/ethics/Corruption-Public-Procurement-Brochure.pdf
   *Framework for detecting bid rigging, specification tailoring, and procurement fraud across OECD countries.*

3. **World Bank Procurement Red Flags**
   World Bank Integrity Vice Presidency (2014). "Fraud and Corruption Awareness Handbook."
   *Defines 25+ red flags used across World Bank-financed projects. Applicable to developing country contexts.*

### Machine Learning for Corruption Detection

4. **Fazekas, M. & Kocsis, G. (2020)**
   "Uncovering High-Level Corruption: Cross-National Corruption Proxies Using Government Contracting Data." *British Journal of Political Science*, 50(1), 155-164.
   *Pioneering work on objective corruption proxies from procurement data. Introduces the single-bidder indicator as a validated corruption measure.*

5. **Wachs, J., Fazekas, M., & Kertesz, J. (2021)**
   "Corruption Risk in Contracting Markets: A Network Science Perspective." *Social Networks*, 65, 76-88.
   *Network analysis of procurement corruption. Introduces community-level corruption risk scores.*

6. **Gallego, J., Rivero, G., & Martinez, J. (2021)**
   "Preventing Rather than Punishing: An Early Warning Model of Malfeasance in Public Procurement." *International Journal of Forecasting*, 37(1), 360-377.
   *ML-based early warning system for Colombian procurement. Demonstrates that ML significantly outperforms rule-based approaches.*

### Graph Neural Networks

7. **Hamilton, W., Ying, R., & Leskovec, J. (2017)**
   "Inductive Representation Learning on Large Graphs." *NeurIPS*.
   *Introduces GraphSAGE, the architecture used in our GNN backbone.*

8. **Velickovic, P. et al. (2018)**
   "Graph Attention Networks." *ICLR*.
   *Introduces GAT (Graph Attention Networks). Used as the final layer in our CollusionGNN.*

9. **Rossi, E. et al. (2020)**
   "Temporal Graph Networks for Deep Learning on Dynamic Graphs." *ICML Workshop*.
   *Foundation for Phase 4's temporal network evolution capability.*

### Explainability

10. **Lundberg, S. & Lee, S. (2017)**
    "A Unified Approach to Interpreting Model Predictions." *NeurIPS*.
    *Introduces SHAP values. TreeSHAP (exact, fast) for tree-based models. Core of Phase 1 explainability.*

11. **Mothilal, R.K., Sharma, A., & Tan, C. (2020)**
    "Explaining Machine Learning Classifiers through Diverse Counterfactual Explanations." *FAT*.
    *DiCE library for counterfactual explanations. Used in Phase 1 for "what-if" analysis.*

### Causal Inference

12. **Athey, S. & Imbens, G. (2019)**
    "Machine Learning Methods That Economists Should Know About." *Annual Review of Economics*.
    *Survey covering causal forests and treatment effect estimation. Foundation for Phase 3 causal inference.*

13. **Wager, S. & Athey, S. (2018)**
    "Estimation and Inference of Heterogeneous Treatment Effects using Random Forests." *JASA*.
    *Introduces Generalized Random Forests (GRF). Core methodology for Phase 3.2.*

### Adversarial ML

14. **Ballet, V. et al. (2019)**
    "Imperceptible Adversarial Attacks on Tabular Data." *NeurIPS Workshop on Robust AI in Financial Services*.
    *Adversarial attacks specifically designed for tabular/structured data. Directly applicable to procurement feature vectors.*

### Federated Learning & Privacy

15. **McMahan, B. et al. (2017)**
    "Communication-Efficient Learning of Deep Networks from Decentralized Data." *AISTATS*.
    *Introduces Federated Averaging (FedAvg). Core algorithm for Phase 5 federation.*

16. **Abadi, M. et al. (2016)**
    "Deep Learning with Differential Privacy." *CCS*.
    *DP-SGD for privacy-preserving model training. Applied in Phase 5.3.*

### Uncertainty Quantification

17. **Gal, Y. & Ghahramani, Z. (2016)**
    "Dropout as a Bayesian Approximation: Representing Model Uncertainty in Deep Learning." *ICML*.
    *MC Dropout for epistemic uncertainty. Applied in Phase 1.4.*

18. **Romano, Y., Patterson, E., & Candes, E. (2019)**
    "Conformalized Quantile Regression." *NeurIPS*.
    *Conformal prediction for distribution-free prediction intervals. Applied in Phase 3.5.*

### NLP for Procurement

19. **Conneau, A. et al. (2020)**
    "Unsupervised Cross-lingual Representation Learning at Scale." *ACL*.
    *XLM-RoBERTa: multilingual transformer. Candidate for Macedonian NER and specification analysis.*

20. **Ratner, A. et al. (2017)**
    "Snorkel: Rapid Training Data Creation with Weak Supervision." *VLDB*.
    *Weak supervision framework for bootstrapping labels from heuristic rules. Fallback if DOZORRO data unavailable.*

---

## Appendix A: DOZORRO Indicator Coverage Map

Detailed mapping of DOZORRO indicators to NabavkiData implementation status, with target phase for each gap.

| DOZORRO ID | Indicator Name | NabavkiData Status | Implementation | Target Phase |
|-----------|---------------|-------------------|----------------|--------------|
| C001 | Single bidder | Fully implemented | `single_bidder` detector | -- |
| C002 | Low participation | Fully implemented | `LowParticipationIndicator` | -- |
| C003 | Same bidder set | Fully implemented | `SameBidderSetIndicator` | -- |
| C004 | Low bidder diversity | Fully implemented | `BidderDiversityIndicator` (Shannon entropy) | -- |
| C005 | Declining competition | Partial | `CompetitionTrendIndicator` (basic) | Phase 3 (temporal) |
| C006 | Market concentration | Fully implemented | HHI calculation | -- |
| C007 | New entrant barriers | Partial | `NewBidderRateIndicator` | Phase 2 (NLP specs) |
| C008 | Geographic concentration | Stub | `GeographicConcentrationIndicator` | Phase 4 |
| C009 | Bidder experience gap | Fully implemented | `BidderExperienceIndicator` | -- |
| C010 | Competition trend | Partial | Basic trend | Phase 3 (Transformer) |
| P001 | Price deviation | Fully implemented | Z-score based | -- |
| P002 | Bid clustering | Fully implemented | CV analysis | -- |
| P003 | Cover bidding | Fully implemented | Gap analysis (1st vs 2nd) | -- |
| P004 | Round number bids | Fully implemented | `RoundNumberIndicator` | -- |
| P005 | Identical bids | Fully implemented | `identical_bids` detector | -- |
| P006 | Below-market pricing | Partial | `BelowMarketPricingIndicator` (limited market data) | Phase 5 (cross-country) |
| P007 | Price variance pattern | Fully implemented | Variance analysis | -- |
| P008 | Estimate match | Fully implemented | `EstimateMatchIndicator` | -- |
| P009 | Price sequence | Partial | `PriceSequenceIndicator` (basic) | Phase 3 (temporal) |
| P010 | Value manipulation | Not started | -- | Phase 2 (NLP) |
| T001 | Short deadline | Fully implemented | `short_deadline` detector | -- |
| T002 | Weekend/holiday publication | Fully implemented | `WeekendPublicationIndicator` | -- |
| T003 | Election cycle timing | Fully implemented | `ElectionCycleIndicator` | -- |
| T004 | End-of-year spending | Fully implemented | `SeasonalPatternIndicator` | -- |
| T005 | Late amendments | Fully implemented | `late_amendment` detector | -- |
| T006 | Abnormally fast process | Partial | `ProcessDurationIndicator` | Phase 3 (temporal) |
| T007 | Deadline extensions | Partial | `DeadlineExtensionIndicator` | Phase 2 (NLP docs) |
| T008 | Submission clustering | Stub | `SubmissionClusteringIndicator` | Phase 4 |
| R001 | Beneficial ownership | Not started | -- | Phase 4 (ownership graph) |
| R002 | Conflict of interest | Not started | -- | Phase 2 (NER) + Phase 4 |
| R003 | Repeat winner dominance | Fully implemented | `repeat_winner` detector | -- |
| R004 | Subcontracting anomalies | Not started | -- | Phase 4 (subcontractor) |
| R005 | Specification manipulation | Not started | -- | Phase 2 (NLP) |
| R006 | Brand-name specifications | Not started | -- | Phase 2 (NLP) |
| R007 | Restrictive requirements | Not started | -- | Phase 2 (NLP) |
| PR001 | Non-competitive procedure | Stub | `procedure_type` (basic) | Phase 2 |
| PR002 | Lot splitting | Stub | `contract_splitting` (basic) | Phase 3 (causal) |
| PR003 | Threshold avoidance | Partial | `threshold_manipulation` detector | Phase 3 |
| PR004 | Qualification manipulation | Not started | -- | Phase 2 (NLP) |
| PR005 | Contract modifications | Stub | `contract_value_growth` (basic) | Phase 4 |

**Coverage after each phase:**

| Phase | Fully Implemented | Partial | Stub | Not Started | Coverage |
|-------|------------------|---------|------|-------------|----------|
| Current | 19 | 8 | 6 | 7 | ~13/40 effective |
| After Phase 1 | 19 | 8 | 6 | 7 | ~19/40 (+ calibration) |
| After Phase 2 | 25 | 6 | 4 | 5 | ~25/40 |
| After Phase 3 | 29 | 5 | 3 | 3 | ~30/40 |
| After Phase 4 | 35 | 3 | 1 | 1 | ~35/40 |
| After Phase 5 | 38 | 2 | 0 | 0 | ~38/40 |

---

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **CRI** | Corruption Risk Index. A weighted composite score (0-100) aggregating all corruption indicators for a single tender. |
| **DOZORRO** | Ukrainian civic monitoring platform for ProZorro procurement system. Developed by Transparency International Ukraine. Defines the de facto standard for procurement red flag indicators. |
| **GNN** | Graph Neural Network. A neural network that operates on graph-structured data, learning node and edge representations. |
| **GraphSAGE** | Graph Sample and Aggregate. An inductive GNN architecture that generates node embeddings by sampling and aggregating features from a node's local neighborhood. |
| **GAT** | Graph Attention Network. A GNN that uses attention mechanisms to weight the importance of different neighbors. |
| **HHI** | Herfindahl-Hirschman Index. A measure of market concentration, calculated as the sum of squared market shares. Range: 0-10,000. Higher = more concentrated. |
| **SHAP** | SHapley Additive exPlanations. A game-theoretic approach to explain individual model predictions by computing each feature's contribution. |
| **TreeSHAP** | An efficient, exact algorithm for computing SHAP values for tree-based models (RF, XGBoost, LightGBM). O(TLD) complexity. |
| **CRI Confidence Interval** | The range within which the true CRI score lies with 90% probability, accounting for data uncertainty and model uncertainty. |
| **Active Learning** | An ML paradigm where the model selects the most informative examples for human labeling, maximizing label efficiency. |
| **Causal Forest** | A variant of Random Forest (Generalized Random Forest) that estimates heterogeneous treatment effects rather than predictions. |
| **Conformal Prediction** | A framework for distribution-free prediction intervals with finite-sample coverage guarantees. |
| **Federated Learning** | Training ML models across multiple decentralized data sources without centralizing the raw data. |
| **MC Dropout** | Monte Carlo Dropout. A Bayesian approximation technique that estimates model uncertainty by running multiple forward passes with dropout enabled at inference time. |
| **ONNX** | Open Neural Network Exchange. A portable format for ML models that enables inference without the full training framework. |
| **NER** | Named Entity Recognition. The NLP task of identifying and classifying named entities (persons, organizations, locations) in text. |
| **CPV** | Common Procurement Vocabulary. An EU-standard classification system for public procurement. |
| **OCDS** | Open Contracting Data Standard. An international standard for publishing structured procurement data. |
| **DiCE** | Diverse Counterfactual Explanations. A library for generating diverse "what-if" explanations for ML predictions. |
| **FGSM** | Fast Gradient Sign Method. An adversarial attack that perturbs input features in the direction of the gradient to fool a classifier. |
| **FedAvg** | Federated Averaging. The canonical federated learning algorithm where clients compute local updates and the server averages them. |
| **DP-SGD** | Differentially Private Stochastic Gradient Descent. An SGD variant that clips gradients and adds noise to guarantee differential privacy. |
| **TGN** | Temporal Graph Network. A GNN architecture designed for continuous-time dynamic graphs. |

---

*This document is maintained by the NabavkiData engineering team and is updated quarterly. For questions, contributions, or partnership inquiries, contact team@nabavkidata.com.*

*Last review: February 2026*

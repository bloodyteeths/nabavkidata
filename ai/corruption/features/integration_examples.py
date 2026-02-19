"""
Integration Examples - Feature Extractor with ML Models

This file demonstrates how to integrate the FeatureExtractor with:
1. XGBoost classifier
2. SHAP explainability
3. Sklearn models
4. Existing corruption_detector.py

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import asyncpg
import os
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
import logging
from datetime import datetime

# ML imports
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import shap

# Our modules
from ai.corruption.features.feature_extractor import FeatureExtractor
from ai.corruption_detector import CorruptionAnalyzer
from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)

# Database config
DB_URL = os.getenv("DATABASE_URL")


# =============================================================================
# Example 1: Train XGBoost Model
# =============================================================================

async def train_xgboost_model():
    """
    Train an XGBoost classifier for corruption detection.

    This example shows how to:
    1. Extract features for labeled tenders
    2. Train XGBoost model
    3. Evaluate performance
    4. Save model for production use
    """
    print("=" * 80)
    print("EXAMPLE 1: Training XGBoost Corruption Detection Model")
    print("=" * 80)

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=3)

    try:
        extractor = FeatureExtractor(pool)

        # Step 1: Get labeled data (from corruption_flags or manual review)
        print("\nStep 1: Loading labeled training data...")

        async with pool.acquire() as conn:
            # Get tenders with corruption flags (positive examples)
            corrupt_tenders = await conn.fetch("""
                SELECT DISTINCT tender_id
                FROM tender_risk_scores
                WHERE risk_score >= 70
                LIMIT 200
            """)
            corrupt_ids = [row['tender_id'] for row in corrupt_tenders]

            # Get clean tenders (negative examples)
            clean_tenders = await conn.fetch("""
                SELECT tender_id
                FROM tenders
                WHERE status = 'awarded'
                  AND num_bidders >= 3
                  AND tender_id NOT IN (
                      SELECT tender_id FROM tender_risk_scores WHERE risk_score >= 50
                  )
                ORDER BY RANDOM()
                LIMIT 200
            """)
            clean_ids = [row['tender_id'] for row in clean_tenders]

        print(f"  Corrupt tenders: {len(corrupt_ids)}")
        print(f"  Clean tenders: {len(clean_ids)}")

        # Step 2: Extract features
        print("\nStep 2: Extracting features...")
        all_ids = corrupt_ids + clean_ids
        labels = [1] * len(corrupt_ids) + [0] * len(clean_ids)

        feature_vectors = await extractor.extract_features_batch(all_ids)

        # Create feature matrix and label vector
        X = np.array([fv.feature_array for fv in feature_vectors])
        y = np.array(labels)

        print(f"  Feature matrix shape: {X.shape}")
        print(f"  Labels: {len(y)} (Corrupt: {sum(y)}, Clean: {len(y) - sum(y)})")

        # Step 3: Train/test split
        print("\nStep 3: Splitting data...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        print(f"  Training: {X_train.shape[0]} samples")
        print(f"  Testing: {X_test.shape[0]} samples")

        # Step 4: Train XGBoost
        print("\nStep 4: Training XGBoost model...")
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            min_child_weight=1,
            subsample=0.8,
            colsample_bytree=0.8,
            objective='binary:logistic',
            random_state=42
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )

        # Step 5: Evaluate
        print("\nStep 5: Evaluating model...")
        y_pred = model.predict(X_test)
        y_pred_proba = model.predict_proba(X_test)[:, 1]

        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, target_names=['Clean', 'Corrupt']))

        print(f"\nROC-AUC Score: {roc_auc_score(y_test, y_pred_proba):.4f}")

        # Confusion Matrix
        cm = confusion_matrix(y_test, y_pred)
        print("\nConfusion Matrix:")
        print(f"  True Negatives: {cm[0, 0]}")
        print(f"  False Positives: {cm[0, 1]}")
        print(f"  False Negatives: {cm[1, 0]}")
        print(f"  True Positives: {cm[1, 1]}")

        # Step 6: Feature importance
        print("\nStep 6: Top 20 Most Important Features:")
        feature_names = feature_vectors[0].feature_names
        feature_importance = model.feature_importances_
        top_indices = np.argsort(feature_importance)[-20:][::-1]

        for i, idx in enumerate(top_indices, 1):
            print(f"  {i:2d}. {feature_names[idx]:40s} {feature_importance[idx]:.4f}")

        # Step 7: Save model
        print("\nStep 7: Saving model...")
        model.save_model('corruption_xgboost_model.json')
        print("  Model saved to: corruption_xgboost_model.json")

        return model, feature_names

    finally:
        await pool.close()


# =============================================================================
# Example 2: SHAP Explainability
# =============================================================================

async def explain_with_shap(model, feature_names: List[str]):
    """
    Use SHAP to explain model predictions.

    This shows:
    1. SHAP value calculation
    2. Feature importance plots
    3. Individual prediction explanation
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 2: SHAP Explainability")
    print("=" * 80)

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)

    try:
        extractor = FeatureExtractor(pool)

        # Get a few test tenders
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT tender_id
                FROM tenders
                WHERE status = 'awarded'
                ORDER BY RANDOM()
                LIMIT 10
            """)
            tender_ids = [row['tender_id'] for row in rows]

        # Extract features
        feature_vectors = await extractor.extract_features_batch(tender_ids)
        X = np.array([fv.feature_array for fv in feature_vectors])

        # Calculate SHAP values
        print("\nCalculating SHAP values...")
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)

        print("SHAP values calculated!")
        print(f"  Shape: {shap_values.shape}")

        # Example: Explain first tender
        print(f"\nExplaining tender: {tender_ids[0]}")
        print(f"  Prediction: {model.predict_proba(X[0:1])[0, 1]:.2%} corruption risk")

        # Get top SHAP contributors
        shap_for_tender = shap_values[0]
        top_shap_indices = np.argsort(np.abs(shap_for_tender))[-10:][::-1]

        print("\nTop 10 Contributing Features:")
        for idx in top_shap_indices:
            fname = feature_names[idx]
            fvalue = X[0, idx]
            shap_value = shap_for_tender[idx]
            direction = "increases" if shap_value > 0 else "decreases"
            print(f"  {fname:40s} = {fvalue:8.2f} → {direction} risk by {abs(shap_value):.4f}")

        # Summary plot (would be visualized in Jupyter)
        print("\nTo visualize SHAP values, use:")
        print("  shap.summary_plot(shap_values, X, feature_names=feature_names)")
        print("  shap.force_plot(explainer.expected_value, shap_values[0], X[0], feature_names=feature_names)")

    finally:
        await pool.close()


# =============================================================================
# Example 3: Integration with Existing Corruption Detector
# =============================================================================

async def combine_rule_based_and_ml():
    """
    Combine rule-based detector with ML model.

    This shows how to:
    1. Run rule-based detection
    2. Extract ML features
    3. Combine both approaches
    4. Generate final assessment
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Combining Rule-Based and ML Detection")
    print("=" * 80)

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=3)

    try:
        # Initialize both systems
        rule_analyzer = CorruptionAnalyzer(DB_URL)
        await rule_analyzer.initialize()

        ml_extractor = FeatureExtractor(pool)

        # Load trained ML model (from Example 1)
        ml_model = xgb.XGBClassifier()
        ml_model.load_model('corruption_xgboost_model.json')

        # Select a tender to analyze
        async with pool.acquire() as conn:
            tender = await conn.fetchrow("""
                SELECT tender_id
                FROM tenders
                WHERE status = 'awarded'
                  AND num_bidders > 0
                ORDER BY RANDOM()
                LIMIT 1
            """)
            tender_id = tender['tender_id']

        print(f"\nAnalyzing tender: {tender_id}")

        # 1. Rule-based detection
        print("\n1. Rule-based detection...")
        rule_assessment = await rule_analyzer.analyze_tender(tender_id)

        if rule_assessment:
            print(f"   Rule-based risk score: {rule_assessment['risk_score']}/100")
            print(f"   Risk level: {rule_assessment['risk_level']}")
            print(f"   Flags: {rule_assessment['flag_count']}")
        else:
            print("   No rule-based assessment available")

        # 2. ML-based detection
        print("\n2. ML-based detection...")
        features = await ml_extractor.extract_features(tender_id)
        X = features.feature_array.reshape(1, -1)
        ml_probability = ml_model.predict_proba(X)[0, 1]
        ml_score = int(ml_probability * 100)

        print(f"   ML risk score: {ml_score}/100")
        print(f"   ML probability: {ml_probability:.2%}")

        # 3. Combined assessment
        print("\n3. Combined assessment...")

        # Simple ensemble: average of rule-based and ML
        if rule_assessment:
            combined_score = (rule_assessment['risk_score'] + ml_score) / 2
        else:
            combined_score = ml_score

        if combined_score >= 75:
            combined_level = 'critical'
        elif combined_score >= 60:
            combined_level = 'high'
        elif combined_score >= 40:
            combined_level = 'medium'
        elif combined_score >= 20:
            combined_level = 'low'
        else:
            combined_level = 'minimal'

        print(f"   Combined score: {combined_score:.0f}/100")
        print(f"   Combined level: {combined_level}")

        # 4. Agreement analysis
        if rule_assessment:
            agreement = abs(rule_assessment['risk_score'] - ml_score) <= 20
            print(f"   Rule-based vs ML agreement: {'Yes' if agreement else 'No'}")
            if not agreement:
                print(f"   → Manual review recommended (disagreement between methods)")

        await rule_analyzer.close()

    finally:
        await pool.close()


# =============================================================================
# Example 4: Batch Scoring for Production
# =============================================================================

async def batch_score_production():
    """
    Score all awarded tenders for production dashboard.

    This shows:
    1. Efficient batch processing
    2. Score storage
    3. Performance monitoring
    """
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Production Batch Scoring")
    print("=" * 80)

    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)

    try:
        extractor = FeatureExtractor(pool)
        model = xgb.XGBClassifier()
        model.load_model('corruption_xgboost_model.json')

        # Get tenders to score
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT tender_id
                FROM tenders
                WHERE status = 'awarded'
                  AND publication_date >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY publication_date DESC
                LIMIT 100
            """)
            tender_ids = [row['tender_id'] for row in rows]

        print(f"\nScoring {len(tender_ids)} recent tenders...")

        # Batch extract features
        start_time = datetime.now()
        feature_vectors = await extractor.extract_features_batch(tender_ids)
        extraction_time = (datetime.now() - start_time).total_seconds()

        print(f"  Feature extraction: {extraction_time:.2f}s ({extraction_time/len(tender_ids)*1000:.0f}ms per tender)")

        # Batch predict
        X = np.array([fv.feature_array for fv in feature_vectors])
        start_time = datetime.now()
        predictions = model.predict_proba(X)[:, 1]
        prediction_time = (datetime.now() - start_time).total_seconds()

        print(f"  ML prediction: {prediction_time:.2f}s ({prediction_time/len(tender_ids)*1000:.0f}ms per tender)")

        # Store scores
        print("\n  Storing scores...")
        async with pool.acquire() as conn:
            for tender_id, prob in zip(tender_ids, predictions):
                ml_score = int(prob * 100)
                await conn.execute("""
                    INSERT INTO tender_risk_scores (tender_id, risk_score, risk_level, last_analyzed)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (tender_id) DO UPDATE SET
                        risk_score = GREATEST(tender_risk_scores.risk_score, EXCLUDED.risk_score),
                        last_analyzed = CURRENT_TIMESTAMP
                """, tender_id, ml_score, 'high' if ml_score >= 70 else 'medium' if ml_score >= 40 else 'low')

        print("  Scores stored in database")

        # Summary statistics
        print("\n  Score distribution:")
        print(f"    Critical (>=80): {sum(predictions >= 0.8)}")
        print(f"    High (60-80):    {sum((predictions >= 0.6) & (predictions < 0.8))}")
        print(f"    Medium (40-60):  {sum((predictions >= 0.4) & (predictions < 0.6))}")
        print(f"    Low (<40):       {sum(predictions < 0.4)}")

    finally:
        await pool.close()


# =============================================================================
# Main - Run All Examples
# =============================================================================

async def main():
    """Run all integration examples"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║         Feature Extractor Integration Examples                              ║
║         ML Corruption Detection for Macedonian Procurement                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # Example 1: Train model
    model, feature_names = await train_xgboost_model()

    # Example 2: SHAP explainability
    await explain_with_shap(model, feature_names)

    # Example 3: Combine with rule-based
    await combine_rule_based_and_ml()

    # Example 4: Production batch scoring
    await batch_score_production()

    print("\n" + "=" * 80)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

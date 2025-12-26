#!/usr/bin/env python3
"""
Generate Synthetic Labeled Dataset for XGBoost Training

This script creates a synthetic labeled dataset for testing the XGBoost training
pipeline when the real labeled_dataset.json is not available (e.g., no database
connection).

The dataset is generated using:
1. Positive samples: Based on matched_tenders.json (known corruption cases)
2. Negative samples: Randomly generated clean tenders with typical distributions

Output: labeled_dataset.json with 300 samples (150 positive, 150 negative)

Usage:
    python generate_synthetic_labeled_dataset.py

Author: nabavkidata.com
License: Proprietary
"""

import json
import os
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import random

# Seed for reproducibility
np.random.seed(42)
random.seed(42)


def load_matched_tenders() -> List[Dict]:
    """Load tenders from matched_tenders.json."""
    matched_path = Path(__file__).parent / 'matched_tenders.json'

    if not matched_path.exists():
        print(f"Warning: matched_tenders.json not found at {matched_path}")
        return []

    with open(matched_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tenders = []
    for case in data.get('cases', []):
        for tender in case.get('matched_tenders', []):
            tender['case_id'] = case.get('case_id')
            tender['case_name'] = case.get('case_name')
            tender['match_confidence'] = tender.get('match_confidence', 'medium')
            tenders.append(tender)

    return tenders


def generate_positive_features(tender: Dict) -> Dict[str, Any]:
    """
    Generate features for a positive (corrupt) sample.

    These features simulate corruption patterns:
    - Single bidder or very few bidders
    - High price ratios (overpricing)
    - Short deadlines
    - Multiple flags
    """
    # Base values from tender data if available
    estimated_value = tender.get('estimated_value_mkd', 0) or 0

    # Corruption patterns
    num_bidders = np.random.choice([1, 1, 1, 2, 2, 3], p=[0.4, 0.2, 0.1, 0.15, 0.1, 0.05])
    single_bidder = 1 if num_bidders == 1 else 0

    # High price ratio (overpricing common in corruption)
    price_ratio = np.random.uniform(0.95, 1.5) if estimated_value > 0 else 0
    actual_value = estimated_value * price_ratio if estimated_value > 0 else 0
    price_deviation = price_ratio - 1.0

    # Short deadlines are suspicious
    deadline_days = int(np.random.choice([3, 5, 7, 10, 14], p=[0.3, 0.25, 0.2, 0.15, 0.1]))
    short_deadline = 1 if deadline_days < 7 else 0

    # Bid patterns (low variance suggests collusion)
    bid_mean = actual_value if actual_value > 0 else estimated_value
    bid_std = bid_mean * np.random.uniform(0.01, 0.05)  # Very low variance
    bid_cv = bid_std / bid_mean if bid_mean > 0 else 0

    # Corruption flags
    flag_count = np.random.randint(2, 8)
    max_flag_score = np.random.uniform(70, 100)
    avg_flag_score = max_flag_score * np.random.uniform(0.7, 0.95)

    # Amendments (corruption often involves amendments)
    amendment_count = np.random.choice([0, 1, 2, 3, 4], p=[0.2, 0.3, 0.25, 0.15, 0.1])
    has_amendments = 1 if amendment_count > 0 else 0

    return {
        'tender_id': tender.get('tender_id', f'synth-pos-{random.randint(1000, 9999)}'),
        'has_winner': 1,
        'num_bidders': num_bidders,
        'single_bidder': single_bidder,
        'bidder_count': num_bidders,
        'estimated_value_mkd': float(estimated_value),
        'actual_value_mkd': float(actual_value),
        'has_price_data': 1 if estimated_value > 0 else 0,
        'price_deviation': float(price_deviation),
        'price_ratio': float(price_ratio),
        'bid_mean': float(bid_mean),
        'bid_std': float(bid_std),
        'bid_cv': float(bid_cv),
        'deadline_days': deadline_days,
        'short_deadline': short_deadline,
        'num_documents': np.random.randint(3, 15),
        'amendment_count': amendment_count,
        'has_amendments': has_amendments,
        'flag_count': flag_count,
        'max_flag_score': float(max_flag_score),
        'avg_flag_score': float(avg_flag_score)
    }


def generate_negative_features() -> Dict[str, Any]:
    """
    Generate features for a negative (clean) sample.

    These features simulate healthy procurement:
    - Multiple bidders (good competition)
    - Normal price ratios (around or below estimate)
    - Reasonable deadlines
    - Few or no flags
    """
    # Healthy competition
    num_bidders = np.random.choice([3, 4, 5, 6, 7, 8, 9, 10],
                                    p=[0.15, 0.2, 0.2, 0.15, 0.1, 0.1, 0.05, 0.05])
    single_bidder = 0

    # Normal price values
    estimated_value = float(np.random.lognormal(mean=15, sigma=2))  # Log-normal distribution
    # Competitive pricing typically below estimate
    price_ratio = np.random.uniform(0.7, 1.0)
    actual_value = estimated_value * price_ratio
    price_deviation = price_ratio - 1.0

    # Reasonable deadlines
    deadline_days = int(np.random.choice([14, 21, 30, 45, 60], p=[0.1, 0.2, 0.3, 0.25, 0.15]))
    short_deadline = 0

    # Natural bid variance (healthy competition)
    bid_mean = actual_value
    bid_std = bid_mean * np.random.uniform(0.1, 0.3)  # Higher variance = real competition
    bid_cv = bid_std / bid_mean if bid_mean > 0 else 0

    # Minimal flags
    flag_count = np.random.choice([0, 0, 0, 1, 1, 2], p=[0.4, 0.2, 0.15, 0.1, 0.1, 0.05])
    max_flag_score = np.random.uniform(0, 30) if flag_count > 0 else 0
    avg_flag_score = max_flag_score * 0.8 if flag_count > 0 else 0

    # Fewer amendments
    amendment_count = np.random.choice([0, 0, 1], p=[0.7, 0.2, 0.1])
    has_amendments = 1 if amendment_count > 0 else 0

    return {
        'tender_id': f'synth-neg-{random.randint(10000, 99999)}/2024',
        'has_winner': 1,
        'num_bidders': num_bidders,
        'single_bidder': single_bidder,
        'bidder_count': num_bidders,
        'estimated_value_mkd': float(estimated_value),
        'actual_value_mkd': float(actual_value),
        'has_price_data': 1,
        'price_deviation': float(price_deviation),
        'price_ratio': float(price_ratio),
        'bid_mean': float(bid_mean),
        'bid_std': float(bid_std),
        'bid_cv': float(bid_cv),
        'deadline_days': deadline_days,
        'short_deadline': short_deadline,
        'num_documents': np.random.randint(5, 25),
        'amendment_count': amendment_count,
        'has_amendments': has_amendments,
        'flag_count': flag_count,
        'max_flag_score': float(max_flag_score),
        'avg_flag_score': float(avg_flag_score)
    }


def generate_labeled_dataset(n_positive: int = 150, n_negative: int = 150) -> Dict:
    """
    Generate complete labeled dataset.

    Args:
        n_positive: Number of positive samples
        n_negative: Number of negative samples

    Returns:
        Dataset dictionary with metadata and samples
    """
    print(f"Generating labeled dataset: {n_positive} positive, {n_negative} negative samples")

    samples = []

    # Load matched tenders for positive samples
    matched_tenders = load_matched_tenders()
    print(f"Loaded {len(matched_tenders)} matched tenders from known corruption cases")

    # Generate positive samples
    for i in range(n_positive):
        if i < len(matched_tenders):
            tender = matched_tenders[i]
            features = generate_positive_features(tender)
            confidence = 0.95 if tender.get('match_confidence') == 'high' else 0.8

            sample = {
                'tender_id': tender.get('tender_id'),
                'label': 1,
                'label_source': 'known_case',
                'confidence': confidence,
                'features': features,
                'ground_truth_case_id': tender.get('case_id'),
                'ground_truth_case_name': tender.get('case_name'),
                'risk_score': features['avg_flag_score'],
                'flag_count': features['flag_count']
            }
        else:
            # Generate additional synthetic positive samples
            features = generate_positive_features({})
            sample = {
                'tender_id': features['tender_id'],
                'label': 1,
                'label_source': 'high_score_flag',
                'confidence': 0.85,
                'features': features,
                'risk_score': features['avg_flag_score'],
                'flag_count': features['flag_count']
            }

        samples.append(sample)

    # Generate negative samples
    for i in range(n_negative):
        features = generate_negative_features()
        sample = {
            'tender_id': features['tender_id'],
            'label': 0,
            'label_source': 'low_risk_clean',
            'confidence': 0.9,
            'features': features,
            'risk_score': features['avg_flag_score'],
            'flag_count': features['flag_count']
        }
        samples.append(sample)

    # Shuffle samples
    random.shuffle(samples)

    # Calculate statistics
    positive_samples = [s for s in samples if s['label'] == 1]
    negative_samples = [s for s in samples if s['label'] == 0]
    known_case_count = sum(1 for s in positive_samples if s['label_source'] == 'known_case')

    metadata = {
        'created_at': datetime.utcnow().isoformat(),
        'generator': 'generate_synthetic_labeled_dataset.py',
        'is_synthetic': True,
        'total_samples': len(samples),
        'positive_samples': len(positive_samples),
        'negative_samples': len(negative_samples),
        'balance_ratio': len(negative_samples) / len(positive_samples),
        'sources': {
            'known_cases': known_case_count,
            'high_score_flags': len(positive_samples) - known_case_count,
            'low_risk_clean': len(negative_samples)
        },
        'confidence_stats': {
            'avg_positive_confidence': sum(s['confidence'] for s in positive_samples) / len(positive_samples),
            'avg_negative_confidence': sum(s['confidence'] for s in negative_samples) / len(negative_samples),
        }
    }

    return {
        'metadata': metadata,
        'samples': samples
    }


def main():
    """Generate and save the labeled dataset."""
    print("=" * 70)
    print("GENERATING SYNTHETIC LABELED DATASET")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().isoformat()}")

    # Generate dataset
    dataset = generate_labeled_dataset(n_positive=150, n_negative=150)

    # Print summary
    meta = dataset['metadata']
    print("\n" + "=" * 70)
    print("DATASET SUMMARY")
    print("=" * 70)
    print(f"\nTotal samples: {meta['total_samples']}")
    print(f"Positive samples: {meta['positive_samples']}")
    print(f"  - From known cases: {meta['sources']['known_cases']}")
    print(f"  - From high-score flags: {meta['sources']['high_score_flags']}")
    print(f"Negative samples: {meta['negative_samples']}")
    print(f"  - From low-risk clean: {meta['sources']['low_risk_clean']}")
    print(f"\nBalance ratio: {meta['balance_ratio']:.2f}")
    print(f"Avg positive confidence: {meta['confidence_stats']['avg_positive_confidence']:.2f}")
    print(f"Avg negative confidence: {meta['confidence_stats']['avg_negative_confidence']:.2f}")

    # Custom JSON encoder for numpy types
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)

    # Save dataset
    output_path = Path(__file__).parent / 'labeled_dataset.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

    print(f"\nDataset saved to: {output_path}")

    # Print sample features
    print("\n" + "=" * 70)
    print("SAMPLE FEATURE DISTRIBUTIONS")
    print("=" * 70)

    positive_features = [s['features'] for s in dataset['samples'] if s['label'] == 1]
    negative_features = [s['features'] for s in dataset['samples'] if s['label'] == 0]

    feature_names = ['num_bidders', 'price_ratio', 'bid_cv', 'deadline_days', 'flag_count']

    print("\n{:<20} {:>15} {:>15}".format("Feature", "Positive Mean", "Negative Mean"))
    print("-" * 52)

    for feat in feature_names:
        pos_mean = np.mean([f[feat] for f in positive_features])
        neg_mean = np.mean([f[feat] for f in negative_features])
        print(f"{feat:<20} {pos_mean:>15.3f} {neg_mean:>15.3f}")

    print("\n" + "=" * 70)
    print("DATASET GENERATED SUCCESSFULLY")
    print("=" * 70)
    print(f"\nYou can now run: python train_xgboost.py")

    return dataset


if __name__ == "__main__":
    main()

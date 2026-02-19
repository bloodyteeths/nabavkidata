"""
Counterfactual Explanation Engine (DiCE-style) for Corruption Risk Scores

Generates counterfactual explanations that answer:
"What would need to change for this tender to NOT be flagged as high-risk?"

Uses a genetic algorithm approach to find minimal, diverse changes to features
that would lower the risk score below a configurable threshold.

Architecture:
- Population of candidate counterfactuals are evolved over generations
- Tournament selection + uniform crossover + constraint-respecting mutation
- Feasibility scoring penalizes unrealistic changes
- Diversity enforcement ensures the returned set covers different feature subsets

Author: nabavkidata.com
License: Proprietary
"""

import copy
import logging
import math
import random
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# CRI weights matching backend/api/corruption.py
CRI_WEIGHTS: Dict[str, float] = {
    'single_bidder': 1.0,
    'procedure_type': 1.2,
    'contract_splitting': 1.3,
    'identical_bids': 1.5,
    'strategic_disqualification': 1.4,
    'bid_rotation': 1.2,
    'professional_loser': 0.8,
    'short_deadline': 0.9,
    'short_decision': 1.0,
    'contract_value_growth': 1.0,
    'late_amendment': 0.9,
    'threshold_manipulation': 0.8,
    'repeat_winner': 1.1,
    'price_anomaly': 1.1,
    'bid_clustering': 1.2,
}


# Human-readable descriptions for feature changes (English + Macedonian)
CHANGE_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    'single_bidder': {
        'decrease': "Attract more bidders to eliminate single-bidder flag / Привлечете повеќе понудувачи за да се елиминира знамето за единствен понудувач",
    },
    'repeat_winner': {
        'decrease': "Diversify supplier selection to reduce repeat-winner concentration / Диверзифицирајте го изборот на добавувачи",
    },
    'price_anomaly': {
        'decrease': "Ensure pricing is within normal market range / Обезбедете цената да биде во нормален пазарен опсег",
    },
    'bid_clustering': {
        'decrease': "Reduce bidder coordination patterns — ensure independent bid preparation / Намалете ги обрасците на координација на понудувачите",
    },
    'short_deadline': {
        'decrease': "Extend tender deadline to standard timeframe (minimum 15 days) / Продолжете го рокот на тендерот до стандарден временски рок",
    },
    'identical_bids': {
        'decrease': "Eliminate identical bid values — investigate independent pricing / Елиминирајте идентични понуди",
    },
    'professional_loser': {
        'decrease': "Address professional-loser bidding patterns / Адресирајте ги обрасците на професионален губитник",
    },
    'contract_splitting': {
        'decrease': "Consolidate related procurements to avoid contract splitting / Консолидирајте ги поврзаните набавки",
    },
    'short_decision': {
        'decrease': "Allow adequate time for evaluation and decision making / Обезбедете адекватно време за евалуација",
    },
    'strategic_disqualification': {
        'decrease': "Review disqualification criteria for fairness / Прегледајте ги критериумите за дисквалификација",
    },
    'contract_value_growth': {
        'decrease': "Control contract value growth through better initial estimates / Контролирајте го растот на вредноста на договорите",
    },
    'bid_rotation': {
        'decrease': "Break bid rotation patterns by attracting new bidders / Прекинете ги обрасците на ротација на понуди",
    },
    'threshold_manipulation': {
        'decrease': "Ensure contract values are not artificially adjusted near thresholds / Обезбедете вредностите да не се манипулирани околу прагови",
    },
    'late_amendment': {
        'decrease': "Issue amendments well before the submission deadline / Издавајте амандмани добро пред крајниот рок",
    },
    'num_bidders': {
        'increase': "Increase the number of bidders through wider tender publication / Зголемете го бројот на понудувачи",
    },
    'procedure_type': {
        'info': "Procedure type is fixed and cannot be changed post-publication / Видот на постапка е фиксен",
    },
    'estimated_value_mkd': {
        'info': "Estimated value is fixed and cannot be changed / Проценетата вредност е фиксна",
    },
}


class CounterfactualEngine:
    """Generate counterfactual explanations for corruption risk scores.

    Answers: "What would need to change for this tender to NOT be flagged as high-risk?"
    Uses genetic algorithm approach to find minimal changes to features that would
    lower the risk score below a threshold.
    """

    # Feature definitions with constraints
    FEATURE_DEFS: Dict[str, Dict[str, Any]] = {
        'single_bidder': {'type': 'binary', 'mutable': True, 'direction': 'decrease'},
        'repeat_winner': {'type': 'continuous', 'range': (0, 100), 'mutable': True, 'direction': 'decrease'},
        'price_anomaly': {'type': 'continuous', 'range': (0, 100), 'mutable': True, 'direction': 'decrease'},
        'bid_clustering': {'type': 'continuous', 'range': (0, 100), 'mutable': True, 'direction': 'decrease'},
        'short_deadline': {'type': 'binary', 'mutable': True, 'direction': 'decrease'},
        'procedure_type': {'type': 'categorical', 'mutable': False},  # immutable
        'identical_bids': {'type': 'binary', 'mutable': True, 'direction': 'decrease'},
        'professional_loser': {'type': 'continuous', 'range': (0, 100), 'mutable': True, 'direction': 'decrease'},
        'contract_splitting': {'type': 'binary', 'mutable': True, 'direction': 'decrease'},
        'short_decision': {'type': 'binary', 'mutable': True, 'direction': 'decrease'},
        'strategic_disqualification': {'type': 'binary', 'mutable': True, 'direction': 'decrease'},
        'contract_value_growth': {'type': 'continuous', 'range': (0, 100), 'mutable': True, 'direction': 'decrease'},
        'bid_rotation': {'type': 'continuous', 'range': (0, 100), 'mutable': True, 'direction': 'decrease'},
        'threshold_manipulation': {'type': 'binary', 'mutable': True, 'direction': 'decrease'},
        'late_amendment': {'type': 'binary', 'mutable': True, 'direction': 'decrease'},
        'num_bidders': {'type': 'integer', 'range': (1, 50), 'mutable': True, 'direction': 'increase'},
        'estimated_value_mkd': {'type': 'continuous', 'range': (0, 1e12), 'mutable': False},  # immutable
    }

    def __init__(
        self,
        target_score: float = 30.0,
        population_size: int = 50,
        generations: int = 100,
        mutation_rate: float = 0.3,
        diversity_weight: float = 0.5,
    ):
        """
        Args:
            target_score: Risk score threshold below which a tender is considered low-risk (0-100).
            population_size: Number of candidate counterfactuals per generation.
            generations: Number of evolutionary generations.
            mutation_rate: Probability of mutating each mutable feature.
            diversity_weight: Weight for the diversity bonus in fitness evaluation.
        """
        self.target_score = target_score
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.diversity_weight = diversity_weight

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        original_features: Dict[str, Any],
        original_score: float,
        score_fn: Optional[Callable[[Dict[str, Any]], float]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Generate top_k diverse counterfactual explanations.

        Args:
            original_features: dict of feature_name -> value for the tender.
            original_score: current risk score (0-100).
            score_fn: optional custom scoring function. If None, uses weighted CRI average.
            top_k: number of counterfactuals to return.

        Returns:
            List of dicts, each containing:
            - changed_features: {feature: {'from': old, 'to': new, 'description': str}}
            - counterfactual_score: predicted new score
            - distance: L1 distance from original (normalized)
            - feasibility: 0-1 feasibility score
            - num_changes: number of features changed
        """
        if score_fn is None:
            score_fn = self._default_score_fn

        # If the original score is already below the target, return empty
        if original_score <= self.target_score:
            logger.info(
                f"Original score {original_score} is already below target {self.target_score}. "
                "No counterfactuals needed."
            )
            return []

        # 1. Initialize population
        population = self._initialize_population(original_features)

        # 2. Evolve
        for gen in range(self.generations):
            # Evaluate fitness for every candidate
            scored = []
            for candidate in population:
                cf_score = score_fn(candidate)
                dist = self._distance(original_features, candidate)
                feas = self._feasibility_score(original_features, candidate)
                fitness = self._fitness(cf_score, dist, feas, original_score)
                scored.append((candidate, cf_score, dist, feas, fitness))

            # Sort by fitness descending
            scored.sort(key=lambda x: x[4], reverse=True)

            # Early termination if we have enough good candidates
            valid_count = sum(1 for _, cs, _, _, _ in scored if cs < self.target_score)
            if valid_count >= top_k * 3 and gen > self.generations // 3:
                logger.debug(f"Early termination at generation {gen} with {valid_count} valid candidates")
                break

            # Select next generation via tournament
            next_gen = []

            # Elitism: keep top 10% unchanged
            elite_count = max(2, self.population_size // 10)
            for i in range(min(elite_count, len(scored))):
                next_gen.append(scored[i][0])

            # Fill rest with crossover + mutation
            while len(next_gen) < self.population_size:
                p1 = self._tournament_select(scored)
                p2 = self._tournament_select(scored)
                child = self._crossover(p1, p2)
                child = self._mutate(child, original_features)
                child = self._enforce_constraints(child, original_features)
                next_gen.append(child)

            population = next_gen

        # 3. Final evaluation of all candidates
        all_candidates = []
        for candidate in population:
            cf_score = score_fn(candidate)
            dist = self._distance(original_features, candidate)
            feas = self._feasibility_score(original_features, candidate)
            n_changes = self._count_changes(original_features, candidate)

            if cf_score < self.target_score and n_changes > 0:
                changed = self._extract_changes(original_features, candidate)
                all_candidates.append({
                    'changed_features': changed,
                    'counterfactual_score': round(cf_score, 2),
                    'distance': round(dist, 4),
                    'feasibility': round(feas, 4),
                    'num_changes': n_changes,
                })

        if not all_candidates:
            logger.warning("No valid counterfactuals found below target score. Returning best efforts.")
            # Return best-effort candidates (lowest scores even if above threshold)
            scored_final = []
            for candidate in population:
                cf_score = score_fn(candidate)
                dist = self._distance(original_features, candidate)
                feas = self._feasibility_score(original_features, candidate)
                n_changes = self._count_changes(original_features, candidate)
                if n_changes > 0:
                    changed = self._extract_changes(original_features, candidate)
                    scored_final.append({
                        'changed_features': changed,
                        'counterfactual_score': round(cf_score, 2),
                        'distance': round(dist, 4),
                        'feasibility': round(feas, 4),
                        'num_changes': n_changes,
                    })
            scored_final.sort(key=lambda x: x['counterfactual_score'])
            return scored_final[:top_k]

        # 4. Rank by distance (prefer minimal changes), then diversify
        all_candidates.sort(key=lambda x: (x['num_changes'], x['distance']))

        # 5. Diversify: ensure returned set covers different feature change combinations
        diversified = self._diversify(all_candidates, top_k)

        return diversified

    def get_actionable_changes(self, counterfactuals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter to only actionable/feasible changes and add human-readable descriptions.

        Args:
            counterfactuals: List of counterfactual dicts from generate().

        Returns:
            Filtered list with only feasibility > 0.6 and enriched descriptions.
        """
        actionable = []
        for cf in counterfactuals:
            if cf['feasibility'] < 0.6:
                continue

            enriched_changes = {}
            for feature, change_info in cf['changed_features'].items():
                feat_def = self.FEATURE_DEFS.get(feature, {})
                if not feat_def.get('mutable', True):
                    continue

                direction = self._change_direction(change_info['from'], change_info['to'])
                desc_map = CHANGE_DESCRIPTIONS.get(feature, {})
                description = desc_map.get(direction, change_info.get('description', ''))

                enriched_changes[feature] = {
                    'from': change_info['from'],
                    'to': change_info['to'],
                    'description': description,
                    'direction': direction,
                    'actionable': True,
                }

            if enriched_changes:
                actionable.append({
                    'changed_features': enriched_changes,
                    'counterfactual_score': cf['counterfactual_score'],
                    'distance': cf['distance'],
                    'feasibility': cf['feasibility'],
                    'num_changes': len(enriched_changes),
                })

        return actionable

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _default_score_fn(self, features: Dict[str, Any]) -> float:
        """Score a feature vector using weighted CRI calculation.

        Mirrors the CRI formula from backend/api/corruption.py:
            base_score = sum(score * weight) / sum(weight)   for active flags
            bonus = 8 * (num_active_types - 1)               if > 1 type
            risk_score = min(100, base_score + bonus)
        """
        type_max_scores: Dict[str, Tuple[float, float]] = {}

        for flag_type, weight in CRI_WEIGHTS.items():
            value = features.get(flag_type)
            if value is None:
                continue

            # Binary flags: treat > 0.5 as active with score based on value
            feat_def = self.FEATURE_DEFS.get(flag_type, {})
            if feat_def.get('type') == 'binary':
                score = float(value) * 100.0  # 1 -> 100, 0 -> 0
            else:
                score = float(value)  # continuous: already 0-100

            if score > 0:
                existing = type_max_scores.get(flag_type, (0.0, 0.0))
                if score > existing[0]:
                    type_max_scores[flag_type] = (score, weight)

        if not type_max_scores:
            return 0.0

        total_ws = sum(s * w for s, w in type_max_scores.values())
        total_w = sum(w for _, w in type_max_scores.values())
        base_score = total_ws / total_w if total_w > 0.0 else 0.0

        num_types = len(type_max_scores)
        bonus = 8.0 * (num_types - 1) if num_types > 1 else 0.0

        # num_bidders influence: fewer bidders increases risk slightly
        num_bidders = features.get('num_bidders')
        if num_bidders is not None and num_bidders >= 1:
            # With many bidders the single_bidder flag should already be 0,
            # but we add a small reduction for having many bidders
            if num_bidders >= 5:
                base_score *= 0.90
            elif num_bidders >= 3:
                base_score *= 0.95

        return min(100.0, base_score + bonus)

    # ------------------------------------------------------------------
    # Genetic Algorithm Internals
    # ------------------------------------------------------------------

    def _initialize_population(self, original: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create initial population by randomly mutating the original features."""
        population = []
        for _ in range(self.population_size):
            candidate = copy.deepcopy(original)
            # Apply between 1 and 5 random mutations
            n_mutations = random.randint(1, min(5, len(self.FEATURE_DEFS)))
            mutable_keys = [
                k for k, v in self.FEATURE_DEFS.items()
                if v.get('mutable', False) and k in original
            ]
            if not mutable_keys:
                population.append(candidate)
                continue

            chosen = random.sample(mutable_keys, min(n_mutations, len(mutable_keys)))
            for feat in chosen:
                candidate[feat] = self._random_value(feat, original.get(feat))

            population.append(candidate)
        return population

    def _mutate(self, features: Dict[str, Any], original: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Mutate a feature vector respecting constraints.

        Each mutable feature is mutated with probability self.mutation_rate.
        """
        mutated = copy.deepcopy(features)
        for feat, feat_def in self.FEATURE_DEFS.items():
            if feat not in mutated:
                continue
            if not feat_def.get('mutable', False):
                continue
            if random.random() > self.mutation_rate:
                continue

            orig_val = original.get(feat) if original else mutated.get(feat)
            mutated[feat] = self._random_value(feat, orig_val)

        return mutated

    def _crossover(self, parent1: Dict[str, Any], parent2: Dict[str, Any]) -> Dict[str, Any]:
        """Uniform crossover between two feature vectors.

        For each feature, randomly pick from parent1 or parent2.
        """
        child = {}
        all_keys = set(parent1.keys()) | set(parent2.keys())
        for key in all_keys:
            if key in parent1 and key in parent2:
                child[key] = parent1[key] if random.random() < 0.5 else parent2[key]
            elif key in parent1:
                child[key] = parent1[key]
            else:
                child[key] = parent2[key]
        return child

    def _tournament_select(
        self,
        scored: List[Tuple[Dict, float, float, float, float]],
        tournament_size: int = 3,
    ) -> Dict[str, Any]:
        """Tournament selection: pick the best from a random subset."""
        contestants = random.sample(scored, min(tournament_size, len(scored)))
        winner = max(contestants, key=lambda x: x[4])  # x[4] = fitness
        return copy.deepcopy(winner[0])

    def _enforce_constraints(
        self, candidate: Dict[str, Any], original: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ensure candidate respects all feature constraints."""
        for feat, feat_def in self.FEATURE_DEFS.items():
            if feat not in candidate:
                continue

            # Immutable features must stay unchanged
            if not feat_def.get('mutable', False):
                if feat in original:
                    candidate[feat] = original[feat]
                continue

            ftype = feat_def.get('type', 'continuous')
            val = candidate[feat]

            if ftype == 'binary':
                # Clamp to 0 or 1
                candidate[feat] = 1 if val > 0.5 else 0

            elif ftype == 'integer':
                rng = feat_def.get('range', (0, 100))
                candidate[feat] = max(rng[0], min(rng[1], int(round(val))))

            elif ftype == 'continuous':
                rng = feat_def.get('range', (0, 100))
                candidate[feat] = max(rng[0], min(rng[1], float(val)))

            # Directional constraint: only allow changes in the preferred direction
            direction = feat_def.get('direction')
            if direction and feat in original:
                orig_val = original[feat]
                new_val = candidate[feat]
                if direction == 'decrease' and new_val > orig_val:
                    candidate[feat] = orig_val
                elif direction == 'increase' and new_val < orig_val:
                    candidate[feat] = orig_val

        return candidate

    def _random_value(self, feature: str, original_value: Any) -> Any:
        """Generate a random value for a feature respecting its definition."""
        feat_def = self.FEATURE_DEFS.get(feature, {})
        ftype = feat_def.get('type', 'continuous')
        direction = feat_def.get('direction')

        if ftype == 'binary':
            if direction == 'decrease':
                return 0  # Always try to turn off risk flags
            elif direction == 'increase':
                return 1
            return random.choice([0, 1])

        elif ftype == 'integer':
            rng = feat_def.get('range', (1, 50))
            if direction == 'increase' and original_value is not None:
                # Generate values above the original
                low = max(rng[0], int(original_value))
                return random.randint(low, rng[1])
            elif direction == 'decrease' and original_value is not None:
                high = min(rng[1], int(original_value))
                return random.randint(rng[0], high)
            return random.randint(rng[0], rng[1])

        elif ftype == 'continuous':
            rng = feat_def.get('range', (0, 100))
            if direction == 'decrease' and original_value is not None:
                # Generate values below original
                high = min(rng[1], float(original_value))
                return random.uniform(rng[0], high)
            elif direction == 'increase' and original_value is not None:
                low = max(rng[0], float(original_value))
                return random.uniform(low, rng[1])
            return random.uniform(rng[0], rng[1])

        # Categorical or unknown: return original
        return original_value

    # ------------------------------------------------------------------
    # Fitness & Distance
    # ------------------------------------------------------------------

    def _fitness(
        self, cf_score: float, distance: float, feasibility: float, original_score: float
    ) -> float:
        """Compute fitness of a counterfactual candidate.

        Higher fitness is better. Components:
        - Score reduction: how much the score dropped (want large drop)
        - Distance penalty: prefer minimal changes
        - Feasibility bonus: prefer realistic changes
        - Below-threshold bonus: big reward for getting below target
        """
        score_reduction = original_score - cf_score  # Positive is good
        below_threshold_bonus = 20.0 if cf_score < self.target_score else 0.0

        fitness = (
            score_reduction * 1.0
            + below_threshold_bonus
            - distance * 10.0  # Penalize large changes
            + feasibility * 5.0  # Reward feasible changes
        )
        return fitness

    def _distance(self, original: Dict[str, Any], counterfactual: Dict[str, Any]) -> float:
        """Normalized L1 distance between feature vectors.

        Each feature's change is normalized to [0, 1] based on its range.
        """
        total_distance = 0.0
        n_features = 0

        for feat, feat_def in self.FEATURE_DEFS.items():
            if feat not in original or feat not in counterfactual:
                continue
            if not feat_def.get('mutable', False):
                continue

            orig_val = float(original[feat]) if original[feat] is not None else 0.0
            cf_val = float(counterfactual[feat]) if counterfactual[feat] is not None else 0.0

            ftype = feat_def.get('type', 'continuous')

            if ftype == 'binary':
                total_distance += abs(orig_val - cf_val)
            elif ftype in ('continuous', 'integer'):
                rng = feat_def.get('range', (0, 100))
                span = rng[1] - rng[0]
                if span > 0:
                    total_distance += abs(orig_val - cf_val) / span
                else:
                    total_distance += abs(orig_val - cf_val)
            n_features += 1

        return total_distance / n_features if n_features > 0 else 0.0

    def _feasibility_score(self, original: Dict[str, Any], counterfactual: Dict[str, Any]) -> float:
        """How feasible are the proposed changes? (0=infeasible, 1=easy).

        Factors:
        - Binary flags turning off: high feasibility (concrete action to take)
        - Large continuous drops: lower feasibility
        - num_bidders increase: moderate feasibility (depends on market)
        - Immutable features changed: score 0 (should not happen)
        """
        feasibility_scores = []

        for feat, feat_def in self.FEATURE_DEFS.items():
            if feat not in original or feat not in counterfactual:
                continue

            orig_val = float(original[feat]) if original[feat] is not None else 0.0
            cf_val = float(counterfactual[feat]) if counterfactual[feat] is not None else 0.0

            if abs(orig_val - cf_val) < 1e-9:
                continue  # No change

            if not feat_def.get('mutable', False):
                return 0.0  # Any immutable change makes the whole CF infeasible

            ftype = feat_def.get('type', 'continuous')

            if ftype == 'binary':
                # Turning off a binary risk flag is generally feasible
                if orig_val > 0.5 and cf_val < 0.5:
                    feasibility_scores.append(0.8)
                else:
                    feasibility_scores.append(0.5)

            elif ftype == 'integer':
                # num_bidders: small increases are more feasible than large ones
                if feat == 'num_bidders':
                    change = cf_val - orig_val
                    if change <= 2:
                        feasibility_scores.append(0.9)
                    elif change <= 5:
                        feasibility_scores.append(0.7)
                    elif change <= 10:
                        feasibility_scores.append(0.5)
                    else:
                        feasibility_scores.append(0.3)
                else:
                    feasibility_scores.append(0.6)

            elif ftype == 'continuous':
                rng = feat_def.get('range', (0, 100))
                span = rng[1] - rng[0]
                if span > 0:
                    relative_change = abs(orig_val - cf_val) / span
                    # Small changes are more feasible
                    feasibility_scores.append(max(0.1, 1.0 - relative_change))
                else:
                    feasibility_scores.append(0.5)

        if not feasibility_scores:
            return 1.0  # No changes = perfectly feasible (but also useless)

        return sum(feasibility_scores) / len(feasibility_scores)

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _count_changes(self, original: Dict[str, Any], candidate: Dict[str, Any]) -> int:
        """Count number of features that differ between original and candidate."""
        count = 0
        for feat in self.FEATURE_DEFS:
            if feat not in original or feat not in candidate:
                continue
            orig_val = original[feat]
            cand_val = candidate[feat]
            if orig_val is None and cand_val is None:
                continue
            if orig_val is None or cand_val is None:
                count += 1
                continue
            feat_def = self.FEATURE_DEFS[feat]
            if feat_def.get('type') == 'binary':
                if int(round(float(orig_val))) != int(round(float(cand_val))):
                    count += 1
            elif feat_def.get('type') == 'integer':
                if int(round(float(orig_val))) != int(round(float(cand_val))):
                    count += 1
            else:
                if abs(float(orig_val) - float(cand_val)) > 0.5:
                    count += 1
        return count

    def _extract_changes(
        self, original: Dict[str, Any], candidate: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Extract the changed features with from/to values and descriptions."""
        changes = {}
        for feat, feat_def in self.FEATURE_DEFS.items():
            if feat not in original or feat not in candidate:
                continue
            if not feat_def.get('mutable', False):
                continue

            orig_val = original[feat]
            cand_val = candidate[feat]

            if orig_val is None and cand_val is None:
                continue

            changed = False
            ftype = feat_def.get('type', 'continuous')
            if ftype == 'binary':
                changed = int(round(float(orig_val or 0))) != int(round(float(cand_val or 0)))
            elif ftype == 'integer':
                changed = int(round(float(orig_val or 0))) != int(round(float(cand_val or 0)))
            else:
                changed = abs(float(orig_val or 0) - float(cand_val or 0)) > 0.5

            if not changed:
                continue

            # Format values for readability
            if ftype == 'binary':
                from_val = int(round(float(orig_val or 0)))
                to_val = int(round(float(cand_val or 0)))
            elif ftype == 'integer':
                from_val = int(round(float(orig_val or 0)))
                to_val = int(round(float(cand_val or 0)))
            else:
                from_val = round(float(orig_val or 0), 1)
                to_val = round(float(cand_val or 0), 1)

            direction = self._change_direction(from_val, to_val)
            desc_map = CHANGE_DESCRIPTIONS.get(feat, {})
            description = desc_map.get(direction, self._auto_description(feat, from_val, to_val))

            changes[feat] = {
                'from': from_val,
                'to': to_val,
                'description': description,
            }

        return changes

    def _change_direction(self, from_val: Any, to_val: Any) -> str:
        """Determine the direction of a change."""
        try:
            fv = float(from_val)
            tv = float(to_val)
            if tv < fv:
                return 'decrease'
            elif tv > fv:
                return 'increase'
            return 'unchanged'
        except (TypeError, ValueError):
            return 'changed'

    def _auto_description(self, feature: str, from_val: Any, to_val: Any) -> str:
        """Generate automatic description for a feature change."""
        feat_def = self.FEATURE_DEFS.get(feature, {})
        ftype = feat_def.get('type', 'continuous')
        name = feature.replace('_', ' ').title()

        if ftype == 'binary':
            if from_val == 1 and to_val == 0:
                return f"Remove {name} flag"
            elif from_val == 0 and to_val == 1:
                return f"Set {name} flag"
        elif ftype == 'integer':
            return f"Change {name} from {from_val} to {to_val}"
        else:
            return f"Reduce {name} score from {from_val} to {to_val}"

        return f"Change {name} from {from_val} to {to_val}"

    def _diversify(self, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """Select a diverse subset of candidates.

        Uses a greedy approach: pick the best, then iteratively pick candidates
        that are most different from the already-selected set.
        """
        if len(candidates) <= top_k:
            return candidates

        selected = [candidates[0]]
        remaining = candidates[1:]

        while len(selected) < top_k and remaining:
            best_idx = 0
            best_diversity = -1.0

            for i, cand in enumerate(remaining):
                # Compute minimum Jaccard distance to any selected candidate
                min_similarity = 1.0
                cand_keys = set(cand['changed_features'].keys())
                for sel in selected:
                    sel_keys = set(sel['changed_features'].keys())
                    if cand_keys or sel_keys:
                        intersection = len(cand_keys & sel_keys)
                        union = len(cand_keys | sel_keys)
                        similarity = intersection / union if union > 0 else 1.0
                        min_similarity = min(min_similarity, similarity)

                diversity = 1.0 - min_similarity
                # Combined score: diversity + feasibility bonus
                combined = diversity * self.diversity_weight + cand['feasibility'] * (1 - self.diversity_weight)

                if combined > best_diversity:
                    best_diversity = combined
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

"""
Bracket Matcher V3.1 - Targeted fixes

Changes from V3:
- FIX: Unmatched wrestlers actually returned (was always returning [])
- FIX: Isolation-based ordering in ALL phases, not just strict
- FIX: Isolation scores recalculated after each bracket (pool shrinks)
- FIX: Straggler absorption has weight ceiling (was unlimited)
- FIX: bracket_size parameter respected

CORE PHILOSOPHY (unchanged):
1. School diversity is SACRED - max 2 from same school per bracket
2. Grade is IMPORTANT - ±2 default, ±3 emergency only
3. Weight is FLEXIBLE - up to 44lbs for good grade matches
4. Process HARD cases first via Isolation Score
"""

from collections import Counter
from statistics import median
from dataclasses import dataclass
from models import Wrestler, Bracket, ConstraintRelaxation


@dataclass
class CompatibilityResult:
    wrestlers: list
    weight_spread: float
    grade_spread: int
    max_same_school: int
    school_count: int

    @property
    def violations(self) -> list[ConstraintRelaxation]:
        v = []
        if self.weight_spread > 10.0:
            v.append(ConstraintRelaxation.WEIGHT)
        if self.grade_spread > 2:
            v.append(ConstraintRelaxation.GRADE)
        if self.max_same_school > 1:
            v.append(ConstraintRelaxation.SCHOOL)
        return v


class BracketMatcherV3:

    MAX_WEIGHT_STRICT = 10.0
    MAX_WEIGHT_RELAXED = 44.0
    MAX_GRADE = 2
    MAX_GRADE_EMERGENCY = 3

    def __init__(self, wrestlers: list[Wrestler], bracket_size: int = 4):
        self.wrestlers = wrestlers
        self.bracket_size = bracket_size
        self.brackets: list[Bracket] = []
        self.unmatched: list[Wrestler] = []

    def _analyze(self, wrestlers: list[Wrestler]) -> CompatibilityResult:
        weights = [w.weight for w in wrestlers]
        grades = [w.grade for w in wrestlers]
        schools = Counter(w.school for w in wrestlers)

        return CompatibilityResult(
            wrestlers=wrestlers,
            weight_spread=max(weights) - min(weights),
            grade_spread=max(grades) - min(grades),
            max_same_school=max(schools.values()),
            school_count=len(schools)
        )

    def _calculate_isolation(self, wrestler: Wrestler, pool: list[Wrestler], max_weight: float) -> float:
        """
        Calculate how hard this wrestler is to place at the given weight tolerance.
        Higher = more isolated = process first.
        """
        grade_compatible = [
            w for w in pool
            if w.id != wrestler.id and abs(w.grade - wrestler.grade) <= 1
        ]

        if not grade_compatible:
            return 1000.0

        weight_compatible = [
            w for w in grade_compatible
            if abs(w.weight - wrestler.weight) <= max_weight
        ]

        same_grade = [w for w in pool if w.grade == wrestler.grade and w.id != wrestler.id]
        if same_grade:
            weights = [w.weight for w in same_grade]
            weight_deviation = abs(wrestler.weight - median(weights))
        else:
            weight_deviation = 50

        # Fewer compatible wrestlers = higher isolation
        compat_factor = max(0, 10 - len(weight_compatible)) * 15
        deviation_factor = weight_deviation * 0.5

        return compat_factor + deviation_factor

    def _find_partners(
        self,
        seed: Wrestler,
        pool: list[Wrestler],
        target_size: int,
        max_weight: float,
        max_grade: int = 1,
        max_same_school: int = 2
    ) -> list[Wrestler] | None:
        group = [seed]
        candidates = [w for w in pool if w.id != seed.id]
        used_schools = Counter([seed.school])

        while len(group) < target_size and candidates:
            best = None
            best_score = float('inf')

            for c in candidates:
                test_group = group + [c]
                result = self._analyze(test_group)

                if result.weight_spread > max_weight:
                    continue
                if result.grade_spread > max_grade:
                    continue
                if result.max_same_school > max_same_school:
                    continue

                score = 0

                if c.school in used_schools:
                    score += 1000
                else:
                    score -= 100

                score += result.grade_spread * 100
                score += result.weight_spread * 1

                if score < best_score:
                    best_score = score
                    best = c

            if best is None:
                break

            group.append(best)
            used_schools[best.school] += 1
            candidates.remove(best)

        return group if len(group) >= target_size else None

    def _find_best_bracket_isolated(
        self,
        pool: list[Wrestler],
        target_size: int,
        max_weight: float,
        max_grade: int = 1,
        max_same_school: int = 2
    ) -> list[Wrestler] | None:
        """
        Find best bracket, trying the most isolated wrestlers as seeds first.
        Returns the first valid bracket found from the most isolated seed,
        which ensures outliers get placed while partners are still available.
        """
        isolation_scores = {
            w.id: self._calculate_isolation(w, pool, max_weight)
            for w in pool
        }
        sorted_pool = sorted(pool, key=lambda w: isolation_scores[w.id], reverse=True)

        for seed in sorted_pool:
            group = self._find_partners(
                seed, pool, target_size,
                max_weight, max_grade, max_same_school
            )

            if group and len(group) == target_size:
                return group

        return None

    def match_all(self, num_mats: int = 3) -> tuple[list[Bracket], list[Wrestler]]:
        available = self.wrestlers.copy()
        brackets = []
        bracket_id = 0
        target = self.bracket_size
        small_target = max(3, target - 1)

        # Phase 0: Identify extreme outliers (zero strict-range matches)
        # and form their brackets first while partners are available
        outliers = []
        for w in available:
            strict_matches = [
                p for p in available
                if p.id != w.id
                and abs(p.grade - w.grade) <= self.MAX_GRADE
                and abs(p.weight - w.weight) <= self.MAX_WEIGHT_STRICT
            ]
            if len(strict_matches) < target - 1:
                outliers.append(w)

        # Sort outliers by isolation (most isolated first)
        if outliers:
            outlier_isolation = {
                w.id: self._calculate_isolation(w, available, self.MAX_WEIGHT_RELAXED)
                for w in outliers
            }
            outliers.sort(key=lambda w: outlier_isolation[w.id], reverse=True)

            for seed in outliers:
                if seed not in available or len(available) < target:
                    continue

                # Try progressive relaxation for this outlier
                for max_weight in [25.0, self.MAX_WEIGHT_RELAXED]:
                    for max_grade in [self.MAX_GRADE, self.MAX_GRADE_EMERGENCY]:
                        group = self._find_partners(
                            seed, available, target,
                            max_weight=max_weight,
                            max_grade=max_grade,
                            max_same_school=2
                        )

                        if group:
                            result = self._analyze(group)
                            brackets.append(Bracket(
                                id=bracket_id,
                                wrestlers=group,
                                relaxations=result.violations
                            ))
                            bracket_id += 1
                            for w in group:
                                available.remove(w)
                            break
                    else:
                        continue
                    break

        # Phase 1: STRICT constraints - isolation-prioritized
        while len(available) >= target:
            group = self._find_best_bracket_isolated(
                available, target,
                max_weight=self.MAX_WEIGHT_STRICT,
                max_grade=self.MAX_GRADE,
                max_same_school=2
            )

            if not group:
                break

            result = self._analyze(group)
            brackets.append(Bracket(
                id=bracket_id,
                wrestlers=group,
                relaxations=result.violations
            ))
            bracket_id += 1
            for w in group:
                available.remove(w)

        # Phase 2: Weight up to 25lbs - isolation-prioritized
        while len(available) >= target:
            group = self._find_best_bracket_isolated(
                available, target,
                max_weight=25.0,
                max_grade=self.MAX_GRADE,
                max_same_school=2
            )

            if not group:
                break

            result = self._analyze(group)
            brackets.append(Bracket(
                id=bracket_id,
                wrestlers=group,
                relaxations=result.violations
            ))
            bracket_id += 1
            for w in group:
                available.remove(w)

        # Phase 3: Weight up to 44lbs - isolation-prioritized
        while len(available) >= target:
            group = self._find_best_bracket_isolated(
                available, target,
                max_weight=self.MAX_WEIGHT_RELAXED,
                max_grade=self.MAX_GRADE,
                max_same_school=2
            )

            if not group:
                break

            result = self._analyze(group)
            brackets.append(Bracket(
                id=bracket_id,
                wrestlers=group,
                relaxations=result.violations
            ))
            bracket_id += 1
            for w in group:
                available.remove(w)

        # Phase 4: Emergency grade ±2 for full-size brackets
        while len(available) >= target:
            group = self._find_best_bracket_isolated(
                available, target,
                max_weight=self.MAX_WEIGHT_RELAXED,
                max_grade=self.MAX_GRADE_EMERGENCY,
                max_same_school=2
            )

            if not group:
                break

            result = self._analyze(group)
            brackets.append(Bracket(
                id=bracket_id,
                wrestlers=group,
                relaxations=result.violations
            ))
            bracket_id += 1
            for w in group:
                available.remove(w)

        # Phase 5: Smaller brackets with progressive weight relaxation
        if target > 3:
            for max_weight in [self.MAX_WEIGHT_STRICT, 25.0, self.MAX_WEIGHT_RELAXED]:
                while len(available) >= small_target:
                    group = self._find_best_bracket_isolated(
                        available, small_target,
                        max_weight=max_weight,
                        max_grade=self.MAX_GRADE,
                        max_same_school=2
                    )

                    if not group:
                        break

                    result = self._analyze(group)
                    brackets.append(Bracket(
                        id=bracket_id,
                        wrestlers=group,
                        relaxations=result.violations
                    ))
                    bracket_id += 1
                    for w in group:
                        available.remove(w)

            # Phase 6: Smaller brackets with grade relaxation
            while len(available) >= small_target:
                group = self._find_best_bracket_isolated(
                    available, small_target,
                    max_weight=self.MAX_WEIGHT_RELAXED,
                    max_grade=self.MAX_GRADE_EMERGENCY,
                    max_same_school=2
                )

                if not group:
                    break

                result = self._analyze(group)
                brackets.append(Bracket(
                    id=bracket_id,
                    wrestlers=group,
                    relaxations=result.violations
                ))
                bracket_id += 1
                for w in group:
                    available.remove(w)

        # Phase 7: Absorb stragglers into best-fit existing brackets
        # Score all remaining wrestlers against all non-full brackets,
        # pick the globally best fit each iteration
        while available:
            best_wrestler = None
            best_bracket = None
            best_score = float('inf')

            for wrestler in available:
                for b in brackets:
                    if len(b.wrestlers) >= target:
                        continue

                    test_group = b.wrestlers + [wrestler]
                    result = self._analyze(test_group)

                    if result.grade_spread > self.MAX_GRADE_EMERGENCY:
                        continue
                    if result.max_same_school > 2:
                        continue
                    # Weight ceiling on absorption - don't create absurd brackets
                    if result.weight_spread > self.MAX_WEIGHT_RELAXED:
                        continue

                    score = (
                        (result.max_same_school - 1) * 1000 +
                        result.grade_spread * 100 +
                        result.weight_spread * 1 +
                        len(b.wrestlers) * 10
                    )

                    if score < best_score:
                        best_score = score
                        best_wrestler = wrestler
                        best_bracket = b

            if best_wrestler and best_bracket:
                best_bracket.wrestlers.append(best_wrestler)
                best_bracket.relaxations = self._analyze(best_bracket.wrestlers).violations
                available.remove(best_wrestler)
            else:
                break

        # Phase 8: Redistribution
        # If stragglers remain and all brackets are full, try to accommodate them
        # by converting some 4-person brackets into 3-person brackets
        if available:
            # Try each unmatched wrestler individually
            still_unmatched = []
            for unmatched_w in list(available):
                placed = False

                # First: try absorbing into a non-full bracket (shouldn't exist but safety check)
                for b in brackets:
                    if len(b.wrestlers) >= target:
                        continue
                    test_group = b.wrestlers + [unmatched_w]
                    result = self._analyze(test_group)
                    if result.grade_spread <= self.MAX_GRADE_EMERGENCY and result.max_same_school <= 2 and result.weight_spread <= self.MAX_WEIGHT_RELAXED:
                        b.wrestlers.append(unmatched_w)
                        b.relaxations = result.violations
                        placed = True
                        break

                if placed:
                    continue

                # Second: find a 4-person bracket where we can pull 1 wrestler,
                # and that pulled wrestler + unmatched wrestler can join another
                # 3-person bracket (created by pulling from yet another bracket)
                # Simpler: find a bracket we can add this wrestler to if we remove
                # one of its wrestlers, and that removed wrestler fits somewhere else
                best_swap = None
                best_swap_score = float('inf')

                for b in brackets:
                    if len(b.wrestlers) < 4:
                        continue

                    for pull_w in b.wrestlers:
                        remaining = [w for w in b.wrestlers if w.id != pull_w.id]
                        new_bracket = remaining + [unmatched_w]
                        result = self._analyze(new_bracket)

                        if result.grade_spread > self.MAX_GRADE_EMERGENCY:
                            continue
                        if result.max_same_school > 2:
                            continue
                        if result.weight_spread > self.MAX_WEIGHT_RELAXED:
                            continue

                        # Can the pulled wrestler go into another non-full bracket?
                        for other_b in brackets:
                            if other_b.id == b.id or len(other_b.wrestlers) >= target:
                                continue
                            test = other_b.wrestlers + [pull_w]
                            other_result = self._analyze(test)
                            if other_result.grade_spread <= self.MAX_GRADE_EMERGENCY and other_result.max_same_school <= 2 and other_result.weight_spread <= self.MAX_WEIGHT_RELAXED:
                                score = result.weight_spread + other_result.weight_spread
                                if score < best_swap_score:
                                    best_swap_score = score
                                    best_swap = (b, pull_w, unmatched_w, other_b)

                if best_swap:
                    src_bracket, pulled, newcomer, dest_bracket = best_swap
                    src_bracket.wrestlers.remove(pulled)
                    src_bracket.wrestlers.append(newcomer)
                    src_bracket.relaxations = self._analyze(src_bracket.wrestlers).violations
                    dest_bracket.wrestlers.append(pulled)
                    dest_bracket.relaxations = self._analyze(dest_bracket.wrestlers).violations
                else:
                    still_unmatched.append(unmatched_w)

            available = still_unmatched

        self.unmatched = list(available)

        self._assign_mats(brackets, num_mats)
        self.brackets = brackets

        return brackets, self.unmatched

    def _assign_mats(self, brackets: list[Bracket], num_mats: int):
        """Distribute brackets across mats evenly."""
        mat_counts = [0] * num_mats
        for bracket in brackets:
            min_mat = mat_counts.index(min(mat_counts))
            bracket.mat_number = min_mat + 1
            mat_counts[min_mat] += 1

    def get_statistics(self) -> dict:
        if not self.brackets:
            return {}

        total = len(self.brackets)
        sizes = Counter(len(b.wrestlers) for b in self.brackets)

        weight_spreads = []
        grade_spreads = []

        for b in self.brackets:
            if len(b.wrestlers) >= 2:
                weights = [w.weight for w in b.wrestlers]
                grades = [w.grade for w in b.wrestlers]
                weight_spreads.append(max(weights) - min(weights))
                grade_spreads.append(max(grades) - min(grades))

        return {
            'total_brackets': total,
            'unmatched': len(self.unmatched),
            'size_distribution': dict(sizes),
            'no_violations': sum(1 for b in self.brackets if not b.relaxations),
            'weight_relaxed': sum(1 for b in self.brackets if ConstraintRelaxation.WEIGHT in b.relaxations),
            'grade_relaxed': sum(1 for b in self.brackets if ConstraintRelaxation.GRADE in b.relaxations),
            'school_relaxed': sum(1 for b in self.brackets if ConstraintRelaxation.SCHOOL in b.relaxations),
            'avg_weight_spread': sum(weight_spreads) / len(weight_spreads) if weight_spreads else 0,
            'max_weight_spread': max(weight_spreads) if weight_spreads else 0,
            'avg_grade_spread': sum(grade_spreads) / len(grade_spreads) if grade_spreads else 0,
        }


BracketMatcher = BracketMatcherV3

"""
Bracket Matcher V3 - Cleaner Philosophy

CORE PHILOSOPHY:
1. School diversity is SACRED - never allow more than 2 from same school, prioritize throughout
2. Grade is IMPORTANT - never relax beyond ±1 unless absolutely necessary
3. Weight is FLEXIBLE - hand-made brackets accept up to 44lbs for good grade matches
4. Process HARD cases first - wrestlers with few compatible partners get priority

NEW METRIC: "Isolation Score"
- Measures how isolated a wrestler is from potential partners
- High isolation = few compatible wrestlers nearby = process first
- This ensures outliers get matched while there are still options
"""

from collections import Counter
from statistics import median
from dataclasses import dataclass
from models import Wrestler, Bracket, ConstraintRelaxation


@dataclass
class CompatibilityResult:
    """Tracks compatibility metrics for a potential grouping."""
    wrestlers: list
    weight_spread: float
    grade_spread: int
    max_same_school: int
    school_count: int
    
    @property
    def is_strict_valid(self) -> bool:
        """Passes all base constraints."""
        return (
            self.weight_spread <= 10.0 and 
            self.grade_spread <= 1 and 
            self.max_same_school <= 1
        )
    
    @property
    def violations(self) -> list[ConstraintRelaxation]:
        v = []
        if self.weight_spread > 10.0:
            v.append(ConstraintRelaxation.WEIGHT)
        if self.grade_spread > 1:
            v.append(ConstraintRelaxation.GRADE)
        if self.max_same_school > 1:
            v.append(ConstraintRelaxation.SCHOOL)
        return v


class BracketMatcherV3:
    """
    Strict-first bracket matching with isolation-based priority.
    """
    
    MAX_WEIGHT_STRICT = 10.0
    MAX_WEIGHT_RELAXED = 44.0
    MAX_GRADE = 1
    MAX_GRADE_EMERGENCY = 2
    
    def __init__(self, wrestlers: list[Wrestler], bracket_size: int = 4):
        self.wrestlers = wrestlers
        self.bracket_size = bracket_size
        self.brackets: list[Bracket] = []
        self.unmatched: list[Wrestler] = []
    
    def _analyze(self, wrestlers: list[Wrestler]) -> CompatibilityResult:
        """Analyze a group's compatibility."""
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
    
    def _calculate_isolation(self, wrestler: Wrestler, pool: list[Wrestler]) -> float:
        """
        Calculate isolation score - how hard is this wrestler to place?
        Higher = more isolated = process first.
        
        Factors:
        - Few wrestlers in compatible grade range
        - Few wrestlers in compatible weight range within grade
        - Extreme weight for their grade
        """
        # Same grade or adjacent grades
        grade_compatible = [
            w for w in pool 
            if w.id != wrestler.id and abs(w.grade - wrestler.grade) <= 1
        ]
        
        if not grade_compatible:
            return 1000.0  # Completely isolated
        
        # Weight compatible within grade range
        weight_compatible = [
            w for w in grade_compatible
            if abs(w.weight - wrestler.weight) <= self.MAX_WEIGHT_STRICT
        ]
        
        # Weight compatible with relaxation
        weight_relaxed_compatible = [
            w for w in grade_compatible
            if abs(w.weight - wrestler.weight) <= self.MAX_WEIGHT_RELAXED
        ]
        
        # How far from median weight in their grade?
        same_grade = [w for w in pool if w.grade == wrestler.grade]
        if same_grade:
            weights = [w.weight for w in same_grade]
            weight_deviation = abs(wrestler.weight - median(weights))
        else:
            weight_deviation = 50  # No same-grade peers
        
        # Isolation formula:
        # - Fewer strict matches = higher isolation
        # - Fewer relaxed matches = even higher isolation
        # - Higher weight deviation = higher isolation
        
        strict_factor = max(0, 10 - len(weight_compatible)) * 10
        relaxed_factor = max(0, 5 - len(weight_relaxed_compatible)) * 20
        deviation_factor = weight_deviation * 0.5
        
        return strict_factor + relaxed_factor + deviation_factor
    
    def _find_partners(
        self, 
        seed: Wrestler, 
        pool: list[Wrestler], 
        target_size: int,
        max_weight: float,
        max_grade: int = 1,
        max_same_school: int = 2
    ) -> list[Wrestler] | None:
        """Build the best group starting from seed within constraints."""
        group = [seed]
        candidates = [w for w in pool if w.id != seed.id]
        used_schools = Counter([seed.school])
        
        while len(group) < target_size and candidates:
            best = None
            best_score = float('inf')
            
            for c in candidates:
                # Check hard constraints
                test_group = group + [c]
                result = self._analyze(test_group)
                
                if result.weight_spread > max_weight:
                    continue
                if result.grade_spread > max_grade:
                    continue
                if result.max_same_school > max_same_school:
                    continue
                
                # Score this candidate (lower is better)
                # School diversity is the MOST important factor
                score = 0
                
                # School diversity is PRIMARY - heavily penalize same school
                if c.school in used_schools:
                    score += 1000
                else:
                    score -= 100  # Bonus for new school
                
                # Grade spread is secondary
                score += result.grade_spread * 100
                
                # Weight spread is tertiary
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
    
    def _find_best_bracket(
        self,
        pool: list[Wrestler],
        target_size: int,
        max_weight: float,
        max_grade: int = 1,
        max_same_school: int = 2
    ) -> list[Wrestler] | None:
        """Find the best possible bracket from the pool."""
        best_group = None
        best_score = float('inf')
        
        for seed in pool:
            group = self._find_partners(
                seed, pool, target_size, 
                max_weight, max_grade, max_same_school
            )
            
            if group and len(group) == target_size:
                result = self._analyze(group)
                
                # Score: school diversity is PRIMARY, then grade, then weight
                score = (
                    (result.max_same_school - 1) * 1000 +  # Penalize same-school wrestlers heavily
                    result.grade_spread * 100 +
                    result.school_count * (-50) +  # Bonus for more schools
                    result.weight_spread * 1
                )
                
                if score < best_score:
                    best_score = score
                    best_group = group
        
        return best_group
    
    def match_all(self, num_mats: int = 3) -> tuple[list[Bracket], list[Wrestler]]:
        available = self.wrestlers.copy()
        brackets = []
        bracket_id = 0
        
        # Calculate isolation scores for all wrestlers
        isolation_scores = {
            w.id: self._calculate_isolation(w, available) 
            for w in available
        }
        
        # Phase 1: STRICT constraints - process by isolation (most isolated first)
        # Prioritize diverse schools from the start
        sorted_by_isolation = sorted(
            available, 
            key=lambda w: isolation_scores[w.id], 
            reverse=True
        )
        
        for seed in sorted_by_isolation:
            if seed not in available or len(available) < 4:
                continue
            
            group = self._find_partners(
                seed, available, 4,
                max_weight=self.MAX_WEIGHT_STRICT,
                max_grade=self.MAX_GRADE,
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
        
        # Phase 2: Allow weight up to 25lbs, 2 same school
        while len(available) >= 4:
            group = self._find_best_bracket(
                available, 4,
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
        
        # Phase 3: Allow weight up to 44lbs (hand-made bracket standard)
        while len(available) >= 4:
            group = self._find_best_bracket(
                available, 4,
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
        
        # Phase 4: Emergency - allow grade ±2 (last resort for 4-person)
        while len(available) >= 4:
            group = self._find_best_bracket(
                available, 4,
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
        
        # Phase 5: 3-person brackets with progressive relaxation
        weight_levels = [10.0, 25.0, 44.0]
        
        for max_weight in weight_levels:
            while len(available) >= 3:
                group = self._find_best_bracket(
                    available, 3,
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
        
        # Phase 6: 3-person with grade relaxation if needed
        while len(available) >= 3:
            group = self._find_best_bracket(
                available, 3,
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
        
        # Phase 7: Absorb stragglers into best-fit brackets
        while available:
            wrestler = available.pop(0)
            
            # Find bracket where this wrestler fits best
            best_bracket = None
            best_score = float('inf')
            
            for b in brackets:
                if len(b.wrestlers) >= 4:
                    continue
                
                test_group = b.wrestlers + [wrestler]
                result = self._analyze(test_group)
                
                # Prefer brackets where adding doesn't violate grade
                if result.grade_spread > self.MAX_GRADE_EMERGENCY:
                    continue
                
                # Score: school diversity is PRIMARY
                score = (
                    (result.max_same_school - 1) * 1000 +  # Penalize same-school heavily
                    result.grade_spread * 100 +
                    result.weight_spread * 1 +
                    len(b.wrestlers) * 10  # Prefer smaller brackets
                )
                
                if score < best_score:
                    best_score = score
                    best_bracket = b
            
            if best_bracket:
                best_bracket.wrestlers.append(wrestler)
                best_bracket.relaxations = self._analyze(best_bracket.wrestlers).violations
            else:
                # Create a tiny bracket (shouldn't happen often)
                brackets.append(Bracket(
                    id=bracket_id,
                    wrestlers=[wrestler],
                    relaxations=[]
                ))
                bracket_id += 1
        
        self._assign_mats(brackets, num_mats)
        self.brackets = brackets
        self.unmatched = []
        
        return brackets, []
    
    def _assign_mats(self, brackets: list[Bracket], num_mats: int):
        for i, bracket in enumerate(brackets):
            bracket.mat_number = (i % num_mats) + 1
    
    def get_statistics(self) -> dict:
        """Return statistics about the generated brackets."""
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
            'size_distribution': dict(sizes),
            'no_violations': sum(1 for b in self.brackets if not b.relaxations),
            'weight_relaxed': sum(1 for b in self.brackets if ConstraintRelaxation.WEIGHT in b.relaxations),
            'grade_relaxed': sum(1 for b in self.brackets if ConstraintRelaxation.GRADE in b.relaxations),
            'school_relaxed': sum(1 for b in self.brackets if ConstraintRelaxation.SCHOOL in b.relaxations),
            'avg_weight_spread': sum(weight_spreads) / len(weight_spreads) if weight_spreads else 0,
            'max_weight_spread': max(weight_spreads) if weight_spreads else 0,
            'avg_grade_spread': sum(grade_spreads) / len(grade_spreads) if grade_spreads else 0,
        }


# Backwards-compatible alias
BracketMatcher = BracketMatcherV3
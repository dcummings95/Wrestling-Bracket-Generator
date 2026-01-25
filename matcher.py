from collections import Counter
from itertools import combinations
from models import Wrestler, Bracket, ConstraintRelaxation


class ConstraintConfig:
    def __init__(
        self,
        weight_diff: float = 10.0,
        grade_diff: int = 1,
        rank_diff: int = 2,
        max_same_school: int = 2
    ):
        self.weight_diff = weight_diff
        self.grade_diff = grade_diff
        self.rank_diff = rank_diff
        self.max_same_school = max_same_school


class BracketMatcher:
    RELAXATION_LEVELS = [
        ConstraintConfig(weight_diff=10.0, grade_diff=1, rank_diff=2, max_same_school=1),
        ConstraintConfig(weight_diff=10.0, grade_diff=1, rank_diff=3, max_same_school=1),
        ConstraintConfig(weight_diff=10.0, grade_diff=1, rank_diff=4, max_same_school=1),
        ConstraintConfig(weight_diff=10.0, grade_diff=2, rank_diff=4, max_same_school=1),
        ConstraintConfig(weight_diff=10.0, grade_diff=1, rank_diff=2, max_same_school=2),
        ConstraintConfig(weight_diff=10.0, grade_diff=1, rank_diff=3, max_same_school=2),
        ConstraintConfig(weight_diff=10.0, grade_diff=1, rank_diff=4, max_same_school=2),
        ConstraintConfig(weight_diff=10.0, grade_diff=2, rank_diff=4, max_same_school=2),
        ConstraintConfig(weight_diff=15.0, grade_diff=2, rank_diff=4, max_same_school=2),
        ConstraintConfig(weight_diff=20.0, grade_diff=2, rank_diff=5, max_same_school=2),
        ConstraintConfig(weight_diff=20.0, grade_diff=2, rank_diff=5, max_same_school=3),
    ]
    
    def __init__(self, wrestlers: list[Wrestler], bracket_size: int = 4):
        self.wrestlers = wrestlers
        self.bracket_size = bracket_size
        self.brackets: list[Bracket] = []
        self.unmatched: list[Wrestler] = []
    
    def check_constraints(self, wrestlers: list[Wrestler], config: ConstraintConfig) -> dict:
        """Check which constraints pass/fail for a group."""
        results = {"weight": True, "grade": True, "rank": True, "school": True}
        
        if len(wrestlers) < 2:
            return results
        
        weights = [w.weight for w in wrestlers]
        if max(weights) - min(weights) > config.weight_diff:
            results["weight"] = False
        
        grades = [w.grade for w in wrestlers]
        if max(grades) - min(grades) > config.grade_diff:
            results["grade"] = False
        
        ranks = [w.rank for w in wrestlers]
        if max(ranks) - min(ranks) > config.rank_diff:
            results["rank"] = False
        
        school_counts = Counter(w.school for w in wrestlers)
        if max(school_counts.values()) > config.max_same_school:
            results["school"] = False
        
        return results
    
    def is_valid_bracket(self, wrestlers: list[Wrestler], config: ConstraintConfig) -> bool:
        if len(wrestlers) < 2:
            return False
        results = self.check_constraints(wrestlers, config)
        return all(results.values())
    
    def get_relaxations(self, wrestlers: list[Wrestler]) -> list[ConstraintRelaxation]:
        relaxations = []
        base = ConstraintConfig(weight_diff=10.0, grade_diff=1, rank_diff=2, max_same_school=1)
        
        weights = [w.weight for w in wrestlers]
        if max(weights) - min(weights) > base.weight_diff:
            relaxations.append(ConstraintRelaxation.WEIGHT)
        
        grades = [w.grade for w in wrestlers]
        if max(grades) - min(grades) > base.grade_diff:
            relaxations.append(ConstraintRelaxation.GRADE)
        
        ranks = [w.rank for w in wrestlers]
        if max(ranks) - min(ranks) > base.rank_diff:
            relaxations.append(ConstraintRelaxation.RANK)
        
        school_counts = Counter(w.school for w in wrestlers)
        if max(school_counts.values()) > base.max_same_school:
            relaxations.append(ConstraintRelaxation.SCHOOL)
        
        return relaxations
    
    def score_bracket(self, wrestlers: list[Wrestler]) -> float:
        """Lower score is better. Heavily penalizes same-school pairings."""
        weights = [w.weight for w in wrestlers]
        grades = [w.grade for w in wrestlers]
        ranks = [w.rank for w in wrestlers]
        
        weight_spread = max(weights) - min(weights)
        grade_spread = max(grades) - min(grades)
        rank_spread = max(ranks) - min(ranks)
        
        school_counts = Counter(w.school for w in wrestlers)
        unique_schools = len(school_counts)
        max_from_same = max(school_counts.values())
        
        school_penalty = (max_from_same - 1) * 100 + (4 - unique_schools) * 50
        
        return school_penalty + (grade_spread * 10) + weight_spread + (rank_spread * 2)
    
    def can_add_wrestler(self, wrestler: Wrestler, group: list[Wrestler], config: ConstraintConfig) -> bool:
        """Check if a wrestler can be added to a group."""
        return self.is_valid_bracket(group + [wrestler], config)
    
    def find_best_bracket_for_wrestler(
        self,
        wrestler: Wrestler,
        available: list[Wrestler],
        config: ConstraintConfig
    ) -> list[Wrestler] | None:
        """Find the best bracket starting with a specific wrestler, prioritizing school diversity."""
        candidates = [wrestler]
        remaining = [w for w in available if w.id != wrestler.id]
        
        schools_used = {wrestler.school}
        
        while len(candidates) < self.bracket_size and remaining:
            best_next = None
            best_score = float('inf')
            
            for w in remaining:
                if not self.can_add_wrestler(w, candidates, config):
                    continue
                
                test_group = candidates + [w]
                score = self.score_bracket(test_group)
                
                if w.school not in schools_used:
                    score -= 200
                
                if score < best_score:
                    best_score = score
                    best_next = w
            
            if best_next is None:
                break
            
            candidates.append(best_next)
            schools_used.add(best_next.school)
            remaining.remove(best_next)
        
        if len(candidates) >= 3:
            return candidates
        return None
    
    def find_best_bracket(
        self,
        available: list[Wrestler],
        config: ConstraintConfig
    ) -> list[Wrestler] | None:
        """Find the best possible bracket from available wrestlers."""
        if len(available) < 3:
            return None
        
        available_sorted = sorted(available, key=lambda w: (w.grade, w.weight))
        
        best_bracket = None
        best_score = float('inf')
        
        for seed in available_sorted[:min(len(available_sorted), 20)]:
            bracket = self.find_best_bracket_for_wrestler(seed, available, config)
            if bracket:
                score = self.score_bracket(bracket)
                size_bonus = len(bracket) * -50
                score += size_bonus
                
                if score < best_score:
                    best_score = score
                    best_bracket = bracket
        
        return best_bracket
    
    def match_all(self, num_mats: int = 3) -> tuple[list[Bracket], list[Wrestler]]:
        available = self.wrestlers.copy()
        brackets = []
        bracket_id = 0
        
        for config in self.RELAXATION_LEVELS:
            while len(available) >= 3:
                bracket_wrestlers = self.find_best_bracket(available, config)
                
                if bracket_wrestlers is None:
                    break
                
                relaxations = self.get_relaxations(bracket_wrestlers)
                brackets.append(Bracket(
                    id=bracket_id,
                    wrestlers=bracket_wrestlers,
                    relaxations=relaxations
                ))
                bracket_id += 1
                
                for w in bracket_wrestlers:
                    available.remove(w)
            
            if len(available) < 3:
                break
        
        if len(available) > 0:
            available = self._redistribute_remaining(available, brackets)
        
        self._assign_mats(brackets, num_mats)
        
        self.brackets = brackets
        self.unmatched = available
        
        return brackets, available
    
    def _redistribute_remaining(
        self,
        remaining: list[Wrestler],
        brackets: list[Bracket]
    ) -> list[Wrestler]:
        """Try to fit remaining wrestlers into existing brackets. Goal: 0 unmatched."""
        still_remaining = list(remaining)
        
        for wrestler in list(still_remaining):
            placed = False
            
            best_bracket = None
            best_score = float('inf')
            best_config = None
            
            for bracket in brackets:
                if len(bracket.wrestlers) >= 4:
                    continue
                    
                test_group = bracket.wrestlers + [wrestler]
                
                for config in self.RELAXATION_LEVELS:
                    if self.is_valid_bracket(test_group, config):
                        score = self.score_bracket(test_group)
                        if score < best_score:
                            best_score = score
                            best_bracket = bracket
                            best_config = config
                        break
            
            if best_bracket:
                best_bracket.wrestlers.append(wrestler)
                best_bracket.relaxations = self.get_relaxations(best_bracket.wrestlers)
                still_remaining.remove(wrestler)
                placed = True
        
        for wrestler in list(still_remaining):
            best_bracket = None
            best_score = float('inf')
            
            for bracket in brackets:
                test_group = bracket.wrestlers + [wrestler]
                
                final_config = ConstraintConfig(
                    weight_diff=25.0, grade_diff=3, rank_diff=5, max_same_school=3
                )
                
                if self.is_valid_bracket(test_group, final_config):
                    score = self.score_bracket(test_group)
                    score += len(bracket.wrestlers) * 10
                    
                    if score < best_score:
                        best_score = score
                        best_bracket = bracket
            
            if best_bracket:
                best_bracket.wrestlers.append(wrestler)
                best_bracket.relaxations = self.get_relaxations(best_bracket.wrestlers)
                still_remaining.remove(wrestler)
        
        if len(still_remaining) >= 2:
            brackets.append(Bracket(
                id=len(brackets),
                wrestlers=still_remaining,
                relaxations=self.get_relaxations(still_remaining) if len(still_remaining) > 1 else []
            ))
            still_remaining = []
        
        return still_remaining
    
    def _assign_mats(self, brackets: list[Bracket], num_mats: int):
        for i, bracket in enumerate(brackets):
            bracket.mat_number = (i % num_mats) + 1
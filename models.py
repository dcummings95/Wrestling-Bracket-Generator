from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class ConstraintRelaxation(Enum):
    NONE = "none"
    RANK = "rank_relaxed"
    GRADE = "grade_relaxed"
    WEIGHT = "weight_relaxed"
    SCHOOL = "school_relaxed"


@dataclass
class Wrestler:
    id: int
    first_name: str
    last_name: str
    grade: int
    weight: float
    rank: int
    school: str
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def grade_display(self) -> str:
        if self.grade == -1:
            return "Pre-K"
        elif self.grade == 0:
            return "K"
        else:
            return str(self.grade)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "grade": self.grade,
            "grade_display": self.grade_display,
            "weight": self.weight,
            "rank": self.rank,
            "school": self.school,
            "full_name": self.full_name
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Wrestler':
        """Create Wrestler from dictionary."""
        return Wrestler(
            id=data['id'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            grade=data['grade'],
            weight=data['weight'],
            rank=data['rank'],
            school=data['school']
        )


@dataclass
class Bracket:
    id: int
    wrestlers: list[Wrestler]
    mat_number: Optional[int] = None
    relaxations: list[ConstraintRelaxation] = field(default_factory=list)
    
    @property
    def letter_label(self) -> str:
        n = self.id
        result = ''
        while True:
            result = chr(ord('A') + n % 26) + result
            n = n // 26 - 1
            if n < 0:
                break
        return result

    @property
    def size(self) -> int:
        return len(self.wrestlers)
    
    @property
    def is_full(self) -> bool:
        return self.size == 4
    
    @property
    def weight_range(self) -> tuple[float, float]:
        weights = [w.weight for w in self.wrestlers]
        return (min(weights), max(weights)) if weights else (0, 0)
    
    @property
    def grade_range(self) -> tuple[int, int]:
        grades = [w.grade for w in self.wrestlers]
        return (min(grades), max(grades)) if grades else (0, 0)
    
    @property
    def grade_range_display(self) -> tuple[str, str]:
        def fmt(g):
            if g == -1:
                return "Pre-K"
            elif g == 0:
                return "K"
            return str(g)
        low, high = self.grade_range
        return (fmt(low), fmt(high))
    
    @property
    def staggered_matchups(self) -> list[tuple['Wrestler', 'Wrestler']]:
        """All round-robin pairs ordered so wrestlers get rest between matches.
        Uses the round-robin polygon algorithm: fix player[0], rotate the rest."""
        n = len(self.wrestlers)
        if n < 2:
            return []

        players = list(range(n))
        if n % 2 == 1:
            players.append(None)  # bye slot for odd counts

        total = len(players)
        fixed = players[0]
        rotating = players[1:]
        result = []

        for _ in range(total - 1):
            opp = rotating[0]
            if fixed is not None and opp is not None:
                result.append((self.wrestlers[fixed], self.wrestlers[opp]))
            for k in range(1, total // 2):
                a, b = rotating[k], rotating[-k]
                if a is not None and b is not None:
                    result.append((self.wrestlers[a], self.wrestlers[b]))
            rotating = [rotating[-1]] + rotating[:-1]

        return result

    def get_relaxation_warnings(self) -> list[str]:
        warnings = []
        for r in self.relaxations:
            if r == ConstraintRelaxation.RANK:
                warnings.append("Rank constraint relaxed (>±2)")
            elif r == ConstraintRelaxation.GRADE:
                warnings.append("Grade constraint relaxed (>±1)")
            elif r == ConstraintRelaxation.WEIGHT:
                warnings.append("Weight constraint relaxed (>10lbs)")
        return warnings
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "wrestlers": [w.to_dict() for w in self.wrestlers],
            "mat_number": self.mat_number,
            "size": self.size,
            "weight_range": self.weight_range,
            "grade_range": self.grade_range,
            "warnings": self.get_relaxation_warnings(),
            "relaxations": [r.value for r in self.relaxations]
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Bracket':
        """Create Bracket from dictionary."""
        relaxations = [ConstraintRelaxation(r) for r in data.get('relaxations', [])]
        return Bracket(
            id=data['id'],
            wrestlers=[Wrestler.from_dict(w) for w in data['wrestlers']],
            mat_number=data.get('mat_number'),
            relaxations=relaxations
        )


@dataclass
class Event:
    id: int
    name: str
    date: str
    num_mats: int
    bracket_size: int = 4
    brackets: list[Bracket] = field(default_factory=list)
    unmatched_wrestlers: list[Wrestler] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "date": self.date,
            "num_mats": self.num_mats,
            "bracket_size": self.bracket_size,
            "brackets": [b.to_dict() for b in self.brackets],
            "unmatched_wrestlers": [w.to_dict() for w in self.unmatched_wrestlers],
            "total_wrestlers": sum(b.size for b in self.brackets) + len(self.unmatched_wrestlers),
            "total_brackets": len(self.brackets)
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Event':
        """Create Event from dictionary."""
        return Event(
            id=data['id'],
            name=data['name'],
            date=data['date'],
            num_mats=data['num_mats'],
            bracket_size=data.get('bracket_size', 4),
            brackets=[Bracket.from_dict(b) for b in data['brackets']],
            unmatched_wrestlers=[Wrestler.from_dict(w) for w in data.get('unmatched_wrestlers', [])]
        )

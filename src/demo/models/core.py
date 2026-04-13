from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

class OpType(Enum):
    ASSIGN = auto()
    READ = auto()
    WRITE = auto()
    CMP = auto()
    BRANCH = auto()
    MATH = auto()
    CALL = auto()
    ANY = auto() # Для total_ops

@dataclass
class StepEvent:
    op: OpType
    meta: dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalResult:
    value: Any
    counters: dict[str, int] = field(default_factory=dict)

def merge_counters(*counters: dict[str, int]) -> dict[str, int]:
    """Утилита для слияния локальных векторов счетчиков"""
    result = {}
    for c in counters:
        for k, v in c.items():
            result[k] = result.get(k, 0) + v
    return result
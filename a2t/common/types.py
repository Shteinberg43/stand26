from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict


class OpType(Enum):
    ANY = auto()
    CMP = auto()
    ASSIGN = auto()
    ARRAY_READ = auto()
    ARRAY_WRITE = auto()
    CALL = auto()
    RETURN = auto()
    BRANCH = auto()
    ALLOC = auto()


@dataclass(frozen=True)
class StepEvent:
    op: OpType
    meta: Dict[str, Any] = field(default_factory=dict)

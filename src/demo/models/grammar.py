from dataclasses import dataclass, field
from src.demo.models.tn_rule import RuleGraph
from enum import Enum
from typing import Dict, List, Tuple, Union, Optional, Any


@dataclass
class Terminal:
    name: str
    pattern: str

    def __str__(self) -> str:
        return f"Terminal(name: {self.name}, pattern: {self.pattern})"


@dataclass
class GrammarObject:

    terminals: Dict[str, Terminal] = field(default_factory=dict)
    keys: List[Tuple[str, str]] = field(default_factory=list)
    non_terminals: List[str] = field(default_factory=list)
    axiom: str = ""
    _syntax_info: dict = field(default_factory=dict)
    graphs_rule: Optional[List[RuleGraph]] = None

    @property
    def syntax_info(self):
        if self._syntax_info is None:
            raise Exception("Need to declare graph_rule or syntax_info")
        return self._syntax_info

    @syntax_info.setter
    def syntax_info(self, value):
        self._syntax_info = value

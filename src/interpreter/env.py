# src/interpreter/env.py
from __future__ import annotations
from typing import Any, Dict, Optional

class Environment:
    """Хранилище переменных и массивов текущей области видимости."""
    
    def __init__(self, enclosing: Optional[Environment] = None) -> None:
        self.values: Dict[str, Any] = {}
        self.enclosing = enclosing

    def define(self, name: str, value: Any) -> None:
        self.values[name] = value

    def assign(self, name: str, value: Any) -> None:
        if name in self.values:
            self.values[name] = value
            return
        if self.enclosing is not None:
            self.enclosing.assign(name, value)
            return
        raise RuntimeError(f"Undefined variable '{name}'.")

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.enclosing is not None:
            return self.enclosing.get(name)
        raise RuntimeError(f"Undefined variable '{name}'.")
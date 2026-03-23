from dataclasses import dataclass
from typing import Dict, Optional
from my_types import Type 

@dataclass
class Symbol:
    name: str
    type: Type
    mutable: bool = True

class Scope:
    def __init__(self, parent: Optional['Scope'] = None):
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}

    def declare(self, name: str, sym: Symbol):
        if name in self.symbols:
            raise KeyError(f"Symbol '{name}' already declared in this scope")
        self.symbols[name] = sym

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

class SymbolTable:
    def __init__(self):
        self.global_scope = Scope(parent=None)
        self.current = self.global_scope

    def push(self):
        self.current = Scope(parent=self.current)

    def pop(self):
        if not self.current.parent:
            raise RuntimeError('Cannot pop global scope')
        self.current = self.current.parent

    def declare(self, name: str, type_: Type, mutable: bool = True) -> Symbol:
        sym = Symbol(name=name, type=type_, mutable=mutable)
        self.current.declare(name, sym)
        return sym

    def lookup(self, name: str) -> Optional[Symbol]:
        return self.current.lookup(name)
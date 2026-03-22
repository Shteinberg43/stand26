from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Any

class Node:
    pass

@dataclass
class Number(Node):
    value: int

@dataclass
class Var(Node):
    name: str

@dataclass
class Assign(Node):
    target: str
    expr: Node

@dataclass
class BinaryOp(Node):
    left: Node
    op: str  # '+', '-', '<', '>', '=='
    right: Node

@dataclass
class Block(Node):
    statements: List[Node]

@dataclass
class While(Node):
    condition: Node
    body: Block

@dataclass
class ArrayAlloc(Node):
    name: str
    size: Node

@dataclass
class ArrayRead(Node):
    name: str
    index: Node

@dataclass
class ArrayWrite(Node):
    name: str
    index: Node
    expr: Node
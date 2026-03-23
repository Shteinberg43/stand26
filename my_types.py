from __future__ import annotations
from dataclasses import dataclass
from typing import List

class Type:
    def __eq__(self, other: object) -> bool:
        return type(self) is type(other)

    def __repr__(self) -> str:
        return self.__class__.__name__.lower()

@dataclass
class IntType(Type):
    def __repr__(self): return 'int'

@dataclass
class BoolType(Type):
    def __repr__(self): return 'bool'

@dataclass
class StringType(Type):
    def __repr__(self): return 'string'

@dataclass
class ArrayType(Type):
    elem_type: Type
    
    def __repr__(self):
        return f'array[{self.elem_type}]'
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ArrayType): return False
        return self.elem_type == other.elem_type

@dataclass
class FuncType(Type):
    arg_types: List[Type]
    ret_type: Type
    
    def __repr__(self):
        args = ','.join(map(str, self.arg_types))
        return f'func({args})->{self.ret_type}'
        
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FuncType): return False
        if len(self.arg_types) != len(other.arg_types): return False
        return all(a == b for a, b in zip(self.arg_types, other.arg_types)) and self.ret_type == other.ret_type
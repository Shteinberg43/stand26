from typing import List
from symbol_table import SymbolTable
from my_types import IntType, BoolType, Type

class TypeChecker:
    def __init__(self):
        self.symtab = SymbolTable()
        self.errors: List[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def check_var_decl(self, name: str, type_: Type, mutable: bool = True):
        try:
            self.symtab.declare(name, type_, mutable=mutable)
        except KeyError as e:
            self.error(str(e))

    def check_assign(self, name: str, expr_type: Type):
        sym = self.symtab.lookup(name)
        if not sym:
            self.error(f"Undeclared variable '{name}'")
            return
        if sym.type != expr_type:
            self.error(f"Type mismatch assigning to '{name}': expected {sym.type}, got {expr_type}")

    def check_binary_op(self, left: Type, op: str, right: Type) -> Type:
        # Арифметика
        if op in ('+', '-', '*', '/'):
            if left == IntType() and right == IntType():
                return IntType()
            self.error('Arithmetic on non-int types')
            return IntType()
            
        # Равенство
        if op in ('==', '!='):
            if left != right:
                self.error('Comparing different types')
            return BoolType()
            
        # Сравнение
        if op in ('<', '>', '<=', '>='):
            if left == IntType() and right == IntType():
                return BoolType()
            self.error('Ordering on non-int types')
            return BoolType()
            
        self.error(f'Unknown operator {op}')
        return IntType()

    def push_scope(self):
        self.symtab.push()

    def pop_scope(self):
        try:
            self.symtab.pop()
        except RuntimeError as e:
            self.error(str(e))
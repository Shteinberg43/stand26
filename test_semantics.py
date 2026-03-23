import unittest
from my_types import IntType, BoolType
from type_checker import TypeChecker
from runtime import Environment, Value

class TestTypeChecker(unittest.TestCase):
    def setUp(self):
        self.tc = TypeChecker()

    def test_valid_declaration_and_assignment(self):
        self.tc.check_var_decl('x', IntType())
        self.tc.check_assign('x', IntType())
        self.assertEqual(len(self.tc.errors), 0)

    def test_undeclared_variable_assignment(self):
        self.tc.check_assign('y', IntType())
        self.assertEqual(len(self.tc.errors), 1)
        self.assertIn("Undeclared variable", self.tc.errors[0])

    def test_type_mismatch(self):
        self.tc.check_var_decl('flag', BoolType())
        self.tc.check_assign('flag', IntType())
        self.assertEqual(len(self.tc.errors), 1)
        self.assertIn("Type mismatch", self.tc.errors[0])

    def test_scope_shadowing(self):
        self.tc.check_var_decl('x', IntType())
        self.tc.push_scope()
        # Внутренняя область видимости может перекрывать внешнюю
        self.tc.check_var_decl('x', BoolType())
        self.tc.check_assign('x', BoolType()) 
        self.assertEqual(len(self.tc.errors), 0)
        self.tc.pop_scope()
        # Вернулись во внешнюю: x снова IntType
        self.tc.check_assign('x', IntType())
        self.assertEqual(len(self.tc.errors), 0)

class TestEnvironment(unittest.TestCase):
    def setUp(self):
        self.env = Environment()

    def test_global_variables(self):
        self.env.declare_var('count', Value(10, IntType()))
        self.assertEqual(self.env.get_var('count').value, 10)
        
        self.env.set_var('count', Value(20, IntType()))
        self.assertEqual(self.env.get_var('count').value, 20)

    def test_lexical_scoping(self):
        self.env.declare_var('global_var', Value(1, IntType()))
        
        # Заходим в функцию A
        self.env.push_frame('func_A')
        self.env.declare_var('local_A', Value(2, IntType()))
        
        # Из A мы видим локальные и глобальные
        self.assertEqual(self.env.get_var('global_var').value, 1)
        self.assertEqual(self.env.get_var('local_A').value, 2)
        
        # Из A вызываем функцию B
        self.env.push_frame('func_B')
        self.env.declare_var('local_B', Value(3, IntType()))
        
        # Внутри B мы видим B и глобальные
        self.assertEqual(self.env.get_var('local_B').value, 3)
        self.assertEqual(self.env.get_var('global_var').value, 1)
        
        # НО мы НЕ должны видеть local_A (строгая лексическая область видимости)
        with self.assertRaises(NameError):
            self.env.get_var('local_A')
            
        self.env.pop_frame() # Вышли из B
        self.env.pop_frame() # Вышли из A

if __name__ == '__main__':
    unittest.main()
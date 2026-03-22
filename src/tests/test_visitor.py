import unittest
from src.common.events import EventBus
from src.common.types import StepEvent, OpType
from src.interpreter.env import Environment
from src.interpreter.visitor import Visitor
import src.interpreter.ast_nodes as ast
from src.watchdog.counters import CounterManager, CounterRule
from src.watchdog.stop_conditions import parse_stop_if
from src.watchdog.watchdog import Watchdog, ExecutionLimitExceeded

class VisitorTests(unittest.TestCase):
    def setUp(self):
        # 1. Настраиваем счетчики
        rules = [
            CounterRule("comparisons", OpType.CMP),
            CounterRule("assigns", OpType.ASSIGN),
            CounterRule("total", OpType.ANY)
        ]
        self.manager = CounterManager(rules)
        
        # 2. Условия остановки
        self.stop_cond = parse_stop_if("STOP_IF comparisons > 2")
        self.watchdog = Watchdog(self.manager, [self.stop_cond])
        
        # 3. Инфраструктура
        self.bus = EventBus()
        self.env = Environment()
        self.visitor = Visitor(self.bus, self.env)
        
        # Подписываем watchdog на шину событий
        self.bus.subscribe(self.watchdog.on_event)

    def test_assignment_instrumentation(self):
        """Проверка генерации событий при присваивании."""
        # Код: x = 42
        node = ast.Assign(target="x", expr=ast.Number(42))
        self.visitor.visit(node)
        
        self.assertEqual(self.env.get("x"), 42)
        self.assertEqual(self.manager.values["assigns"], 1)

    def test_binary_op_instrumentation(self):
        """Проверка генерации событий при операциях сравнения."""
        # Код: 10 < 20
        node = ast.BinaryOp(left=ast.Number(10), op="<", right=ast.Number(20))
        result = self.visitor.visit(node)
        
        self.assertTrue(result)
        self.assertEqual(self.manager.values["comparisons"], 1)

    def test_environment_scoping(self):
        """Тест изоляции переменных."""
        self.env.define("x", 10)
        self.assertEqual(self.env.get("x"), 10)
        
        # Создаем вложенную область видимости
        child_env = Environment(enclosing=self.env)
        self.assertEqual(child_env.get("x"), 10)
        
        child_env.define("y", 20)
        self.assertEqual(child_env.get("y"), 20)
        
        with self.assertRaises(RuntimeError):
            self.env.get("y") # В родителе нет переменной из дочернего слоя

    def test_watchdog_interruption(self):
        """Интеграционный тест: прерывание бесконечного цикла."""
        # i = 0; while (i < 10) { i = i + 1 }
        # Ограничение: comparisons > 2 (сработает на 3-й итерации)
        loop = ast.Block([
            ast.Assign("i", ast.Number(0)),
            ast.While(
                condition=ast.BinaryOp(ast.Var("i"), "<", ast.Number(10)),
                body=ast.Block([
                    ast.Assign("i", ast.BinaryOp(ast.Var("i"), "+", ast.Number(1)))
                ])
            )
        ])

        with self.assertRaises(ExecutionLimitExceeded):
            self.visitor.visit(loop)
        
        # Проверяем, что i успело увеличиться до прерывания
        self.assertGreater(self.env.get("i"), 0)

if __name__ == "__main__":
    unittest.main()
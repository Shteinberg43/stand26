from __future__ import annotations
from typing import Any, Dict, Iterator


class Stepper:
    """
    Обертка над пошаговым исполнением одной программы.
    Интерпретатор должен предоставлять метод execute_iter(program, inputs),
    возвращающий итератор событий выполнения.
    """

    def __init__(self, interpreter: Any, program: Any, inputs: Dict[str, Any]):
        self._iter: Iterator[Any] = interpreter.execute_iter(program, inputs)
        self.finished = False

    def step(self):
        if self.finished:
            return None
        try:
            return next(self._iter)
        except StopIteration:
            self.finished = True
            return None

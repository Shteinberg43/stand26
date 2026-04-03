class PseudoCodeRuntimeError(Exception):
    """Ошибка времени выполнения внутри исполняемой псевдопрограммы."""
    pass


class ExecutionLimitExceeded(PseudoCodeRuntimeError):
    """Превышен лимит операций / сработало STOP_IF."""
    pass

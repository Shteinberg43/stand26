class Stepper:
    def __init__(self, interpreter, program, inputs):
        self._iter = interpreter.execute_iter(program, inputs)
        self.finished = False

    def step(self):
        if self.finished:
            return None
        try:
            return next(self._iter)
        except StopIteration:
            self.finished = True
            return None

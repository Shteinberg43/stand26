from a2t.common.errors import PseudoCodeRuntimeError
from a2t.interpreter.stepper import Stepper
from a2t.stand.scheduler import RoundRobinScheduler, ScheduledRun


class DemoInterpreter:
    def __init__(self, steps, fail_at=None, fail_exc=None):
        self.steps = steps
        self.fail_at = fail_at
        self.fail_exc = fail_exc

    def execute_iter(self, program, inputs):
        for i in range(self.steps):
            if self.fail_at is not None and i == self.fail_at:
                raise self.fail_exc
            yield {"program": program, "tick": i}


class DemoWatchdog:
    def __init__(self, limit_after=None):
        self.limit_after = limit_after
        self.counter = 0

    def on_event(self, event):
        self.counter += 1
        if self.limit_after is not None and self.counter > self.limit_after:
            from a2t.common.errors import ExecutionLimitExceeded
            raise ExecutionLimitExceeded("STOP_IF total_ops > limit")


def make_run(run_id, steps, limit_after=None, fail_at=None, fail_exc=None):
    interpreter = DemoInterpreter(steps=steps, fail_at=fail_at, fail_exc=fail_exc)
    stepper = Stepper(interpreter, program=run_id, inputs={})
    watchdog = DemoWatchdog(limit_after=limit_after)
    return ScheduledRun(run_id=run_id, stepper=stepper, watchdog=watchdog)


if __name__ == "__main__":
    scheduler = RoundRobinScheduler(quantum=10)
    runs = [
        make_run("run1", steps=15),
        make_run("run2", steps=100, limit_after=12),
        make_run("run3", steps=8, fail_at=5, fail_exc=PseudoCodeRuntimeError("index out of bounds")),
    ]

    completed = scheduler.run(runs)

    print("DEMO STAGE 5")
    for run in sorted(completed, key=lambda r: r.run_id):
        print(
            "{0}: status={1}, scheduled={2}, steps={3}, error={4}".format(
                run.run_id,
                run.status,
                run.times_scheduled,
                run.steps_executed,
                run.error_message,
            )
        )

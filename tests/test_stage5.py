import unittest

from a2t.common.errors import ExecutionLimitExceeded, PseudoCodeRuntimeError
from a2t.interpreter.stepper import Stepper
from a2t.stand.scheduler import RoundRobinScheduler, ScheduledRun


class MockInterpreter:
    def __init__(self, steps, fail_at=None, fail_exc=None):
        self.steps = steps
        self.fail_at = fail_at
        self.fail_exc = fail_exc

    def execute_iter(self, program, inputs):
        for i in range(self.steps):
            if self.fail_at is not None and i == self.fail_at:
                raise self.fail_exc
            yield {"tick": i, "program": program, "inputs": inputs}


class MockWatchdog:
    def __init__(self, limit_after=None):
        self.limit_after = limit_after
        self.counter = 0

    def on_event(self, event):
        self.counter += 1
        if self.limit_after is not None and self.counter > self.limit_after:
            raise ExecutionLimitExceeded("STOP_IF total_ops > limit")


def make_task(run_id, steps, quantum=10, limit_after=None, fail_at=None, fail_exc=None):
    interpreter = MockInterpreter(steps=steps, fail_at=fail_at, fail_exc=fail_exc)
    stepper = Stepper(interpreter, program=run_id, inputs={})
    watchdog = MockWatchdog(limit_after=limit_after)
    return ScheduledRun(run_id=run_id, stepper=stepper, watchdog=watchdog)


class Stage5SchedulerTests(unittest.TestCase):
    def test_three_runs_all_receive_turn(self):
        scheduler = RoundRobinScheduler(quantum=10)
        runs = [
            make_task("run1", steps=15),
            make_task("run2", steps=17),
            make_task("run3", steps=12),
        ]
        completed = scheduler.run(runs)

        self.assertEqual(3, len(completed))
        for run in completed:
            self.assertGreaterEqual(run.times_scheduled, 1)

    def test_limit_of_one_run_does_not_stop_others(self):
        scheduler = RoundRobinScheduler(quantum=10)
        runs = [
            make_task("run1", steps=15),
            make_task("run2", steps=50, limit_after=12),
            make_task("run3", steps=11),
        ]
        completed = scheduler.run(runs)
        by_id = {r.run_id: r for r in completed}

        self.assertEqual("OK", by_id["run1"].status)
        self.assertEqual("LIMIT", by_id["run2"].status)
        self.assertEqual("OK", by_id["run3"].status)

    def test_runtime_error_of_one_run_does_not_stop_others(self):
        scheduler = RoundRobinScheduler(quantum=10)
        runs = [
            make_task("run1", steps=5),
            make_task(
                "run2",
                steps=20,
                fail_at=3,
                fail_exc=PseudoCodeRuntimeError("division by zero"),
            ),
            make_task("run3", steps=8),
        ]
        completed = scheduler.run(runs)
        by_id = {r.run_id: r for r in completed}

        self.assertEqual("OK", by_id["run1"].status)
        self.assertEqual("ERROR", by_id["run2"].status)
        self.assertEqual("OK", by_id["run3"].status)

    def test_quantum_change_does_not_change_final_statuses(self):
        runs1 = [
            make_task("run1", steps=15),
            make_task("run2", steps=50, limit_after=12),
            make_task("run3", steps=9),
        ]
        runs2 = [
            make_task("run1", steps=15),
            make_task("run2", steps=50, limit_after=12),
            make_task("run3", steps=9),
        ]

        result_q5 = RoundRobinScheduler(quantum=5).run(runs1)
        result_q10 = RoundRobinScheduler(quantum=10).run(runs2)

        s1 = {r.run_id: r.status for r in result_q5}
        s2 = {r.run_id: r.status for r in result_q10}
        self.assertEqual(s1, s2)

    def test_quantum_must_be_positive(self):
        with self.assertRaises(ValueError):
            RoundRobinScheduler(quantum=0)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import random
from typing import Any, Dict


class InputGenerator:
    def generate(self, params: Dict[str, Any], seed: int) -> Dict[str, Any]:
        raise NotImplementedError


class IntArrayGenerator(InputGenerator):
    """
    Generates primitive experiment inputs without introducing a custom type system.
    Supported result payload:
      - array: list[int]
      - n: int
      - seed: int
      - mode: str
    """

    def generate(self, params: Dict[str, Any], seed: int) -> Dict[str, Any]:
        rnd = random.Random(seed)

        n = int(params.get("n", 10))
        mode = str(params.get("mode", "random"))
        low = int(params.get("low", 0))
        high = int(params.get("high", 100))

        data = [rnd.randint(low, high) for _ in range(n)]

        if mode == "sorted":
            data.sort()
        elif mode == "reversed":
            data.sort(reverse=True)
        elif mode == "random":
            pass
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        return {
            "array": data,
            "n": n,
            "seed": seed,
            "mode": mode,
        }


def build_generator(name: str) -> InputGenerator:
    if name == "int_array":
        return IntArrayGenerator()
    raise ValueError(f"Unknown generator: {name}")
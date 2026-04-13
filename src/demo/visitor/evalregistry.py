from dataclasses import field, dataclass
from typing import Any, TYPE_CHECKING, Optional

from src.demo.models.core import StepEvent

if TYPE_CHECKING:
    from src.demo.models.nodes import ASTNode


@dataclass
class EvalContext:
    symbol_table: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    current_scope: Any = None
    data_types: dict = field(default_factory=dict)

    # Для детерминированной публикации шагов Visitor -> EventBus
    event_bus: Any = None
    step_id: int = 0

    def publish_step(
    self,
    op: Any,
    meta: Optional[dict] = None,
    counters: Optional[dict] = None
) -> StepEvent:
        """
        Visitor вызывает этот метод на семантически значимых действиях.
        EventBus получает уже готовый StepEvent.
        """
        self.step_id += 1
        payload = dict(meta or {})
        payload.setdefault("step_id", self.step_id)
        if counters is not None:
            payload["counters"] = dict(counters)

        event = StepEvent(op=op, meta=payload)

        bus = self.event_bus
        if bus is not None:
            if hasattr(bus, "publish"):
                bus.publish(event)
            elif hasattr(bus, "emit"):
                bus.emit(event)
            elif callable(bus):
                bus(event)

        return event


class EvalRegistry:
    _evaluators: dict[tuple["ASTNode.Type", str], "ASTNode.IAttrEval"] = {}

    @classmethod
    def register(
        cls, type: "ASTNode.Type", subtype: str, evaluation: "ASTNode.IAttrEval"
    ):
        cls._evaluators[(type, subtype)] = evaluation

    @classmethod
    def evaluation(cls, type: "ASTNode.Type", subtype: str) -> "ASTNode.IAttrEval":
        from src.demo.models.nodes import ASTNode
        return cls._evaluators.get((type, subtype), ASTNode.IdentityEval())

    @classmethod
    def clear(cls) -> None:
        cls._evaluators = {}
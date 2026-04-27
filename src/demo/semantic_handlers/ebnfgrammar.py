from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from src.demo.models.nodes import ASTNode
from src.demo.visitor.evalregistry import EvalContext, EvalRegistry
from src.demo.models.core import EvalResult, OpType, merge_counters


# -------------------------
# Helpers
# -------------------------

def _op(name: str) -> Any:
    """Безопасно достаём OpType.*; если такого значения нет, используем строку."""
    return getattr(OpType, name, name)


def _safe_publish(
    context: EvalContext,
    op: Any,
    meta: Optional[Dict[str, Any]] = None,
    counters: Optional[Dict[str, int]] = None,
) -> None:
    meta_out = dict(meta or {})
    counters_out = dict(counters or {})

    aliases = _experiment_state(context).get("counter_aliases", {})
    if aliases and not meta_out.get("experiment_control"):
        for alias, event_name in aliases.items():
            amount = _alias_increment(event_name, op, meta_out, counters_out)
            if amount:
                counters_out[alias] = counters_out.get(alias, 0) + amount

    state = _experiment_state(context)
    if counters_out:
        state["runtime_counters"] = _merge_all(state.get("runtime_counters", {}), counters_out)

    publisher = getattr(context, "publish_step", None)
    if callable(publisher):
        publisher(op, meta_out, counters_out if counters is not None or counters_out else None)


def _event_name(op: Any) -> str:
    return str(getattr(op, "name", op)).upper()


def _alias_increment(
    event_name: str,
    op: Any,
    meta: Dict[str, Any],
    counters: Dict[str, int],
) -> int:
    target = str(event_name).upper()
    op_name = _event_name(op)
    event_counter_keys = {
        "READ": "reads",
        "ARRAY_READ": "reads",
        "WRITE": "writes",
        "ARRAY_WRITE": "writes",
        "ASSIGN": "assignments",
        "CMP": "comparisons",
        "COMPARE": "comparisons",
        "BRANCH": "branches",
        "CALL": "calls",
        "ALLOC": "allocations",
        "RETURN": "total_ops",
        "EXIT": "total_ops",
        "ANY": "total_ops",
    }

    if target in event_counter_keys:
        if target == "ANY" or target == op_name or (target == "ARRAY_READ" and op_name == "READ") or (
            target == "ARRAY_WRITE" and op_name == "WRITE"
        ):
            return int(counters.get(event_counter_keys[target], counters.get("total_ops", 1)))
        return 0

    callee = str(meta.get("callee", "")).lower()
    kind = str(meta.get("kind", "")).lower()
    if target.lower() in (callee, kind):
        return int(counters.get("calls", counters.get("total_ops", 1)))
    return 0


def _ensure_result(value: Any) -> EvalResult:
    if isinstance(value, EvalResult):
        return value
    return EvalResult(value=value, counters={})


def _merge_all(*maps: Optional[Dict[str, int]]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for m in maps:
        if m:
            result = merge_counters(result, m)
    return result


def _strip_quotes(value: Any) -> str:
    text = str(value)
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1]
    return text


def _token_text(node: Any) -> str:
    return _strip_quotes(getattr(node, "value", ""))


def _describe_node(node: Any) -> Any:
    """
    Безопасное текстовое описание узла без побочного исполнения.
    Для токена возвращает его текст, для нетерминала — subtype.
    """
    node_type = getattr(node, "type", None)
    if node_type == ASTNode.Type.TOKEN:
        return _token_text(node)
    subtype = getattr(node, "subtype", None)
    if subtype is not None:
        return subtype
    return node.__class__.__name__


def _literal_or_eval(child: "ASTNode", context: EvalContext) -> tuple[Any, Dict[str, int]]:
    """
    Для команд стенда:
    - токены-литералы читаем без побочного исполнения
    - сложные выражения допускаем к вычислению
    """
    if getattr(child, "type", None) == ASTNode.Type.TOKEN:
        subtype = _strip_quotes(getattr(child, "subtype", "")).lower()
        raw = _token_text(child)
        if subtype == "number":
            return _parse_number(raw), {}
        return raw, {}

    res = _ensure_result(child.evaluated(context))
    return res.value, res.counters


def _command_args(children: List["ASTNode"], command_name: str) -> List["ASTNode"]:
    if not children:
        return []
    first = _strip_quotes(getattr(children[0], "value", "")).lower()
    if first == command_name.lower():
        return children[1:]
    return children


def _eval_children(children: List["ASTNode"], context: EvalContext) -> tuple[Any, Dict[str, int]]:
    last_value = None
    counters: Dict[str, int] = {}
    for child in children:
        res = _ensure_result(child.evaluated(context))
        last_value = res.value
        counters = _merge_all(counters, res.counters)
    return last_value, counters


def _eval_sequence(children: List["ASTNode"], context: EvalContext) -> EvalResult:
    value, counters = _eval_children(children, context)
    return EvalResult(value=value, counters=counters)


def _truthy(value: Any) -> bool:
    return bool(value)


def _parse_number(text: str) -> int | float:
    cleaned = _strip_quotes(text)
    return float(cleaned) if "." in cleaned else int(cleaned)


def _binary_arith(lhs: Any, rhs: Any, op: str) -> Any:
    if op == "+":
        return lhs + rhs
    if op == "-":
        return lhs - rhs
    if op == "*":
        return lhs * rhs
    if op == "/":
        return lhs / rhs
    if op in ("//", "DIV"):
        return lhs // rhs
    if op in ("%", "MOD"):
        return lhs % rhs
    raise ValueError(f"Unsupported arithmetic operator: {op}")


def _compare(lhs: Any, rhs: Any, op: str) -> bool:
    if op in ("=", "=="):
        return lhs == rhs
    if op in ("!=", "<>"):
        return lhs != rhs
    if op == "<":
        return lhs < rhs
    if op == ">":
        return lhs > rhs
    if op == "<=":
        return lhs <= rhs
    if op == ">=":
        return lhs >= rhs
    raise ValueError(f"Unsupported comparison operator: {op}")


def _iter_items(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, range)):
        return list(value)
    if isinstance(value, dict):
        return list(value.items())
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]


def _experiment_seed(context: EvalContext, explicit_seed: Any = None) -> Any:
    if explicit_seed is not None:
        return explicit_seed
    state = _experiment_state(context)
    base_seed = state.get("seed", context.symbol_table.get("seed"))
    trial_seed = state.get("trial_seed", 0)
    if base_seed is None:
        return None
    return int(base_seed) + int(trial_seed or 0)


def _resolve_callable(context: EvalContext, name: str):
    candidate = context.symbol_table.get(name)
    if callable(candidate):
        return candidate
    return None


def _builtin_call(name: str, args: List[Any], context: EvalContext) -> tuple[Any, Dict[str, int]]:
    """
    Минимальный, безопасный dispatch для встроенных операций.
    """
    if name == "min":
        seq = _iter_items(args[0]) if args else []
        return (min(seq) if seq else None), {"calls": 1, "total_ops": 1}
    if name == "max":
        seq = _iter_items(args[0]) if args else []
        return (max(seq) if seq else None), {"calls": 1, "total_ops": 1}
    if name == "len":
        seq = args[0] if args else []
        return len(seq), {"calls": 1, "total_ops": 1}
    if name == "quick_sort":
        seq = _iter_items(args[0]) if args else []
        return sorted(seq), {"calls": 1, "allocations": 1, "total_ops": 1}

    if name == "create_array":
        n = int(args[0]) if args else 0
        default = args[1] if len(args) > 1 else 0
        return [default] * (n + 1), {"calls": 1, "allocations": 1, "total_ops": 1}

    if name == "create_matrix":
        rows = int(args[0]) if args else 0
        cols = int(args[1]) if len(args) > 1 else 0
        default = args[2] if len(args) > 2 else 0
        return [[default] * (cols + 1) for _ in range(rows + 1)], {
            "calls": 1,
            "allocations": 1,
            "total_ops": 1,
        }

    if name == "range_set":
        lo = int(args[0]) if args else 0
        hi = int(args[1]) if len(args) > 1 else 0
        return list(range(lo, hi + 1)), {"calls": 1, "allocations": 1, "total_ops": 1}

    if name == "remove":
        collection = args[0] if args else []
        item = args[1] if len(args) > 1 else None
        if isinstance(collection, list) and item in collection:
            collection.remove(item)
        return None, {"calls": 1, "total_ops": 1}

    if name == "adj":
        graph = args[0] if args else []
        v = int(args[1]) if len(args) > 1 else 0
        if isinstance(graph, list) and 0 <= v < len(graph):
            return graph[v], {"calls": 1, "reads": 1, "total_ops": 1}
        return [], {"calls": 1, "total_ops": 1}

    if name == "get_vertices":
        graph = args[0] if args else []
        n = max(len(graph) - 1, 0) if isinstance(graph, list) else 0
        return list(range(1, n + 1)), {"calls": 1, "allocations": 1, "total_ops": 1}

    if name == "is_empty":
        collection = args[0] if args else []
        return 1 if not collection else 0, {"calls": 1, "total_ops": 1}

    if name == "quick_sort_by_degree":
        v_list = args[0] if args else []
        graph = args[1] if len(args) > 1 else []
        if isinstance(v_list, list) and isinstance(graph, list):
            v_list.sort(key=lambda v: len(graph[v]) if 0 <= int(v) < len(graph) else 0, reverse=True)
        return None, {"calls": 1, "total_ops": 1}

    if name == "generate_random_graph":
        n = int(args[0]) if args else 5
        rng = random.Random(_experiment_seed(context, args[1] if len(args) > 1 else None))
        graph = [[] for _ in range(n + 1)]
        edge_prob = 0.3
        for i in range(1, n + 1):
            for j in range(i + 1, n + 1):
                if rng.random() < edge_prob:
                    graph[i].append(j)
                    graph[j].append(i)
        return graph, {"calls": 1, "allocations": 1, "total_ops": 1}

    if name == "generate_weight_matrix":
        n = int(args[0]) if args else 5
        inf = 999999
        rng = random.Random(_experiment_seed(context, args[1] if len(args) > 1 else None))
        matrix = [[inf] * (n + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            matrix[i][i] = 0
        for i in range(1, n + 1):
            for j in range(i + 1, n + 1):
                if rng.random() < 0.5:
                    weight = rng.randint(1, 20)
                    matrix[i][j] = weight
                    matrix[j][i] = weight
        return matrix, {"calls": 1, "allocations": 1, "total_ops": 1}
    
    if name == "array":
        if not args:
            return [], {"calls": 1, "total_ops": 1}
        size = int(args[0]) if args else 0
        # type (второй аргумент) пока игнорируем, создаём список нулей
        result = [0] * size
        return result, {"calls": 1, "allocations": 1, "total_ops": 1}

    fn = _resolve_callable(context, name)
    if fn is not None:
        return fn(*args), {"calls": 1, "total_ops": 1}

    context.warnings.append(f"Unresolved call: {name}")
    return None, {"calls": 1, "total_ops": 1}


def _experiment_state(context: EvalContext) -> Dict[str, Any]:
    return context.data_types.setdefault("experiment", {})


def _record_experiment_command(
    context: EvalContext,
    kind: str,
    value: Any,
    counters: Dict[str, int],
    meta: Optional[Dict[str, Any]] = None,
) -> EvalResult:
    state = _experiment_state(context)
    state.setdefault("commands", []).append(
        {
            "kind": kind,
            "value": value,
            "meta": dict(meta or {}),
        }
    )
    state["last_command"] = {
        "kind": kind,
        "value": value,
        "meta": dict(meta or {}),
    }
    return EvalResult(value=value, counters=counters)


def _expression_children(nodes: List["ASTNode"]) -> List["ASTNode"]:
    return [node for node in nodes if getattr(node, "subtype", "") == "Expression"]


def _refresh_counter_symbols(context: EvalContext) -> Dict[str, Any]:
    counters = _experiment_state(context).get("runtime_counters", {})
    saved: Dict[str, Any] = {}
    for name, value in counters.items():
        saved[name] = context.symbol_table.get(name)
        context.symbol_table[name] = value
    return saved


def _restore_symbols(context: EvalContext, saved: Dict[str, Any]) -> None:
    for name, value in saved.items():
        if value is None:
            context.symbol_table.pop(name, None)
        else:
            context.symbol_table[name] = value


def _check_stop_if(context: EvalContext) -> bool:
    state = _experiment_state(context)
    stop_node = state.get("stop_if_node")
    if stop_node is None:
        return False

    saved = _refresh_counter_symbols(context)
    try:
        res = _ensure_result(stop_node.evaluated(context))
    finally:
        _restore_symbols(context, saved)

    stopped = _truthy(res.value)
    state["stop_if_result"] = stopped
    if stopped:
        state["stopped"] = True
        state["stop_reason"] = "STOP_IF condition matched"
    return stopped


def _eval_or_chain(children: List["ASTNode"], context: EvalContext) -> EvalResult:
    if not children:
        return EvalResult(value=False, counters={})
    if len(children) == 1:
        return _ensure_result(children[0].evaluated(context))

    total_counters: Dict[str, int] = {}
    first = _ensure_result(children[0].evaluated(context))
    total_counters = _merge_all(total_counters, first.counters)

    current = _truthy(first.value)
    _safe_publish(
        context,
        _op("BRANCH"),
        {
            "kind": "or",
            "operand_index": 0,
            "operand": first.value,
            "result": current,
            "short_circuit": current,
        },
        {"branches": 1, "total_ops": 1},
    )
    total_counters = _merge_all(total_counters, {"branches": 1, "total_ops": 1})

    if current:
        return EvalResult(value=True, counters=total_counters)

    operand_index = 1
    i = 2
    while i < len(children):
        next_res = _ensure_result(children[i].evaluated(context))
        total_counters = _merge_all(total_counters, next_res.counters)

        current = _truthy(next_res.value)
        _safe_publish(
            context,
            _op("BRANCH"),
            {
                "kind": "or",
                "operand_index": operand_index,
                "operand": next_res.value,
                "result": current,
                "short_circuit": current,
            },
            {"branches": 1, "total_ops": 1},
        )
        total_counters = _merge_all(total_counters, {"branches": 1, "total_ops": 1})

        if current:
            return EvalResult(value=True, counters=total_counters)

        operand_index += 1
        i += 2

    return EvalResult(value=False, counters=total_counters)


def _eval_and_chain(children: List["ASTNode"], context: EvalContext) -> EvalResult:
    if not children:
        return EvalResult(value=True, counters={})
    if len(children) == 1:
        return _ensure_result(children[0].evaluated(context))

    total_counters: Dict[str, int] = {}
    first = _ensure_result(children[0].evaluated(context))
    total_counters = _merge_all(total_counters, first.counters)

    current = _truthy(first.value)
    _safe_publish(
        context,
        _op("BRANCH"),
        {
            "kind": "and",
            "operand_index": 0,
            "operand": first.value,
            "result": current,
            "short_circuit": not current,
        },
        {"branches": 1, "total_ops": 1},
    )
    total_counters = _merge_all(total_counters, {"branches": 1, "total_ops": 1})

    if not current:
        return EvalResult(value=False, counters=total_counters)

    operand_index = 1
    i = 2
    while i < len(children):
        next_res = _ensure_result(children[i].evaluated(context))
        total_counters = _merge_all(total_counters, next_res.counters)

        current = _truthy(next_res.value)
        _safe_publish(
            context,
            _op("BRANCH"),
            {
                "kind": "and",
                "operand_index": operand_index,
                "operand": next_res.value,
                "result": current,
                "short_circuit": not current,
            },
            {"branches": 1, "total_ops": 1},
        )
        total_counters = _merge_all(total_counters, {"branches": 1, "total_ops": 1})

        if not current:
            return EvalResult(value=False, counters=total_counters)

        operand_index += 1
        i += 2

    return EvalResult(value=True, counters=total_counters)


# -------------------------
# Базовые токены
# -------------------------

class IdentTokenEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        var_name = _strip_quotes(value)
        actual_value = context.symbol_table.get(var_name, None)

        _safe_publish(
            context,
            _op("READ"),
            {"var": var_name},
            {"reads": 1, "total_ops": 1},
        )

        return EvalResult(
            value=actual_value,
            counters={"reads": 1, "total_ops": 1},
        )


class NumberTokenEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        return EvalResult(
            value=_parse_number(value),
            counters={},        
        )

class StringTokenEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        return EvalResult(value=_strip_quotes(value), counters={})

class WhitespaceTokenEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        return EvalResult(value=_strip_quotes(value), counters={})


# -------------------------
# Пасстру-узлы
# -------------------------

class _PassthroughEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        return _eval_sequence(children, context)


class ProgramEval(_PassthroughEval):
    pass


class SubroutineBlockEval(_PassthroughEval):
    pass


class FuncBlockEval(ASTNode.IAttrEval):
    """
    FUNC ident ( ParamDecl, ... ) : TypeDecl StatementList END
    Регистрирует функцию в symbol_table как вызываемый объект.
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        func_name = _strip_quotes(getattr(children[1], "value", ""))

        param_names: List[str] = []
        body_node = None
        for ch in children:
            sub = getattr(ch, "subtype", "")
            if sub == "ParamDecl" and ch.children:
                param_names.append(_strip_quotes(getattr(ch.children[0], "value", "")))
            elif sub == "StatementList":
                body_node = ch

        if body_node is None:
            return EvalResult(value=None, counters={})

        captured_context = context

        def func_callable(*args):
            saved = dict(captured_context.symbol_table)
            for pname, arg in zip(param_names, args):
                captured_context.symbol_table[pname] = arg
            try:
                result = _ensure_result(body_node.evaluated(captured_context))
                return result.value
            finally:
                captured_context.symbol_table.clear()
                captured_context.symbol_table.update(saved)

        context.symbol_table[func_name] = func_callable

        _safe_publish(
            context,
            _op("ASSIGN"),
            {"kind": "func_def", "name": func_name, "params": param_names},
            {"assignments": 1, "total_ops": 1},
        )

        return EvalResult(value=func_name, counters={"assignments": 1, "total_ops": 1})


class ProcBlockEval(ASTNode.IAttrEval):
    """
    PROC ident ( ParamDecl, ... ) StatementList END
    Регистрирует процедуру в symbol_table.
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        proc_name = _strip_quotes(getattr(children[1], "value", ""))

        param_names: List[str] = []
        body_node = None
        for ch in children:
            sub = getattr(ch, "subtype", "")
            if sub == "ParamDecl" and ch.children:
                param_names.append(_strip_quotes(getattr(ch.children[0], "value", "")))
            elif sub == "StatementList":
                body_node = ch

        if body_node is None:
            return EvalResult(value=None, counters={})

        captured_context = context

        def proc_callable(*args):
            saved = dict(captured_context.symbol_table)
            for pname, arg in zip(param_names, args):
                captured_context.symbol_table[pname] = arg
            try:
                result = _ensure_result(body_node.evaluated(captured_context))
                return result.value
            finally:
                captured_context.symbol_table.clear()
                captured_context.symbol_table.update(saved)

        context.symbol_table[proc_name] = proc_callable
        return EvalResult(value=proc_name, counters={"assignments": 1, "total_ops": 1})


class IterBlockEval(_PassthroughEval):
    pass


class AlgorithmBlockEval(ASTNode.IAttrEval):
    """
    ALGORITHM ident ( [ParamDecl, ...] ) [: TypeDecl] StatementList END
    Регистрирует алгоритм как вызываемый (для рекурсии) и исполняет тело.
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        algo_name = _strip_quotes(getattr(children[1], "value", "")) if len(children) > 1 else ""
        param_names: List[str] = []
        body_node = None
        for ch in children:
            sub = getattr(ch, "subtype", "")
            if sub == "ParamDecl" and ch.children:
                param_names.append(_strip_quotes(getattr(ch.children[0], "value", "")))
            elif sub == "StatementList":
                body_node = ch

        if body_node is None:
            return _eval_sequence(children, context)

        # Регистрируем для рекурсивного вызова
        captured_context = context

        def algo_callable(*args):
            saved = dict(captured_context.symbol_table)
            for pname, arg in zip(param_names, args):
                captured_context.symbol_table[pname] = arg
            try:
                result = _ensure_result(body_node.evaluated(captured_context))
                return result.value
            finally:
                captured_context.symbol_table.clear()
                captured_context.symbol_table.update(saved)

        context.symbol_table[algo_name] = algo_callable

        if context.data_types.get("defer_algorithm_body"):
            _safe_publish(
                context,
                _op("ASSIGN"),
                {"kind": "algorithm_def", "name": algo_name, "params": param_names},
                {"assignments": 1, "total_ops": 1},
            )
            return EvalResult(value=algo_name, counters={"assignments": 1, "total_ops": 1})

        return _ensure_result(body_node.evaluated(context))


class ExperimentBlockEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        res = _eval_sequence(children, context)
        state = _experiment_state(context)
        state["experiment_block_result"] = res.value
        return res


class ParamDeclEval(_PassthroughEval):
    pass


class TypeDeclEval(_PassthroughEval):
    pass


class PrimitiveTypeEval(_PassthroughEval):
    pass


class StatementEval(_PassthroughEval):
    pass


class StatementListEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        value_out, counters = _eval_children(children, context)
        return EvalResult(value=value_out, counters=counters)


class ConditionEval(ASTNode.IAttrEval):
    """
    OR-цепочка: term1 or term2 or ...
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        return _eval_or_chain(children, context)


class LogicalTermEval(ASTNode.IAttrEval):
    """
    AND-цепочка: factor1 and factor2 and ...
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        return _eval_and_chain(children, context)


class LogicalFactorEval(ASTNode.IAttrEval):
    """
    factor или not factor
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if not children:
            return EvalResult(value=False, counters={})

        if len(children) == 1:
            return _ensure_result(children[0].evaluated(context))

        if len(children) == 2 and _strip_quotes(getattr(children[0], "value", "")).lower() == "not":
            operand_res = _ensure_result(children[1].evaluated(context))
            result_val = not _truthy(operand_res.value)

            _safe_publish(
                context,
                _op("BRANCH"),
                {"kind": "not", "operand": operand_res.value, "result": result_val},
                {"branches": 1, "total_ops": 1},
            )

            counters = _merge_all(operand_res.counters, {"branches": 1, "total_ops": 1})
            return EvalResult(value=result_val, counters=counters)

        return _eval_sequence(children, context)


class ParamCmdEval(ASTNode.IAttrEval):
    """
    param имя = значение
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        args = _command_args(children, "param")
        if not args:
            return EvalResult(value=None, counters={})

        param_name = _strip_quotes(getattr(args[0], "value", ""))
        state = _experiment_state(context)
        expr_counters: Dict[str, int] = {}
        range_values: List[Any] = []
        for expr_node in _expression_children(args):
            expr_value, counters = _literal_or_eval(expr_node, context)
            range_values.append(expr_value)
            expr_counters = _merge_all(expr_counters, counters)

        expr_value = context.symbol_table.get(param_name, state.get("size"))
        if expr_value is None:
            expr_value = range_values[0] if range_values else None

        state.setdefault("params", {})[param_name] = expr_value
        state.setdefault("param_ranges", {})[param_name] = tuple(range_values)
        context.symbol_table[param_name] = expr_value

        _safe_publish(
            context,
            _op("ASSIGN"),
            {"kind": "param", "param": param_name, "value": expr_value},
            {"assignments": 1, "total_ops": 1},
        )

        return _record_experiment_command(
            context,
            "ParamCmd",
            expr_value,
            _merge_all(expr_counters, {"assignments": 1, "total_ops": 1}),
            {"param": param_name},
        )


class TrialsCmdEval(ASTNode.IAttrEval):
    """
    trials = N
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        args = _command_args(children, "trials")
        if not args:
            return EvalResult(value=1, counters={})

        last_value, last_counters = _literal_or_eval(args[-1], context)
        trials = int(last_value)

        state = _experiment_state(context)
        state["trials"] = trials

        _safe_publish(
            context,
            _op("ASSIGN"),
            {"kind": "trials", "value": trials},
            {"assignments": 1, "total_ops": 1},
        )

        return _record_experiment_command(
            context,
            "TrialsCmd",
            trials,
            _merge_all(last_counters, {"assignments": 1, "total_ops": 1}),
        )


class SeedCmdEval(ASTNode.IAttrEval):
    """
    seed = N
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        args = _command_args(children, "seed")
        if not args:
            return EvalResult(value=None, counters={})

        last_value, last_counters = _literal_or_eval(args[-1], context)
        seed_val = int(last_value)

        state = _experiment_state(context)
        state["seed"] = seed_val

        _safe_publish(
            context,
            _op("ASSIGN"),
            {"kind": "seed", "value": seed_val},
            {"assignments": 1, "total_ops": 1},
        )

        return _record_experiment_command(
            context,
            "SeedCmd",
            seed_val,
            _merge_all(last_counters, {"assignments": 1, "total_ops": 1}),
        )


class GenCmdEval(ASTNode.IAttrEval):
    """
    gen имя_массива = спецификация
    Примеры:
        gen arr = [1, 2, 3]
        gen data = array(100, random)
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        args = _command_args(children, "generator")
        if not args:
            return EvalResult(value=None, counters={})

        # Первый аргумент — имя переменной
        target_name = _strip_quotes(getattr(args[0], "value", ""))

        # Находим узел спецификации (пропускаем возможный токен '=')
        spec_node = None
        if len(args) >= 2:
            if len(args) >= 3 and _strip_quotes(getattr(args[1], "value", "")) == "=":
                spec_node = args[2]
            else:
                spec_node = args[1]

        if spec_node is None:
            spec_value = []
            counters = {}
        else:
            # ВЫЧИСЛЯЕМ спецификацию, а не описываем строкой
            spec_res = _ensure_result(spec_node.evaluated(context))
            spec_value = spec_res.value
            counters = spec_res.counters

        # Сохраняем в состояние эксперимента
        state = _experiment_state(context)
        state.setdefault("generators", {})[target_name] = {
            "value": spec_value,
        }
        context.symbol_table[target_name] = spec_value

        # Публикуем событие выделения памяти
        _safe_publish(
            context,
            _op("ALLOC"),
            {"kind": "gen", "target": target_name, "spec": _describe_node(spec_node) if spec_node else "None"},
            {"allocations": 1, "total_ops": 1},
        )

        # Записываем команду в историю эксперимента
        return _record_experiment_command(
            context,
            "GenCmd",
            spec_value,
            _merge_all(counters, {"allocations": 1, "total_ops": 1}),
            {"target": target_name},
        )

class CounterCmdEval(ASTNode.IAttrEval):
    """
    counter total_ops > 10000
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        args = _command_args(children, "counter")
        if len(args) < 3:
            return EvalResult(value=None, counters={})

        counter_name = _strip_quotes(getattr(args[0], "value", ""))
        event_name = _strip_quotes(getattr(args[2], "value", _describe_node(args[2])))

        rule = {
            "counter": counter_name,
            "event": event_name,
        }

        state = _experiment_state(context)
        state.setdefault("counter_aliases", {})[counter_name] = event_name
        state.setdefault("counter_rules", []).append(rule)

        _safe_publish(
            context,
            _op("CMP"),
            {"kind": "counter_rule", "experiment_control": True, **rule},
            {"comparisons": 1, "total_ops": 1},
        )

        return _record_experiment_command(
            context,
            "CounterCmd",
            rule,
            {"comparisons": 1, "total_ops": 1},
        )


class StopIfCmdEval(ASTNode.IAttrEval):
    """
    stop_if total_ops > 10000
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        args = _command_args(children, "stop_if")
        if not args:
            return EvalResult(value=None, counters={})

        condition_node = args[0]
        rule = {"condition": _describe_node(condition_node)}

        state = _experiment_state(context)
        state["stop_if"] = rule
        state["stop_if_node"] = condition_node

        _safe_publish(
            context,
            _op("CMP"),
            {"kind": "stop_if", "experiment_control": True, **rule},
            {"comparisons": 1, "total_ops": 1},
        )

        return _record_experiment_command(
            context,
            "StopIfCmd",
            rule,
            {"comparisons": 1, "total_ops": 1},
        )


class RunCmdEval(ASTNode.IAttrEval):
    """
    run
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        args = _command_args(children, "run")
        state = _experiment_state(context)

        run_payload = []
        for child in args:
            run_payload.append(_describe_node(child))

        state["run_requested"] = True
        if run_payload:
            state["run_args"] = run_payload

        run_result = None
        run_counters: Dict[str, int] = {}
        if args:
            result = _ensure_result(args[0].evaluated(context))
            run_result = result.value
            run_counters = result.counters
            state["last_run_result"] = run_result
            state.setdefault("run_results", []).append(run_result)
            _check_stop_if(context)

        _safe_publish(
            context,
            _op("CALL"),
            {"kind": "run", "args": run_payload, "result": run_result},
            {"calls": 1, "total_ops": 1},
        )

        return _record_experiment_command(
            context,
            "RunCmd",
            run_result,
            _merge_all(run_counters, {"calls": 1, "total_ops": 1}),
            {"args": run_payload},
        )


class ExportCmdEval(ASTNode.IAttrEval):
    """
    export results.csv
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        args = _command_args(children, "export")
        if not args:
            return EvalResult(value=None, counters={})

        # Обычно имя файла — последний аргумент
        filename_value, filename_counters = _literal_or_eval(args[-1], context)
        filename = _strip_quotes(str(filename_value))

        state = _experiment_state(context)
        state["export_file"] = filename

        _safe_publish(
            context,
            _op("WRITE"),
            {"kind": "export", "file": filename},
            {"writes": 1, "total_ops": 1},
        )

        return _record_experiment_command(
            context,
            "ExportCmd",
            filename,
            _merge_all(filename_counters, {"writes": 1, "total_ops": 1}),
            {"file": filename},
        )


class ArgumentListEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        items: List[Any] = []
        counters: Dict[str, int] = {}
        for child in children:
            if getattr(child, "type", None) == ASTNode.Type.NONTERMINAL:
                res = _ensure_result(child.evaluated(context))
                items.append(res.value)
                counters = _merge_all(counters, res.counters)
        return EvalResult(value=items, counters=counters)


class ExpCommandEval(ASTNode.IAttrEval):
    """
    Универсальная обёртка для команд эксперимента.
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        payload = []
        counters: Dict[str, int] = {}
        for child in children:
            # Для экспорта/настроек полезнее хранить безопасное описание,
            # а не выполнять дочерние узлы дважды.
            if getattr(child, "type", None) == ASTNode.Type.TOKEN:
                payload.append(_describe_node(child))
            else:
                res = _ensure_result(child.evaluated(context))
                payload.append(res.value)
                counters = _merge_all(counters, res.counters)

        state = _experiment_state(context)
        state.setdefault("exp_commands", []).append(payload)

        return EvalResult(value=payload, counters=counters)


class ExpCommandListEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        values: List[Any] = []
        counters: Dict[str, int] = {}
        for child in children:
            res = _ensure_result(child.evaluated(context))
            values.append(res.value)
            counters = _merge_all(counters, res.counters)

        state = _experiment_state(context)
        state["command_list"] = values
        return EvalResult(value=values, counters=counters)


# -------------------------
# Выражения
# -------------------------

class FactorEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if not children:
            text = _strip_quotes(value)
            try:
                return EvalResult(value=_parse_number(text), counters={})
            except Exception:
                return EvalResult(value=text, counters={})

        if len(children) == 1:
            return _ensure_result(children[0].evaluated(context))

        # Унарные операции: -x / +x
        if len(children) == 2:
            op_text = _strip_quotes(getattr(children[0], "value", ""))
            rhs = _ensure_result(children[1].evaluated(context))
            if op_text == "-":
                return EvalResult(value=-rhs.value, counters=rhs.counters)
            if op_text == "+":
                return EvalResult(value=+rhs.value, counters=rhs.counters)
            return rhs

        # Скобки: ( expr )
        if len(children) == 3:
            first_val = _strip_quotes(getattr(children[0], "value", ""))
            if first_val == "(":
                return _ensure_result(children[1].evaluated(context))

        # Доступ к элементу массива: ident [ expr, ... ]
        if len(children) >= 4:
            second_val = _strip_quotes(getattr(children[1], "value", ""))
            if second_val == "[":
                arr_name = _strip_quotes(getattr(children[0], "value", ""))
                arr = context.symbol_table.get(arr_name)

                indices = []
                idx_counters: Dict[str, int] = {}
                for ch in children[2:]:
                    if getattr(ch, "type", None) == ASTNode.Type.NONTERMINAL:
                        idx_res = _ensure_result(ch.evaluated(context))
                        indices.append(idx_res.value)
                        idx_counters = _merge_all(idx_counters, idx_res.counters)

                result = arr
                for idx in indices:
                    result = result[int(idx)]

                _safe_publish(
                    context,
                    _op("READ"),
                    {"var": arr_name, "indices": [int(x) for x in indices]},
                    {"reads": 1, "total_ops": 1},
                )

                return EvalResult(
                    value=result,
                    counters=_merge_all(idx_counters, {"reads": 1, "total_ops": 1}),
                )

        return _eval_sequence(children, context)


class TermEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if not children:
            return EvalResult(value=None, counters={})

        if len(children) == 1:
            return _ensure_result(children[0].evaluated(context))

        current = _ensure_result(children[0].evaluated(context))
        counters = dict(current.counters)
        i = 1
        while i + 1 < len(children):
            op = _strip_quotes(getattr(children[i], "value", ""))
            rhs = _ensure_result(children[i + 1].evaluated(context))
            current = EvalResult(
                value=_binary_arith(current.value, rhs.value, op),
                counters={},
            )
            counters = _merge_all(counters, rhs.counters, {"total_ops": 1})
            i += 2

        return EvalResult(value=current.value, counters=counters)


class ExpressionEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if not children:
            return EvalResult(value=None, counters={})

        if len(children) == 1:
            return _ensure_result(children[0].evaluated(context))

        current = _ensure_result(children[0].evaluated(context))
        counters = dict(current.counters)
        i = 1
        while i + 1 < len(children):
            op = _strip_quotes(getattr(children[i], "value", ""))
            rhs = _ensure_result(children[i + 1].evaluated(context))
            current = EvalResult(
                value=_binary_arith(current.value, rhs.value, op),
                counters={},
            )
            counters = _merge_all(counters, rhs.counters, {"total_ops": 1})
            i += 2

        return EvalResult(value=current.value, counters=counters)


class ComparisonEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if len(children) == 1:
            return _ensure_result(children[0].evaluated(context))

        if len(children) < 3:
            return _eval_sequence(children, context)

        left_res = _ensure_result(children[0].evaluated(context))
        right_res = _ensure_result(children[2].evaluated(context))
        operator = _strip_quotes(getattr(children[1], "value", ""))

        result_val = _compare(left_res.value, right_res.value, operator)

        _safe_publish(
            context,
            _op("CMP"),
            {"op": operator, "left": left_res.value, "right": right_res.value, "result": result_val},
            {"comparisons": 1, "total_ops": 1},
        )

        final_counters = _merge_all(
            left_res.counters,
            right_res.counters,
            {"comparisons": 1, "total_ops": 1},
        )

        return EvalResult(value=result_val, counters=final_counters)


# -------------------------
# Операторы и управляющие конструкции
# -------------------------

class AssignmentEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if len(children) < 3:
            return _eval_sequence(children, context)

        # Найти позицию "=" среди дочерних узлов
        eq_idx = None
        for idx, ch in enumerate(children):
            if _strip_quotes(getattr(ch, "value", "")) == "=" and getattr(ch, "type", None) == ASTNode.Type.TOKEN:
                eq_idx = idx
                break

        if eq_idx is None or eq_idx + 1 >= len(children):
            return _eval_sequence(children, context)

        target_name = _strip_quotes(getattr(children[0], "value", ""))
        expr_res = _ensure_result(children[eq_idx + 1].evaluated(context))

        # Присваивание элементу массива: arr[i] = val
        if eq_idx > 1:
            indices = []
            idx_counters: Dict[str, int] = {}
            for ch in children[1:eq_idx]:
                if getattr(ch, "type", None) == ASTNode.Type.NONTERMINAL:
                    idx_res = _ensure_result(ch.evaluated(context))
                    indices.append(idx_res.value)
                    idx_counters = _merge_all(idx_counters, idx_res.counters)

            arr = context.symbol_table.get(target_name)
            if arr is not None and indices:
                current = arr
                for i_val in indices[:-1]:
                    current = current[int(i_val)]
                current[int(indices[-1])] = expr_res.value

                _safe_publish(
                    context,
                    _op("WRITE"),
                    {"var": target_name, "indices": [int(x) for x in indices], "val": expr_res.value},
                    {"writes": 1, "total_ops": 1},
                )

                return EvalResult(
                    value=expr_res.value,
                    counters=_merge_all(expr_res.counters, idx_counters, {"writes": 1, "total_ops": 1}),
                )

        # Простое присваивание переменной
        context.symbol_table[target_name] = expr_res.value

        _safe_publish(
            context,
            _op("ASSIGN"),
            {"var": target_name, "val": expr_res.value},
            {"assignments": 1, "total_ops": 1},
        )

        local_counters = _merge_all(
            expr_res.counters,
            {"assignments": 1, "total_ops": 1},
        )

        return EvalResult(value=expr_res.value, counters=local_counters)


class IfStatementEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        # Дочерние: [IF, Condition, THEN, StatementList, ENDIF]  (5)
        #      или: [IF, Condition, THEN, StatementList, ELSE, StatementList, ENDIF]  (7)
        if len(children) < 5:
            return _eval_sequence(children, context)

        condition_node = children[1]
        then_block = children[3]

        cond_res = _ensure_result(condition_node.evaluated(context))

        _safe_publish(
            context,
            _op("BRANCH"),
            {"kind": "if", "cond_result": _truthy(cond_res.value)},
            {"branches": 1, "total_ops": 1},
        )

        branch_counters = {"branches": 1, "total_ops": 1}

        if _truthy(cond_res.value):
            block_res = _ensure_result(then_block.evaluated(context))
        elif len(children) >= 7:
            block_res = _ensure_result(children[5].evaluated(context))
        else:
            block_res = EvalResult(value=None, counters={})

        final_counters = _merge_all(cond_res.counters, branch_counters, block_res.counters)
        return EvalResult(value=block_res.value, counters=final_counters)


class WhileStatementEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        # Дочерние: [WHILE, Condition, DO, StatementList, ENDWHILE]  (5)
        if len(children) < 5:
            return _eval_sequence(children, context)

        cond_node = children[1]
        body_node = children[3]

        total_counters: Dict[str, int] = {}
        last_value = None

        while True:
            cond_res = _ensure_result(cond_node.evaluated(context))
            total_counters = _merge_all(total_counters, cond_res.counters)

            cond_bool = _truthy(cond_res.value)

            _safe_publish(
                context,
                _op("BRANCH"),
                {"kind": "while", "cond_result": cond_bool},
                {"branches": 1, "total_ops": 1},
            )
            total_counters = _merge_all(total_counters, {"branches": 1, "total_ops": 1})

            if not cond_bool:
                break

            body_res = _ensure_result(body_node.evaluated(context))
            total_counters = _merge_all(total_counters, body_res.counters)
            last_value = body_res.value

        return EvalResult(value=last_value, counters=total_counters)


class ForStatementEval(ASTNode.IAttrEval):
    """
    FOR ident FROM expr TO expr DO StatementList ENDFOR
    Дочерние: [FOR, ident, FROM, Expression, TO, Expression, DO, StatementList, ENDFOR]
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if len(children) < 8:
            return _eval_sequence(children, context)

        var_name = _strip_quotes(getattr(children[1], "value", ""))
        start_res = _ensure_result(children[3].evaluated(context))
        end_res = _ensure_result(children[5].evaluated(context))
        body_node = children[7]

        start_val = int(start_res.value)
        end_val = int(end_res.value)

        total_counters: Dict[str, int] = _merge_all(start_res.counters, end_res.counters)
        last_value = None

        for i in range(start_val, end_val + 1):
            context.symbol_table[var_name] = i

            _safe_publish(
                context,
                _op("ASSIGN"),
                {"var": var_name, "val": i, "kind": "for"},
                {"assignments": 1, "total_ops": 1},
            )
            total_counters = _merge_all(total_counters, {"assignments": 1, "total_ops": 1})

            _safe_publish(
                context,
                _op("BRANCH"),
                {"kind": "for", "cond_result": True},
                {"branches": 1, "total_ops": 1},
            )
            total_counters = _merge_all(total_counters, {"branches": 1, "total_ops": 1})

            body_res = _ensure_result(body_node.evaluated(context))
            total_counters = _merge_all(total_counters, body_res.counters)
            last_value = body_res.value

        # Финальная проверка условия (выход из цикла)
        _safe_publish(
            context,
            _op("BRANCH"),
            {"kind": "for", "cond_result": False},
            {"branches": 1, "total_ops": 1},
        )
        total_counters = _merge_all(total_counters, {"branches": 1, "total_ops": 1})

        return EvalResult(value=last_value, counters=total_counters)


class ForInStatementEval(ASTNode.IAttrEval):
    """
    for target in iterable : body
    """
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if len(children) < 6:
            return _eval_sequence(children, context)

        target_node = children[1]
        iterable_node = children[3]
        body_node = children[5]

        iterable_res = _ensure_result(iterable_node.evaluated(context))
        items = _iter_items(iterable_res.value)

        total_counters = dict(iterable_res.counters)
        last_value = None

        target_name = _strip_quotes(getattr(target_node, "value", ""))

        for item in items:
            context.symbol_table[target_name] = item

            _safe_publish(
                context,
                _op("ASSIGN"),
                {"var": target_name, "val": item, "kind": "for-in"},
                {"assignments": 1, "total_ops": 1},
            )
            total_counters = _merge_all(total_counters, {"assignments": 1, "total_ops": 1})

            body_res = _ensure_result(body_node.evaluated(context))
            total_counters = _merge_all(total_counters, body_res.counters)
            last_value = body_res.value

        return EvalResult(value=last_value, counters=total_counters)


class CallExprEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if not children:
            return EvalResult(value=None, counters={})

        callee_node = children[0]
        callee_name = _strip_quotes(getattr(callee_node, "value", ""))

        # Пропускаем ключевые токены "(", ")", "," — берём только нетерминалы
        arg_values: List[Any] = []
        arg_counters: Dict[str, int] = {}
        for arg_node in children[1:]:
            if getattr(arg_node, "type", None) == ASTNode.Type.NONTERMINAL:
                arg_res = _ensure_result(arg_node.evaluated(context))
                sub = getattr(arg_node, "subtype", "")
                if sub == "ArgumentList" and isinstance(arg_res.value, list):
                    arg_values.extend(arg_res.value)
                else:
                    arg_values.append(arg_res.value)
                arg_counters = _merge_all(arg_counters, arg_res.counters)

        result_value, call_counters = _builtin_call(callee_name, arg_values, context)

        _safe_publish(
            context,
            _op("CALL"),
            {"callee": callee_name, "args": arg_values, "result": result_value},
            call_counters,
        )

        return EvalResult(
            value=result_value,
            counters=_merge_all(arg_counters, call_counters),
        )


class CallStatementEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        if not children:
            return EvalResult(value=None, counters={})
        if len(children) == 1:
            return _ensure_result(children[0].evaluated(context))
        return _ensure_result(CallExprEval()(value, children, context))


class CollectionLiteralEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        items: List[Any] = []
        counters: Dict[str, int] = {}

        for child in children:
            if getattr(child, "type", None) == ASTNode.Type.NONTERMINAL:
                res = _ensure_result(child.evaluated(context))
                items.append(res.value)
                counters = _merge_all(counters, res.counters)

        counters = _merge_all(counters, {"allocations": 1, "total_ops": 1})

        _safe_publish(
            context,
            _op("ALLOC"),
            {"kind": "collection_literal", "size": len(items)},
            {"allocations": 1, "total_ops": 1},
        )

        return EvalResult(value=items, counters=counters)


class ReturnStatementEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        # Дочерние: [RETURN, Expression] или [RETURN]
        expr_node = None
        for ch in children:
            if getattr(ch, "type", None) == ASTNode.Type.NONTERMINAL:
                expr_node = ch
                break
        res = _ensure_result(expr_node.evaluated(context)) if expr_node else EvalResult(value=None, counters={})

        _safe_publish(
            context,
            _op("RETURN"),
            {"value": res.value},
            {"returns": 1, "total_ops": 1},
        )

        return EvalResult(
            value=res.value,
            counters=_merge_all(res.counters, {"returns": 1, "total_ops": 1}),
        )


class YieldStatementEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        res = _ensure_result(children[0].evaluated(context)) if children else EvalResult(value=None, counters={})

        _safe_publish(
            context,
            _op("YIELD"),
            {"value": res.value},
            {"returns": 1, "total_ops": 1},
        )

        return EvalResult(
            value=res.value,
            counters=_merge_all(res.counters, {"returns": 1, "total_ops": 1}),
        )


class ExitStatementEval(ASTNode.IAttrEval):
    def __call__(self, value: str, children: List["ASTNode"], context: "EvalContext") -> EvalResult:
        res = _ensure_result(children[0].evaluated(context)) if children else EvalResult(value=None, counters={})

        _safe_publish(
            context,
            _op("EXIT"),
            {"value": res.value},
            {"total_ops": 1},
        )

        return EvalResult(
            value=res.value,
            counters=_merge_all(res.counters, {"total_ops": 1}),
        )


# -------------------------
# Регистрация visitor-ов
# -------------------------

def register_evaluators():
    NT = ASTNode.Type.NONTERMINAL
    T = ASTNode.Type.TOKEN
    EvalRegistry.clear()

    EvalRegistry.register(T, "ident", IdentTokenEval())
    EvalRegistry.register(T, "number", NumberTokenEval())
    EvalRegistry.register(T, "string", StringTokenEval())
    EvalRegistry.register(T, "whitespace", WhitespaceTokenEval())

    EvalRegistry.register(NT, "Program", ProgramEval())
    EvalRegistry.register(NT, "SubroutineBlock", SubroutineBlockEval())
    EvalRegistry.register(NT, "FuncBlock", FuncBlockEval())
    EvalRegistry.register(NT, "ProcBlock", ProcBlockEval())
    EvalRegistry.register(NT, "IterBlock", IterBlockEval())
    EvalRegistry.register(NT, "AlgorithmBlock", AlgorithmBlockEval())
    EvalRegistry.register(NT, "ExperimentBlock", ExperimentBlockEval())

    EvalRegistry.register(NT, "ParamDecl", ParamDeclEval())
    EvalRegistry.register(NT, "TypeDecl", TypeDeclEval())
    EvalRegistry.register(NT, "PrimitiveType", PrimitiveTypeEval())

    EvalRegistry.register(NT, "StatementList", StatementListEval())
    EvalRegistry.register(NT, "Statement", StatementEval())
    EvalRegistry.register(NT, "Assignment", AssignmentEval())
    EvalRegistry.register(NT, "IfStatement", IfStatementEval())
    EvalRegistry.register(NT, "WhileStatement", WhileStatementEval())
    EvalRegistry.register(NT, "ForStatement", ForStatementEval())
    EvalRegistry.register(NT, "ForInStatement", ForInStatementEval())

    EvalRegistry.register(NT, "CallStatement", CallStatementEval())
    EvalRegistry.register(NT, "ReturnStatement", ReturnStatementEval())
    EvalRegistry.register(NT, "YieldStatement", YieldStatementEval())
    EvalRegistry.register(NT, "ExitStatement", ExitStatementEval())

    EvalRegistry.register(NT, "Condition", ConditionEval())
    EvalRegistry.register(NT, "LogicalTerm", LogicalTermEval())
    EvalRegistry.register(NT, "LogicalFactor", LogicalFactorEval())
    EvalRegistry.register(NT, "Comparison", ComparisonEval())

    EvalRegistry.register(NT, "Expression", ExpressionEval())
    EvalRegistry.register(NT, "Term", TermEval())
    EvalRegistry.register(NT, "Factor", FactorEval())

    EvalRegistry.register(NT, "CallExpr", CallExprEval())
    EvalRegistry.register(NT, "CollectionLiteral", CollectionLiteralEval())
    EvalRegistry.register(NT, "ArgumentList", ArgumentListEval())

    EvalRegistry.register(NT, "ExpCommandList", ExpCommandListEval())
    EvalRegistry.register(NT, "ExpCommand", ExpCommandEval())

    EvalRegistry.register(NT, "ParamCmd", ParamCmdEval())
    EvalRegistry.register(NT, "TrialsCmd", TrialsCmdEval())
    EvalRegistry.register(NT, "SeedCmd", SeedCmdEval())
    EvalRegistry.register(NT, "GenCmd", GenCmdEval())
    EvalRegistry.register(NT, "CounterCmd", CounterCmdEval())
    EvalRegistry.register(NT, "StopIfCmd", StopIfCmdEval())
    EvalRegistry.register(NT, "RunCmd", RunCmdEval())
    EvalRegistry.register(NT, "ExportCmd", ExportCmdEval())

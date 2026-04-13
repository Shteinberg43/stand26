from copy import deepcopy
from enum import Enum
from typing import List, Tuple, Dict


class NodeType(str, Enum):
    NONTERMINAL = "nonterminal"
    TERMINAL = "terminal"
    KEY = "key"
    END = "end"


class NodeTypeLegacy(str, Enum):
    TERMINAL = "terminal"
    KEY = "key"
    NONTERMINAL = "nonterminal"
    START = "start"
    END = "end"


class NodeLegacy:
    """Это старый объект узла правила, который нужно переработать."""

    def __init__(self, type, str_, nextNodes=None, nonterminal=None, terminal=None):

        self.type = type
        self.str = str_
        self.nextNodes: list | None = (nextNodes, [])[nextNodes is None]
        self.nonterminal: str | None = nonterminal
        self.terminal: str | None = terminal

    @staticmethod
    def optional_field_to_text(field_value):
        return field_value if field_value is None else f"'{field_value}'"

    def __str__(self):
        res = (
            "NodeLegacy("
            f"type= '{self.type}', "
            + f"str_= '{self.str}', "
            + f"nonterminal='{self.nonterminal}', "
            + f"terminal='{self.terminal}', "
        )
        res += "nextNodes=["
        for node in self.nextNodes:
            res += f"{node}"
        return res + "])"

    def __repr__(self):
        res = (
            "NodeLegacy("
            f"type= {self.type}, "
            + f"str_= '{self.str}', "
            + f"nonterminal= {self.optional_field_to_text(self.nonterminal)}, "
            + f"terminal= {self.optional_field_to_text(self.terminal)}, "
        )
        res += "nextNodes= ["
        for node in self.nextNodes:
            res += f"{node}"
        return res + "])"


Edge = Tuple[str, str, str]


class RuleGraph:

    def __init__(self, name: str, nodes: Dict[str, NodeLegacy], edges):
        self.name: str = name
        self.nodes: Dict[str, NodeLegacy] = nodes
        self.edges: List[Edge] = edges

    @staticmethod
    def get_start_and_end(nodes: Dict[str, NodeLegacy]):
        starts = list(
            filter(lambda x: x[1].type == NodeTypeLegacy.START, nodes.items())
        )
        ends = list(filter(lambda x: x[1].type == NodeTypeLegacy.END, nodes.items()))

        if len(starts) != 1:
            raise Exception(f"Incorrect number of starts")

        if len(ends) != 1:
            raise Exception(f"Incorrect number of ends")
        return starts[0][1], ends[0][1]

    def _get_edge_structure(self):

        starts = list(set(map(lambda x: x[0], self.edges)))
        res = {start: [] for start in starts}

        for edge in self.edges:
            res[edge[0]].append((edge[1], edge[2]))

        return res

    def to_tn_rule(self):

        edge_structure = self._get_edge_structure()
        wirthNodes = deepcopy(self.nodes)
        start, _ = self.get_start_and_end(wirthNodes)

        for nodeName, node in wirthNodes.items():
            outgoingEdges = edge_structure.get(nodeName, [])
            for edge in outgoingEdges:
                code = edge[1]
                node.nextNodes.append((wirthNodes[edge[0]], code))

        return self.name, start

    def to_text(self) -> str:

        nodes_str = (
            "{"
            + ",\n".join(
                list(map(lambda x: f"'{x[0]}': {x[1].__repr__()}", self.nodes.items()))
            )
            + "}"
        )

        edges_str = "[" + ",\n".join(list(map(lambda x: str(x), self.edges))) + "]"

        body = (
            f"RuleGraph( name='{self.name}', \n"
            f"nodes={nodes_str}, \n"
            f"edges={edges_str})"
        )

        return body

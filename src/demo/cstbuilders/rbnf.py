from copy import deepcopy
from src.demo.bases.coremodules.cstbuilder import CSTBuilder
from src.demo.models.grammar import GrammarObject
from src.demo.models.nodes import ASTNode
from src.demo.models.tn_rule import NodeType, NodeLegacy
from src.demo.models.tokenizer_tokens import Token
from typing import TypeVar, List

TWalkStep = TypeVar("TWalkStep", bound="WalkStep")


class WalkStep:
    def __init__(
        self,
        parent_state: TWalkStep = None,
        pos: int = 0,
        node: NodeLegacy = [],
        rule_index: int = 0,
        nonterm: str = "",
        depth: int = -1,
    ):
        self.parent_state = parent_state
        self.pos = pos
        self.node = node
        self.rule_index = rule_index
        self.nonterm = nonterm
        self.depth = depth

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return f"Step: pos = {self.pos}, nonterminal: {self.nonterm}"


class CSTRBNFBuilder(CSTBuilder):
    def __init__(self, meta_grammar: GrammarObject, debug: bool = False):
        self.meta_grammar = meta_grammar
        self.states: list[WalkStep] = []
        self.tokens: list[Token] = []
        self.end: int = 0
        self.axiom: str = ""
        self._debug = debug
        self.__logs: list[str] = []
        self.depth: int = 0
        self.max_pos: int = 0

    def __ret(self):
        snap = deepcopy(self.states)
        self.states[-1].rule_index += 1
        while self.states[-1].rule_index >= len(self.states[-1].node.nextNodes):
            self.states.pop()
            self.depth -= 1
            if len(self.states) == 0:
                print(self.__ast)
                error = f"Current token: {self.tokens[snap[-1].pos].repr()}\r\n"
                self._log_ret(error)
                error += f"Furthest token reached: {self.tokens[self.max_pos if self.max_pos < self.end else self.end].repr()}\r\n"
                error += "States to crash:\r\n"
                for step in snap:
                    info = str(step)
                    error += f"{info}\r\n"
                    self._log_ret(info)
                raise Exception(f"Ran out of states: \r\n{error}")
            self.states[-1].rule_index += 1

    def __walk(self):
        self.states = [
            WalkStep(
                node=self.meta_grammar.syntax_info[self.axiom],
                nonterm=self.axiom,
                depth=0,
            )
        ]
        counter = 0
        limit = 100
        while True:
            counter += 1
            print(f"Iteration {counter}")
            state = self.states[-1]
            pos = state.pos
            if pos > self.max_pos:
                self.max_pos = pos
            node = state.node
            depth = state.depth
            rule = node.nextNodes[state.rule_index]
            if NodeType.END == rule[0].type:
                self._walk_details(pos, depth, rule[0].type.value, rule[0].nonterminal)
                self._print_last_log()
                parent_state = state.parent_state
                self.depth -= 1
                if parent_state is None:
                    if pos == self.end:
                        return
                    else:
                        self.__ret()
                        continue

                if parent_state.parent_state is not None:
                    pass

                self.states.append(
                    WalkStep(
                        parent_state.parent_state,
                        pos,
                        parent_state.node.nextNodes[parent_state.rule_index][0],
                        0,
                        parent_state.nonterm,
                        (
                            parent_state.parent_state.depth
                            if parent_state.parent_state
                            else 0
                        ),
                    )
                )
                continue
            elif NodeType.NONTERMINAL == rule[0].type:
                self._walk_details(pos, depth, rule[0].type.value, rule[0].nonterminal)
                self._print_last_log()
                if rule[0].nonterminal not in self.meta_grammar.syntax_info:
                    raise Exception(
                        f"Failed to find '{rule[0].nonterminal}' description in {self.go.syntax_info}\r\nCurrent token: {self.tokens[pos].repr()}"
                    )
                self.states.append(
                    WalkStep(
                        state,
                        pos,
                        self.meta_grammar.syntax_info[rule[0].nonterminal],
                        0,
                        rule[0].nonterminal,
                        depth + 1,
                    )
                )
                self.depth += 1
                continue
            if pos >= self.end:
                self.__ret()
                continue
            new_token = self.tokens[pos]
            if (
                NodeType.KEY == rule[0].type
                and Token.Type.KEY == new_token.token_type
                and new_token.str == rule[0].str
            ):
                self._walk_details(pos, depth, rule[0].type.value, rule[0].str)
                self._print_last_log()
                self.states.append(
                    WalkStep(
                        state.parent_state,
                        pos + 1,
                        rule[0],
                        0,
                        state.nonterm,
                        state.depth,
                    )
                )
                continue
            elif (
                NodeType.TERMINAL == rule[0].type
                and Token.Type.TERMINAL == new_token.token_type
                and new_token.terminalType == rule[0].terminal
            ):
                self._walk_details(pos, depth, rule[0].type.value, rule[0].terminal)
                self._print_last_log()
                self.states.append(
                    WalkStep(
                        state.parent_state,
                        pos + 1,
                        rule[0],
                        0,
                        state.nonterm,
                        state.depth,
                    )
                )
                self.depth -= 1
                continue

            self.__ret()
            continue

    def build(self, tokens: List[Token]) -> ASTNode:
        self.tokens = tokens
        self.end = len(self.tokens)
        self.axiom = self.meta_grammar.axiom

        ast = ASTNode(ASTNode.Type.NONTERMINAL, self.axiom)
        self.__ast = ast
        ast.nonterminalType = self.axiom
        nodes_stack = [ast]
        self.__walk()
        for state in self.states:
            pos = state.pos
            node = state.node
            rule = node.nextNodes[state.rule_index]
            if NodeType.END == rule[0].type:
                parent_state = state.parent_state
                if parent_state is None:
                    if pos == self.end:
                        nodes_stack[-1].commands.append(rule[1])
                        return ast
                    else:
                        raise Exception(
                            f"Reached an end node, but {pos = }, {self.end = }"
                        )
                nodes_stack[-1].commands.append(rule[1])
                nodes_stack.pop()
                continue
            elif NodeType.NONTERMINAL == rule[0].type:
                if rule[0].nonterminal not in self.meta_grammar.syntax_info:
                    raise Exception(
                        f"Failed to find '{rule[0].nonterminal}' description in {self.go.syntax_info = }"
                    )
                new_nonterm = ASTNode(ASTNode.Type.NONTERMINAL, rule[0].nonterminal)
                new_nonterm.nonterminalType = rule[0].nonterminal
                nodes_stack[-1].children.append(new_nonterm)
                nodes_stack[-1].commands.append(rule[1])
                node = rule[0]
                nodes_stack.append(new_nonterm)
                continue
            if pos >= self.end:
                raise Exception(f"{pos = } exceeded {self.end = }")
            new_token = self.tokens[pos]
            if (
                NodeType.KEY == rule[0].type
                and Token.Type.KEY == new_token.token_type
                and new_token.str == rule[0].str
            ):
                element = ASTNode(ASTNode.Type.TOKEN, new_token.str)
                element.attribute = new_token.attribute
                element.value = new_token.str
                element.token = new_token
                nodes_stack[-1].children.append(element)
                nodes_stack[-1].commands.append(rule[1])
                continue
            elif (
                NodeType.TERMINAL == rule[0].type
                and Token.Type.TERMINAL == new_token.token_type
                and new_token.terminalType == rule[0].terminal
            ):
                element = ASTNode(ASTNode.Type.TOKEN, new_token.terminalType)
                element.attribute = new_token.attribute
                element.value = new_token.value
                element.token = new_token
                nodes_stack[-1].children.append(element)
                nodes_stack[-1].commands.append(rule[1])
                continue
            raise Exception(
                f"Current state of {rule = } and {new_token = } does not satisfy any of the cases."
            )
        return ast

    # region Logging part. Need to decompose
    def _log(self, message: str):
        """Логирование процесса построения"""
        if self._debug:
            built = f"[Builder] {message}"
            self.__logs.append(built)
            print(built)

    def _log_method(self, method: str, msg: str):
        if self._debug:
            built = f"[Builder.{method}] {msg}"
            self.__logs.append(built)
            # print(built)

    def _print_last_log(self):
        if self.__logs:
            print(self.__logs[-1])

    def _log_walk(self, msg: str):
        self._log_method("walk", msg)

    def _walk_details(self, pos: int, depth: int, branch: str, val: str):
        if pos < self.end:
            self._log_walk(
                f"{pos = }, {depth = }, {branch = }, rule for: {val}, token: {self.tokens[pos].repr()}"
            )

    def _log_build(self, msg: str):
        self._log_method("build", msg)

    def _log_ret(self, msg: str):
        self._log_method("ret", msg)

    def logs(self) -> list[str]:
        return self.__logs

    # endregion

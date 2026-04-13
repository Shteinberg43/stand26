from src.demo.bases.coremodules.tokenizer import TokenizerBase
from src.demo.models.tokenizer_tokens import Token
from typing import List
import re


class RBNFTokenizer(TokenizerBase):
    """Класс токенезатора для грамматики заданной
    в форме ebnf и написанной в .rbnf файлах"""

    def __init__(self, meta_grammar):
        super().__init__(meta_grammar)

        # Сначала добавляем ключевые слова как литералы
        for key_type, key_value in meta_grammar.keys:
            # Экранируем специальные символы в ключах
            pattern = re.escape(key_value)
            self.patterns.append((key_value, re.compile(f"{pattern}")))
        self.patterns = sorted(self.patterns, key=lambda t: len(t[0]), reverse=True)
        # Затем добавляем терминалы по убыванию специфичности
        # ordered_terminals = self.grammar.terminals.values()
        ordered_terminals = sorted(
            meta_grammar.terminals.values(), key=lambda t: len(t.pattern), reverse=True
        )
        for terminal in ordered_terminals:
            self.patterns.append((terminal.name, re.compile(f"{terminal.pattern}")))

    def tokenize(self, input_str: str) -> List[Token]:

        tokens = []
        position = 0
        line_num = 1
        column = 1
        input_len = len(input_str)

        while position < input_len:
            # Пропускаем пробелы
            if input_str[position].isspace():
                if input_str[position] == "\n":
                    line_num += 1
                    column = 1
                else:
                    column += 1
                position += 1
                continue

            match = None
            for token_type, pattern in self.patterns:
                if (regex_match := pattern.match(input_str, position)) is not None:
                    # print(token_type)
                    value = regex_match.group()

                    if token_type in self.terminal_list:
                        token = Token(
                            token_type=Token.Type.TERMINAL,
                            value=value,
                            line=line_num,
                            column=column,
                        )
                        token.terminalType = token_type

                    elif token_type in self.key_list:
                        token = Token(
                            token_type=Token.Type.KEY,
                            value=value,
                            line=line_num,
                            column=column,
                        )
                        token.str = token_type
                    else:
                        raise "Unexpected token!"

                    tokens.append(token)

                    # Обновляем позицию
                    length = len(value)
                    position += length if length > 0 else 1
                    column += length
                    break
            else:
                # Если не нашли совпадений
                tokes = "\n".join(map(lambda x: x.to_text(), tokens))
                context = input_str[position : position + 20]
                raise SyntaxError(
                    f"Unexpected token at line {line_num}, column {column}\n"
                    f"Context: {context}...\n"
                    f"Tokens: {tokes}"
                )

        return tokens

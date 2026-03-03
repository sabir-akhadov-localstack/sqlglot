from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects import Hive, Trino
from sqlglot.parser import Parser as _Parser
from sqlglot.tokens import TokenType, Token


def _using_statement(self: _TrinoParser) -> exp.Command:
    return self._parse_as_command(self._prev)


# Athena extensions to Trino's parser
class _TrinoParser(Trino.Parser):
    STATEMENT_PARSERS = {
        **Trino.Parser.STATEMENT_PARSERS,
        TokenType.USING: _using_statement,
    }


class Parser(_Parser):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        hive = kwargs.pop("hive", None) or Hive()
        trino = kwargs.pop("trino", None) or Trino()

        super().__init__(*args, **kwargs)

        self._hive_parser = hive.parser(*args, **{**kwargs, "dialect": hive})
        self._trino_parser = _TrinoParser(*args, **{**kwargs, "dialect": trino})

    def parse(
        self, raw_tokens: t.List[Token], sql: t.Optional[str] = None
    ) -> t.List[t.Optional[exp.Expr]]:
        if raw_tokens and raw_tokens[0].token_type == TokenType.HIVE_TOKEN_STREAM:
            return self._hive_parser.parse(raw_tokens[1:], sql)

        return self._trino_parser.parse(raw_tokens, sql)

    def parse_into(
        self,
        expression_types: exp.IntoType,
        raw_tokens: t.List[Token],
        sql: t.Optional[str] = None,
    ) -> t.List[t.Optional[exp.Expr]]:
        if raw_tokens and raw_tokens[0].token_type == TokenType.HIVE_TOKEN_STREAM:
            return self._hive_parser.parse_into(expression_types, raw_tokens[1:], sql)

        return self._trino_parser.parse_into(expression_types, raw_tokens, sql)

from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects.postgres import Postgres
from sqlglot.helper import seq_get
from sqlglot.parsers.postgres import Parser as _PostgresParser
from sqlglot.tokens import TokenType


def _map_parser(self: Parser) -> exp.Expr:
    return self._parse_map()


def _farrow_lambda(self: Parser, expressions: t.List) -> exp.Kwarg:
    return self.expression(
        exp.Kwarg, this=seq_get(expressions, 0), expression=self._parse_assignment()
    )


class Parser(_PostgresParser):
    NO_PAREN_FUNCTION_PARSERS = {
        **Postgres.Parser.NO_PAREN_FUNCTION_PARSERS,
        "MAP": _map_parser,
    }

    LAMBDAS = {
        **Postgres.Parser.LAMBDAS,
        TokenType.FARROW: _farrow_lambda,
    }

    def _parse_lambda_arg(self) -> t.Optional[exp.Expr]:
        return self._parse_field()

    def _parse_map(self) -> exp.ToMap:
        if self._match(TokenType.L_PAREN):
            to_map = self.expression(exp.ToMap, this=self._parse_select())
            self._match_r_paren()
            return to_map

        if not self._match(TokenType.L_BRACKET):
            self.raise_error("Expecting [")

        entries = [
            exp.PropertyEQ(this=e.this, expression=e.expression)
            for e in self._parse_csv(self._parse_lambda)
        ]

        if not self._match(TokenType.R_BRACKET):
            self.raise_error("Expecting ]")

        return self.expression(exp.ToMap, this=self.expression(exp.Struct, expressions=entries))

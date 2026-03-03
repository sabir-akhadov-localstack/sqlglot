from __future__ import annotations

import typing as t

from sqlglot import exp, parser
from sqlglot.parsers.presto import Parser as _PrestoParser, _PRESTO_FUNCTIONS, _PRESTO_FUNCTION_PARSERS
from sqlglot.tokens import TokenType


def _trim_parser(self: Parser) -> exp.Expr:
    return self._parse_trim()


def _json_query_parser(self: Parser) -> exp.Expr:
    return self._parse_json_query()


def _json_value_parser(self: Parser) -> exp.Expr:
    return self._parse_json_value()


def _listagg_parser(self: Parser) -> exp.Expr:
    return self._parse_string_agg()


class Parser(_PrestoParser):
    FUNCTIONS = {
        **_PRESTO_FUNCTIONS,
        "VERSION": exp.CurrentVersion.from_arg_list,
    }

    FUNCTION_PARSERS = {
        **_PRESTO_FUNCTION_PARSERS,
        "TRIM": _trim_parser,
        "JSON_QUERY": _json_query_parser,
        "JSON_VALUE": _json_value_parser,
        "LISTAGG": _listagg_parser,
    }

    JSON_QUERY_OPTIONS: parser.OPTIONS_TYPE = {
        **dict.fromkeys(
            ("WITH", "WITHOUT"),
            (
                ("WRAPPER"),
                ("ARRAY", "WRAPPER"),
                ("CONDITIONAL", "WRAPPER"),
                ("CONDITIONAL", "ARRAY", "WRAPPED"),
                ("UNCONDITIONAL", "WRAPPER"),
                ("UNCONDITIONAL", "ARRAY", "WRAPPER"),
            ),
        ),
    }

    def _parse_json_query_quote(self) -> t.Optional[exp.JSONExtractQuote]:
        if not (
            self._match_text_seq("KEEP", "QUOTES") or self._match_text_seq("OMIT", "QUOTES")
        ):
            return None

        return self.expression(
            exp.JSONExtractQuote,
            option=self._tokens[self._index - 2].text.upper(),
            scalar=self._match_text_seq("ON", "SCALAR", "STRING"),
        )

    def _parse_json_query(self) -> exp.JSONExtract:
        return self.expression(
            exp.JSONExtract,
            this=self._parse_bitwise(),
            expression=self._match(TokenType.COMMA) and self._parse_bitwise(),
            option=self._parse_var_from_options(self.JSON_QUERY_OPTIONS, raise_unmatched=False),
            json_query=True,
            quote=self._parse_json_query_quote(),
            on_condition=self._parse_on_condition(),
        )

from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects.dialect import build_date_delta, build_formatted_time
from sqlglot.helper import seq_get
from sqlglot.parser import _CAST_COLUMN_OPERATORS, _COLUMN_OPERATORS, _FACTOR
from sqlglot.parsers.hive import _HIVE_NO_PAREN_FUNCTION_PARSERS
from sqlglot.parsers.spark import Parser as _SparkParser, _SPARK_FUNCTIONS
from sqlglot.tokens import TokenType


def _build_uniform(args: t.List) -> exp.Uniform:
    return exp.Uniform(
        this=seq_get(args, 0), expression=seq_get(args, 1), seed=seq_get(args, 2)
    )


def _curdate_parser(self: Parser) -> exp.CurrentDate:
    return self._parse_curdate()


def _qdcolon_column_operator(self: Parser, this: exp.Expr, to: exp.Expr) -> exp.Expr:
    return self.build_cast(
        False,
        this=this,
        to=to,
    )


class Parser(_SparkParser):
    LOG_DEFAULTS_TO_LN = True
    STRICT_CAST = True
    COLON_IS_VARIANT_EXTRACT = True

    FUNCTIONS = {
        **_SPARK_FUNCTIONS,
        "GETDATE": exp.CurrentTimestamp.from_arg_list,
        "DATEADD": build_date_delta(exp.DateAdd),
        "DATE_ADD": build_date_delta(exp.DateAdd),
        "DATEDIFF": build_date_delta(exp.DateDiff),
        "DATE_DIFF": build_date_delta(exp.DateDiff),
        "NOW": exp.CurrentTimestamp.from_arg_list,
        "TO_DATE": build_formatted_time(exp.TsOrDsToDate, "databricks"),
        "UNIFORM": _build_uniform,
    }

    NO_PAREN_FUNCTION_PARSERS = {
        **_HIVE_NO_PAREN_FUNCTION_PARSERS,
        "CURDATE": _curdate_parser,
    }

    FACTOR = {
        **_FACTOR,
        TokenType.COLON: exp.JSONExtract,
    }

    COLUMN_OPERATORS = {
        **_COLUMN_OPERATORS,
        TokenType.QDCOLON: _qdcolon_column_operator,
    }
    CAST_COLUMN_OPERATORS = {
        *_CAST_COLUMN_OPERATORS,
        TokenType.QDCOLON,
    }

    def _parse_curdate(self) -> exp.CurrentDate:
        # CURDATE, an alias for CURRENT_DATE, has optional parentheses
        if self._match(TokenType.L_PAREN):
            self._match_r_paren()
        return self.expression(exp.CurrentDate)

from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects.dialect import build_date_delta, build_like
from sqlglot.helper import ensure_list, seq_get
from sqlglot.parsers.hive import _build_with_ignore_nulls
from sqlglot.parser import _PLACEHOLDER_PARSERS, _SET_PARSERS, _STATEMENT_PARSERS
from sqlglot.parsers.spark2 import Parser as _Spark2Parser, _build_as_cast, _SPARK2_FUNCTIONS, _SPARK2_FUNCTION_PARSERS
from sqlglot.tokens import TokenType


def _build_datediff(args: t.List) -> exp.Expr:
    """
    Although Spark docs don't mention the "unit" argument, Spark3 added support for
    it at some point. Databricks also supports this variant (see below).

    For example, in spark-sql (v3.3.1):
    - SELECT DATEDIFF('2020-01-01', '2020-01-05') results in -4
    - SELECT DATEDIFF(day, '2020-01-01', '2020-01-05') results in 4

    See also:
    - https://docs.databricks.com/sql/language-manual/functions/datediff3.html
    - https://docs.databricks.com/sql/language-manual/functions/datediff.html
    """
    unit = None
    this = seq_get(args, 0)
    expression = seq_get(args, 1)

    if len(args) == 3:
        unit = exp.var(t.cast(exp.Expr, this).name)
        this = args[2]

    return exp.DateDiff(
        this=exp.TsOrDsToDate(this=this), expression=exp.TsOrDsToDate(this=expression), unit=unit
    )


def _build_dateadd(args: t.List) -> exp.Expr:
    expression = seq_get(args, 1)

    if len(args) == 2:
        # DATE_ADD(startDate, numDays INTEGER)
        # https://docs.databricks.com/en/sql/language-manual/functions/date_add.html
        return exp.TsOrDsAdd(
            this=seq_get(args, 0), expression=expression, unit=exp.Literal.string("DAY")
        )

    # DATE_ADD / DATEADD / TIMESTAMPADD(unit, value integer, expr)
    # https://docs.databricks.com/en/sql/language-manual/functions/date_add3.html
    return exp.TimestampAdd(this=seq_get(args, 2), expression=expression, unit=seq_get(args, 0))


def _set_var_parser(self: "Parser") -> exp.Expression:
    return self._parse_set_item_assignment("VARIABLE")  # type: ignore


def _build_array_insert(args: t.List) -> exp.ArrayInsert:
    return exp.ArrayInsert(
        this=seq_get(args, 0),
        position=seq_get(args, 1),
        expression=seq_get(args, 2),
        offset=1,
    )


def _build_try_element_at(args: t.List) -> exp.Bracket:
    return exp.Bracket(
        this=seq_get(args, 0),
        expressions=ensure_list(seq_get(args, 1)),
        offset=1,
        safe=True,
    )


def _placeholder_l_brace_parser(self: "Parser") -> t.Optional[exp.Expr]:
    return self._parse_query_parameter()


def _substr_parser(self: "Parser") -> t.Optional[exp.Expr]:
    return self._parse_substring()


def _declare_statement(self: "Parser") -> exp.Declare:
    return self._parse_declare()  # type: ignore


_SPARK_FUNCTIONS: t.Dict[str, t.Callable] = {
    **_SPARK2_FUNCTIONS,
    "ANY_VALUE": _build_with_ignore_nulls(exp.AnyValue),
    "ARRAY_INSERT": _build_array_insert,
    "BIT_AND": exp.BitwiseAndAgg.from_arg_list,
    "BIT_GET": exp.Getbit.from_arg_list,
    "BIT_OR": exp.BitwiseOrAgg.from_arg_list,
    "BIT_XOR": exp.BitwiseXorAgg.from_arg_list,
    "BIT_COUNT": exp.BitwiseCount.from_arg_list,
    "CURDATE": exp.CurrentDate.from_arg_list,
    "DATE_ADD": _build_dateadd,
    "DATEADD": _build_dateadd,
    "MAKE_TIMESTAMP": exp.TimestampFromParts.from_arg_list,
    "TIMESTAMPADD": _build_dateadd,
    "TIMESTAMPDIFF": build_date_delta(exp.TimestampDiff),
    "TRY_ADD": exp.SafeAdd.from_arg_list,
    "TRY_MULTIPLY": exp.SafeMultiply.from_arg_list,
    "TRY_SUBTRACT": exp.SafeSubtract.from_arg_list,
    "DATEDIFF": _build_datediff,
    "DATE_DIFF": _build_datediff,
    "JSON_OBJECT_KEYS": exp.JSONKeys.from_arg_list,
    "LISTAGG": exp.GroupConcat.from_arg_list,
    "TIMESTAMP_LTZ": _build_as_cast("TIMESTAMP_LTZ"),
    "TIMESTAMP_NTZ": _build_as_cast("TIMESTAMP_NTZ"),
    "TRY_ELEMENT_AT": _build_try_element_at,
    "LIKE": build_like(exp.Like),
    "ILIKE": build_like(exp.ILike),
}

_SPARK_FUNCTION_PARSERS = {
    **_SPARK2_FUNCTION_PARSERS,
    "SUBSTR": _substr_parser,
}

_SPARK_STATEMENT_PARSERS = {
    **_STATEMENT_PARSERS,
    TokenType.DECLARE: _declare_statement,
}


class Parser(_Spark2Parser):
    SET_PARSERS = {
        **_SET_PARSERS,
        "VAR": _set_var_parser,
        "VARIABLE": _set_var_parser,
    }

    FUNCTIONS = _SPARK_FUNCTIONS

    PLACEHOLDER_PARSERS = {
        **_PLACEHOLDER_PARSERS,
        TokenType.L_BRACE: _placeholder_l_brace_parser,
    }

    def _parse_query_parameter(self) -> t.Optional[exp.Expr]:
        this = self._parse_id_var()
        self._match(TokenType.R_BRACE)
        return self.expression(exp.Placeholder, this=this, widget=True)

    FUNCTION_PARSERS = _SPARK_FUNCTION_PARSERS
    STATEMENT_PARSERS = _SPARK_STATEMENT_PARSERS

    def _parse_generated_as_identity(
        self,
    ) -> (
        exp.GeneratedAsIdentityColumnConstraint
        | exp.ComputedColumnConstraint
        | exp.GeneratedAsRowColumnConstraint
    ):
        this = super()._parse_generated_as_identity()
        if this.expression:
            return self.expression(exp.ComputedColumnConstraint, this=this.expression)
        return this

    def _parse_pivot_aggregation(self) -> t.Optional[exp.Expr]:
        # Spark 3+ and Databricks support non aggregate functions in PIVOT too, e.g
        # PIVOT (..., 'foo' AS bar FOR col_to_pivot IN (...))
        aggregate_expr = self._parse_function() or self._parse_disjunction()
        return self._parse_alias(aggregate_expr)

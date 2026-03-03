from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects.dialect import binary_from_function, build_formatted_time, pivot_column_names
from sqlglot.helper import ensure_list, seq_get
from sqlglot.parser import build_trim
from sqlglot.parsers.hive import Parser as _HiveParser, _HIVE_FUNCTIONS, _HIVE_FUNCTION_PARSERS
from sqlglot.tokens import TokenType


def _build_as_cast(to_type: str) -> t.Callable[[t.List], exp.Expr]:
    return lambda args: exp.Cast(this=seq_get(args, 0), to=exp.DataType.build(to_type))


def _build_date_trunc(args: t.List) -> exp.TimestampTrunc:
    return exp.TimestampTrunc(this=seq_get(args, 1), unit=exp.var(seq_get(args, 0)))


def _build_dayofmonth(args: t.List) -> exp.DayOfMonth:
    return exp.DayOfMonth(this=exp.TsOrDsToDate(this=seq_get(args, 0)))


def _build_dayofweek(args: t.List) -> exp.DayOfWeek:
    return exp.DayOfWeek(this=exp.TsOrDsToDate(this=seq_get(args, 0)))


def _build_dayofyear(args: t.List) -> exp.DayOfYear:
    return exp.DayOfYear(this=exp.TsOrDsToDate(this=seq_get(args, 0)))


def _build_element_at(args: t.List) -> exp.Bracket:
    return exp.Bracket(
        this=seq_get(args, 0),
        expressions=ensure_list(seq_get(args, 1)),
        offset=1,
        safe=False,
    )


def _build_from_utc_timestamp(args: t.List, dialect: t.Any = None) -> exp.AtTimeZone:
    return exp.AtTimeZone(
        this=exp.cast(
            seq_get(args, 0) or exp.Var(this=""),
            exp.DType.TIMESTAMP,
            dialect=dialect,
        ),
        zone=seq_get(args, 1),
    )


def _build_ltrim(args: t.List) -> exp.Expr:
    return build_trim(args, reverse_args=True)


def _build_rtrim(args: t.List) -> exp.Expr:
    return build_trim(args, is_left=False, reverse_args=True)


def _build_to_timestamp(args: t.List) -> exp.Expr:
    if len(args) == 1:
        return _build_as_cast("timestamp")(args)
    return build_formatted_time(exp.StrToTime, "spark")(args)


def _build_to_utc_timestamp(args: t.List, dialect: t.Any = None) -> exp.FromTimeZone:
    return exp.FromTimeZone(
        this=exp.cast(
            seq_get(args, 0) or exp.Var(this=""),
            exp.DType.TIMESTAMP,
            dialect=dialect,
        ),
        zone=seq_get(args, 1),
    )


def _build_trunc(args: t.List) -> exp.DateTrunc:
    return exp.DateTrunc(unit=seq_get(args, 1), this=seq_get(args, 0))


def _build_weekofyear(args: t.List) -> exp.WeekOfYear:
    return exp.WeekOfYear(this=exp.TsOrDsToDate(this=seq_get(args, 0)))


def _approx_percentile_parser(self: Parser) -> exp.Expr:
    return self._parse_quantile_function(exp.ApproxQuantile)


def _broadcast_parser(self: Parser) -> exp.Expr:
    return self._parse_join_hint("BROADCAST")


def _broadcastjoin_parser(self: Parser) -> exp.Expr:
    return self._parse_join_hint("BROADCASTJOIN")


def _mapjoin_parser(self: Parser) -> exp.Expr:
    return self._parse_join_hint("MAPJOIN")


def _merge_parser(self: Parser) -> exp.Expr:
    return self._parse_join_hint("MERGE")


def _shufflemerge_parser(self: Parser) -> exp.Expr:
    return self._parse_join_hint("SHUFFLEMERGE")


def _mergejoin_parser(self: Parser) -> exp.Expr:
    return self._parse_join_hint("MERGEJOIN")


def _shuffle_hash_parser(self: Parser) -> exp.Expr:
    return self._parse_join_hint("SHUFFLE_HASH")


def _shuffle_replicate_nl_parser(self: Parser) -> exp.Expr:
    return self._parse_join_hint("SHUFFLE_REPLICATE_NL")


_SPARK2_FUNCTIONS: t.Dict[str, t.Callable] = {
    **_HIVE_FUNCTIONS,
    "AGGREGATE": exp.Reduce.from_arg_list,
    "BOOLEAN": _build_as_cast("boolean"),
    "DATE": _build_as_cast("date"),
    "DATE_TRUNC": _build_date_trunc,
    "DAYOFMONTH": _build_dayofmonth,
    "DAYOFWEEK": _build_dayofweek,
    "DAYOFYEAR": _build_dayofyear,
    "DOUBLE": _build_as_cast("double"),
    "ELEMENT_AT": _build_element_at,
    "FLOAT": _build_as_cast("float"),
    "FORMAT_STRING": exp.Format.from_arg_list,
    "FROM_UTC_TIMESTAMP": _build_from_utc_timestamp,
    "LTRIM": _build_ltrim,
    "INT": _build_as_cast("int"),
    "MAP_FROM_ARRAYS": exp.Map.from_arg_list,
    "RLIKE": exp.RegexpLike.from_arg_list,
    "RTRIM": _build_rtrim,
    "SHIFTLEFT": binary_from_function(exp.BitwiseLeftShift),
    "SHIFTRIGHT": binary_from_function(exp.BitwiseRightShift),
    "STRING": _build_as_cast("string"),
    "SLICE": exp.ArraySlice.from_arg_list,
    "TIMESTAMP": _build_as_cast("timestamp"),
    "TO_TIMESTAMP": _build_to_timestamp,
    "TO_UNIX_TIMESTAMP": exp.StrToUnix.from_arg_list,
    "TO_UTC_TIMESTAMP": _build_to_utc_timestamp,
    "TRUNC": _build_trunc,
    "WEEKOFYEAR": _build_weekofyear,
}

_SPARK2_FUNCTION_PARSERS = {
    **_HIVE_FUNCTION_PARSERS,
    "APPROX_PERCENTILE": _approx_percentile_parser,
    "BROADCAST": _broadcast_parser,
    "BROADCASTJOIN": _broadcastjoin_parser,
    "MAPJOIN": _mapjoin_parser,
    "MERGE": _merge_parser,
    "SHUFFLEMERGE": _shufflemerge_parser,
    "MERGEJOIN": _mergejoin_parser,
    "SHUFFLE_HASH": _shuffle_hash_parser,
    "SHUFFLE_REPLICATE_NL": _shuffle_replicate_nl_parser,
}


class Parser(_HiveParser):
    TRIM_PATTERN_FIRST = True
    CHANGE_COLUMN_ALTER_SYNTAX = True

    FUNCTIONS = _SPARK2_FUNCTIONS
    FUNCTION_PARSERS = _SPARK2_FUNCTION_PARSERS

    def _parse_drop_column(self) -> t.Optional[exp.Drop | exp.Command]:
        return (
            self.expression(exp.Drop, this=self._parse_schema(), kind="COLUMNS")
            if self._match_text_seq("DROP", "COLUMNS")
            else None
        )

    def _pivot_column_names(self, aggregations: t.List[exp.Expr]) -> t.List[str]:
        if len(aggregations) == 1:
            return []
        return pivot_column_names(aggregations, dialect="spark")

from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects.dialect import (
    binary_from_function,
    build_formatted_time,
    build_replace_with_optional_replacement,
    build_regexp_extract,
    date_trunc_to_time,
)
from sqlglot.helper import seq_get
from sqlglot.parser import Parser as _Parser, _FUNCTIONS, _FUNCTION_PARSERS


def _build_approx_percentile(args: t.List) -> exp.Expr:
    if len(args) == 4:
        return exp.ApproxQuantile(
            this=seq_get(args, 0),
            weight=seq_get(args, 1),
            quantile=seq_get(args, 2),
            accuracy=seq_get(args, 3),
        )
    if len(args) == 3:
        return exp.ApproxQuantile(
            this=seq_get(args, 0), quantile=seq_get(args, 1), accuracy=seq_get(args, 2)
        )
    return exp.ApproxQuantile.from_arg_list(args)


def _build_from_unixtime(args: t.List) -> exp.Expr:
    if len(args) == 3:
        return exp.UnixToTime(
            this=seq_get(args, 0),
            hours=seq_get(args, 1),
            minutes=seq_get(args, 2),
        )
    if len(args) == 2:
        return exp.UnixToTime(this=seq_get(args, 0), zone=seq_get(args, 1))

    return exp.UnixToTime.from_arg_list(args)


def _build_to_char(args: t.List) -> exp.TimeToStr:
    fmt = seq_get(args, 1)
    if isinstance(fmt, exp.Literal):
        # We uppercase this to match Teradata's format mapping keys
        fmt.set("this", fmt.this.upper())

    # We use "teradata" on purpose here, because the time formats are different in Presto.
    # See https://prestodb.io/docs/current/functions/teradata.html?highlight=to_char#to_char
    return build_formatted_time(exp.TimeToStr, "teradata")(args)


def _build_bitwise_not(args: t.List) -> exp.BitwiseNot:
    return exp.BitwiseNot(this=seq_get(args, 0))


def _build_date_add(args: t.List) -> exp.DateAdd:
    return exp.DateAdd(
        this=seq_get(args, 2), expression=seq_get(args, 1), unit=seq_get(args, 0)
    )


def _build_date_diff(args: t.List) -> exp.DateDiff:
    return exp.DateDiff(
        this=seq_get(args, 2), expression=seq_get(args, 1), unit=seq_get(args, 0)
    )


def _build_element_at(args: t.List) -> exp.Bracket:
    return exp.Bracket(
        this=seq_get(args, 0), expressions=[seq_get(args, 1)], offset=1, safe=True
    )


def _build_from_utf8(args: t.List) -> exp.Decode:
    return exp.Decode(
        this=seq_get(args, 0), replace=seq_get(args, 1), charset=exp.Literal.string("utf-8")
    )


def _build_json_format(args: t.List) -> exp.JSONFormat:
    return exp.JSONFormat(
        this=seq_get(args, 0), options=seq_get(args, 1), is_json=True
    )


def _build_regexp_replace(args: t.List) -> exp.RegexpReplace:
    return exp.RegexpReplace(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        replacement=seq_get(args, 2) or exp.Literal.string(""),
    )


def _build_strpos(args: t.List) -> exp.StrPosition:
    return exp.StrPosition(
        this=seq_get(args, 0), substr=seq_get(args, 1), occurrence=seq_get(args, 2)
    )


def _build_to_utf8(args: t.List) -> exp.Encode:
    return exp.Encode(
        this=seq_get(args, 0), charset=exp.Literal.string("utf-8")
    )


def _build_sha256(args: t.List) -> exp.SHA2:
    return exp.SHA2(this=seq_get(args, 0), length=exp.Literal.number(256))


def _build_sha512(args: t.List) -> exp.SHA2:
    return exp.SHA2(this=seq_get(args, 0), length=exp.Literal.number(512))


_PRESTO_FUNCTIONS: t.Dict[str, t.Callable] = {
    **_FUNCTIONS,
    "ARBITRARY": exp.AnyValue.from_arg_list,
    "APPROX_DISTINCT": exp.ApproxDistinct.from_arg_list,
    "APPROX_PERCENTILE": _build_approx_percentile,
    "BITWISE_AND": binary_from_function(exp.BitwiseAnd),
    "BITWISE_NOT": _build_bitwise_not,
    "BITWISE_OR": binary_from_function(exp.BitwiseOr),
    "BITWISE_XOR": binary_from_function(exp.BitwiseXor),
    "CARDINALITY": exp.ArraySize.from_arg_list,
    "CONTAINS": exp.ArrayContains.from_arg_list,
    "DATE_ADD": _build_date_add,
    "DATE_DIFF": _build_date_diff,
    "DATE_FORMAT": build_formatted_time(exp.TimeToStr, "presto"),
    "DATE_PARSE": build_formatted_time(exp.StrToTime, "presto"),
    "DATE_TRUNC": date_trunc_to_time,
    "DAY_OF_WEEK": exp.DayOfWeekIso.from_arg_list,
    "DOW": exp.DayOfWeekIso.from_arg_list,
    "DOY": exp.DayOfYear.from_arg_list,
    "ELEMENT_AT": _build_element_at,
    "FROM_HEX": exp.Unhex.from_arg_list,
    "FROM_UNIXTIME": _build_from_unixtime,
    "FROM_UTF8": _build_from_utf8,
    "JSON_FORMAT": _build_json_format,
    "LEVENSHTEIN_DISTANCE": exp.Levenshtein.from_arg_list,
    "NOW": exp.CurrentTimestamp.from_arg_list,
    "REGEXP_EXTRACT": build_regexp_extract(exp.RegexpExtract),
    "REGEXP_EXTRACT_ALL": build_regexp_extract(exp.RegexpExtractAll),
    "REGEXP_REPLACE": _build_regexp_replace,
    "REPLACE": build_replace_with_optional_replacement,
    "ROW": exp.Struct.from_arg_list,
    "SEQUENCE": exp.GenerateSeries.from_arg_list,
    "SET_AGG": exp.ArrayUniqueAgg.from_arg_list,
    "SPLIT_TO_MAP": exp.StrToMap.from_arg_list,
    "STRPOS": _build_strpos,
    "SLICE": exp.ArraySlice.from_arg_list,
    "TO_CHAR": _build_to_char,
    "TO_UNIXTIME": exp.TimeToUnix.from_arg_list,
    "TO_UTF8": _build_to_utf8,
    "MD5": exp.MD5Digest.from_arg_list,
    "SHA256": _build_sha256,
    "SHA512": _build_sha512,
    "WEEK": exp.WeekOfYear.from_arg_list,
}

_PRESTO_FUNCTION_PARSERS = {k: v for k, v in _FUNCTION_PARSERS.items() if k != "TRIM"}


class Parser(_Parser):
    VALUES_FOLLOWED_BY_PAREN = False
    ZONE_AWARE_TIMESTAMP_CONSTRUCTOR = True

    FUNCTIONS = _PRESTO_FUNCTIONS
    FUNCTION_PARSERS = _PRESTO_FUNCTION_PARSERS

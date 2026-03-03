from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects.dialect import (
    Dialect,
    build_formatted_time,
    build_json_extract_path,
)
from sqlglot.helper import seq_get
from sqlglot.parser import _COLUMN_OPERATORS, _NO_PAREN_FUNCTIONS
from sqlglot.parsers.mysql import (
    Parser as _MySQLParser,
    _MYSQL_ALTER_PARSERS,
    _MYSQL_FUNCTION_PARSERS,
    _MYSQL_FUNCTIONS,
    _MYSQL_SHOW_PARSERS,
    _show_parser,
)
from sqlglot.tokens import TokenType


def cast_to_time6(
    expression: t.Optional[exp.Expr], time_type: exp.DType = exp.DType.TIME
) -> exp.Cast:
    return exp.Cast(
        this=expression,
        to=exp.DataType.build(
            time_type,
            expressions=[exp.DataTypeParam(this=exp.Literal.number(6))],
        ),
    )


def _build_time_format(args: t.List) -> exp.TimeToStr:
    return exp.TimeToStr(
        this=cast_to_time6(seq_get(args, 0)),
        format=Dialect["mysql"].format_time(seq_get(args, 1)),
    )


def _build_hour(args: t.List) -> exp.Cast:
    return exp.cast(
        exp.TimeToStr(
            this=cast_to_time6(seq_get(args, 0)),
            format=Dialect["mysql"].format_time(exp.Literal.string("%k")),
        ),
        exp.DType.INT,
    )


def _build_microsecond(args: t.List) -> exp.Cast:
    return exp.cast(
        exp.TimeToStr(
            this=cast_to_time6(seq_get(args, 0)),
            format=Dialect["mysql"].format_time(exp.Literal.string("%f")),
        ),
        exp.DType.INT,
    )


def _build_second(args: t.List) -> exp.Cast:
    return exp.cast(
        exp.TimeToStr(
            this=cast_to_time6(seq_get(args, 0)),
            format=Dialect["mysql"].format_time(exp.Literal.string("%s")),
        ),
        exp.DType.INT,
    )


def _build_minute(args: t.List) -> exp.Cast:
    return exp.cast(
        exp.TimeToStr(
            this=cast_to_time6(seq_get(args, 0)),
            format=Dialect["mysql"].format_time(exp.Literal.string("%i")),
        ),
        exp.DType.INT,
    )


def _build_monthname(args: t.List) -> exp.TimeToStr:
    return exp.TimeToStr(
        this=seq_get(args, 0),
        format=Dialect["mysql"].format_time(exp.Literal.string("%M")),
    )


def _build_weekday(args: t.List) -> exp.Expr:
    return exp.paren(exp.DayOfWeek(this=seq_get(args, 0)) + 5, copy=False) % 7


def _build_time_bucket(args: t.List) -> exp.DateBin:
    return exp.DateBin(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        origin=seq_get(args, 2),
    )


def _build_json_array_contains_string(args: t.List) -> exp.JSONArrayContains:
    return exp.JSONArrayContains(
        this=seq_get(args, 1),
        expression=seq_get(args, 0),
        json_type="STRING",
    )


def _build_json_array_contains_double(args: t.List) -> exp.JSONArrayContains:
    return exp.JSONArrayContains(
        this=seq_get(args, 1),
        expression=seq_get(args, 0),
        json_type="DOUBLE",
    )


def _build_json_array_contains_json(args: t.List) -> exp.JSONArrayContains:
    return exp.JSONArrayContains(
        this=seq_get(args, 1),
        expression=seq_get(args, 0),
        json_type="JSON",
    )


def _build_json_keys(args: t.List) -> exp.JSONKeys:
    return exp.JSONKeys(
        this=seq_get(args, 0),
        expressions=args[1:],
    )


def _build_json_build_array(args: t.List) -> exp.JSONArray:
    return exp.JSONArray(expressions=args)


def _build_json_build_object(args: t.List) -> exp.JSONObject:
    return exp.JSONObject(expressions=args)


def _build_dayname(args: t.List) -> exp.TimeToStr:
    return exp.TimeToStr(
        this=seq_get(args, 0),
        format=Dialect["mysql"].format_time(exp.Literal.string("%W")),
    )


def _build_timestampdiff(args: t.List) -> exp.TimestampDiff:
    return exp.TimestampDiff(
        this=seq_get(args, 2),
        expression=seq_get(args, 1),
        unit=seq_get(args, 0),
    )


def _build_approx_percentile(args: t.List, dialect: t.Any = None) -> exp.ApproxQuantile:
    return exp.ApproxQuantile(
        this=seq_get(args, 0),
        quantile=seq_get(args, 1),
        error_tolerance=seq_get(args, 2),
    )


def _build_regexp_match(args: t.List) -> exp.RegexpExtractAll:
    return exp.RegexpExtractAll(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        parameters=seq_get(args, 2),
    )


def _build_regexp_substr(args: t.List) -> exp.RegexpExtract:
    return exp.RegexpExtract(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        position=seq_get(args, 2),
        occurrence=seq_get(args, 3),
        parameters=seq_get(args, 4),
    )


def _build_reduce(args: t.List) -> exp.Reduce:
    return exp.Reduce(
        initial=seq_get(args, 0),
        this=seq_get(args, 1),
        merge=seq_get(args, 2),
    )


def _json_agg_parser(self: Parser) -> exp.JSONArrayAgg:
    return exp.JSONArrayAgg(
        this=self._parse_term(),
        order=self._parse_order(),
    )


def _column_op_cast(self: Parser, this: exp.Expr, to: exp.Expr) -> exp.Cast:
    return self.expression(exp.Cast, this=this, to=to)


def _column_op_try_cast(self: Parser, this: exp.Expr, to: exp.Expr) -> exp.TryCast:
    return self.expression(exp.TryCast, this=this, to=to)


def _column_op_dcolon(self: Parser, this: exp.Expr, path: exp.Expr) -> exp.Expr:
    return build_json_extract_path(exp.JSONExtract)([this, exp.Literal.string(path.name)])


def _column_op_dcolondollar(self: Parser, this: exp.Expr, path: exp.Expr) -> exp.Expr:
    return build_json_extract_path(exp.JSONExtractScalar, json_type="STRING")(
        [this, exp.Literal.string(path.name)]
    )


def _column_op_dcolonpercent(self: Parser, this: exp.Expr, path: exp.Expr) -> exp.Expr:
    return build_json_extract_path(exp.JSONExtractScalar, json_type="DOUBLE")(
        [this, exp.Literal.string(path.name)]
    )


def _column_op_dcolonqmark(self: Parser, this: exp.Expr, path: exp.Expr) -> exp.JSONExists:
    return self.expression(
        exp.JSONExists,
        this=this,
        path=path.name,
        from_dcolonqmark=True,
    )


def _alter_change_parser(self: Parser) -> exp.RenameColumn:
    return self.expression(
        exp.RenameColumn, this=self._parse_column(), to=self._parse_column()
    )


class Parser(_MySQLParser):
    FUNCTIONS = {
        **_MYSQL_FUNCTIONS,
        "TO_DATE": build_formatted_time(exp.TsOrDsToDate, "singlestore"),
        "TO_TIMESTAMP": build_formatted_time(exp.StrToTime, "singlestore"),
        "TO_CHAR": build_formatted_time(exp.ToChar, "singlestore"),
        "STR_TO_DATE": build_formatted_time(exp.StrToDate, "mysql"),
        "DATE_FORMAT": build_formatted_time(exp.TimeToStr, "mysql"),
        # The first argument of following functions is converted to TIME(6)
        # This is needed because exp.TimeToStr is converted to DATE_FORMAT
        # which interprets the first argument as DATETIME and fails to parse
        # string literals like '12:05:47' without a date part.
        "TIME_FORMAT": _build_time_format,
        "HOUR": _build_hour,
        "MICROSECOND": _build_microsecond,
        "SECOND": _build_second,
        "MINUTE": _build_minute,
        "MONTHNAME": _build_monthname,
        "WEEKDAY": _build_weekday,
        "UNIX_TIMESTAMP": exp.StrToUnix.from_arg_list,
        "FROM_UNIXTIME": build_formatted_time(exp.UnixToTime, "mysql"),
        "TIME_BUCKET": _build_time_bucket,
        "BSON_EXTRACT_BSON": build_json_extract_path(exp.JSONBExtract),
        "BSON_EXTRACT_STRING": build_json_extract_path(
            exp.JSONBExtractScalar, json_type="STRING"
        ),
        "BSON_EXTRACT_DOUBLE": build_json_extract_path(
            exp.JSONBExtractScalar, json_type="DOUBLE"
        ),
        "BSON_EXTRACT_BIGINT": build_json_extract_path(
            exp.JSONBExtractScalar, json_type="BIGINT"
        ),
        "JSON_EXTRACT_JSON": build_json_extract_path(exp.JSONExtract),
        "JSON_EXTRACT_STRING": build_json_extract_path(
            exp.JSONExtractScalar, json_type="STRING"
        ),
        "JSON_EXTRACT_DOUBLE": build_json_extract_path(
            exp.JSONExtractScalar, json_type="DOUBLE"
        ),
        "JSON_EXTRACT_BIGINT": build_json_extract_path(
            exp.JSONExtractScalar, json_type="BIGINT"
        ),
        "JSON_ARRAY_CONTAINS_STRING": _build_json_array_contains_string,
        "JSON_ARRAY_CONTAINS_DOUBLE": _build_json_array_contains_double,
        "JSON_ARRAY_CONTAINS_JSON": _build_json_array_contains_json,
        "JSON_KEYS": _build_json_keys,
        "JSON_PRETTY": exp.JSONFormat.from_arg_list,
        "JSON_BUILD_ARRAY": _build_json_build_array,
        "JSON_BUILD_OBJECT": _build_json_build_object,
        "DATE": exp.Date.from_arg_list,
        "DAYNAME": _build_dayname,
        "TIMESTAMPDIFF": _build_timestampdiff,
        "APPROX_COUNT_DISTINCT": exp.Hll.from_arg_list,
        "APPROX_PERCENTILE": _build_approx_percentile,
        "VARIANCE": exp.VariancePop.from_arg_list,
        "INSTR": exp.Contains.from_arg_list,
        "REGEXP_MATCH": _build_regexp_match,
        "REGEXP_SUBSTR": _build_regexp_substr,
        "REDUCE": _build_reduce,
    }

    FUNCTION_PARSERS: t.Dict[str, t.Callable] = {
        **_MYSQL_FUNCTION_PARSERS,
        "JSON_AGG": _json_agg_parser,
    }

    NO_PAREN_FUNCTIONS = {
        **_NO_PAREN_FUNCTIONS,
        TokenType.UTC_DATE: exp.UtcDate,
        TokenType.UTC_TIME: exp.UtcTime,
        TokenType.UTC_TIMESTAMP: exp.UtcTimestamp,
    }

    CAST_COLUMN_OPERATORS = {TokenType.COLON_GT, TokenType.NCOLON_GT}

    COLUMN_OPERATORS = {
        k: v
        for k, v in {
            **_COLUMN_OPERATORS,
            TokenType.COLON_GT: _column_op_cast,
            TokenType.NCOLON_GT: _column_op_try_cast,
            TokenType.DCOLON: _column_op_dcolon,
            TokenType.DCOLONDOLLAR: _column_op_dcolondollar,
            TokenType.DCOLONPERCENT: _column_op_dcolonpercent,
            TokenType.DCOLONQMARK: _column_op_dcolonqmark,
        }.items()
        if k not in (TokenType.ARROW, TokenType.DARROW, TokenType.HASH_ARROW, TokenType.DHASH_ARROW, TokenType.PLACEHOLDER)
    }

    SHOW_PARSERS = {
        **_MYSQL_SHOW_PARSERS,
        "AGGREGATES": _show_parser("AGGREGATES"),
        "CDC EXTRACTOR POOL": _show_parser("CDC EXTRACTOR POOL"),
        "CREATE AGGREGATE": _show_parser("CREATE AGGREGATE", target=True),
        "CREATE PIPELINE": _show_parser("CREATE PIPELINE", target=True),
        "CREATE PROJECTION": _show_parser("CREATE PROJECTION", target=True),
        "DATABASE STATUS": _show_parser("DATABASE STATUS"),
        "DISTRIBUTED_PLANCACHE STATUS": _show_parser("DISTRIBUTED_PLANCACHE STATUS"),
        "FULLTEXT SERVICE METRICS LOCAL": _show_parser("FULLTEXT SERVICE METRICS LOCAL"),
        "FULLTEXT SERVICE METRICS FOR NODE": _show_parser(
            "FULLTEXT SERVICE METRICS FOR NODE", target=True
        ),
        "FULLTEXT SERVICE STATUS": _show_parser("FULLTEXT SERVICE STATUS"),
        "FUNCTIONS": _show_parser("FUNCTIONS"),
        "GROUPS": _show_parser("GROUPS"),
        "GROUPS FOR ROLE": _show_parser("GROUPS FOR ROLE", target=True),
        "GROUPS FOR USER": _show_parser("GROUPS FOR USER", target=True),
        "INDEXES": _show_parser("INDEX", target="FROM"),
        "KEYS": _show_parser("INDEX", target="FROM"),
        "LINKS": _show_parser("LINKS", target="ON"),
        "LOAD ERRORS": _show_parser("LOAD ERRORS"),
        "LOAD WARNINGS": _show_parser("LOAD WARNINGS"),
        "PARTITIONS": _show_parser("PARTITIONS", target="ON"),
        "PIPELINES": _show_parser("PIPELINES"),
        "PLAN": _show_parser("PLAN", target=True),
        "PLANCACHE": _show_parser("PLANCACHE"),
        "PROCEDURES": _show_parser("PROCEDURES"),
        "PROJECTIONS": _show_parser("PROJECTIONS", target="ON TABLE"),
        "REPLICATION STATUS": _show_parser("REPLICATION STATUS"),
        "REPRODUCTION": _show_parser("REPRODUCTION"),
        "RESOURCE POOLS": _show_parser("RESOURCE POOLS"),
        "ROLES": _show_parser("ROLES"),
        "ROLES FOR USER": _show_parser("ROLES FOR USER", target=True),
        "ROLES FOR GROUP": _show_parser("ROLES FOR GROUP", target=True),
        "STATUS EXTENDED": _show_parser("STATUS EXTENDED"),
        "USERS": _show_parser("USERS"),
        "USERS FOR ROLE": _show_parser("USERS FOR ROLE", target=True),
        "USERS FOR GROUP": _show_parser("USERS FOR GROUP", target=True),
    }

    ALTER_PARSERS = {
        **_MYSQL_ALTER_PARSERS,
        "CHANGE": _alter_change_parser,
    }

    def _parse_vector_expressions(self, expressions: t.List[exp.Expr]) -> t.List[exp.Expr]:
        type_name = expressions[1].name.upper()
        if type_name in self.dialect.VECTOR_TYPE_ALIASES:
            type_name = self.dialect.VECTOR_TYPE_ALIASES[type_name]

        return [exp.DataType.build(type_name, dialect=self.dialect), expressions[0]]

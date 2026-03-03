from __future__ import annotations

import re
import typing as t

from sqlglot import exp, parser
from sqlglot._typing import E
from sqlglot.dialects.dialect import (
    binary_from_function,
    build_date_delta_with_interval,
    build_formatted_time,
)
from sqlglot.helper import seq_get
from sqlglot.parser import Parser as _Parser, _FUNCTIONS, _FUNCTION_PARSERS, _NO_PAREN_FUNCTIONS, _NESTED_TYPE_TOKENS, _PROPERTY_PARSERS, _CONSTRAINT_PARSERS, _RANGE_PARSERS, _STATEMENT_PARSERS, _ID_VAR_TOKENS, _ALIAS_TOKENS, _TABLE_ALIAS_TOKENS, _COMMENT_TABLE_ALIAS_TOKENS, _UPDATE_ALIAS_TOKENS
from sqlglot.tokens import TokenType

if t.TYPE_CHECKING:
    from sqlglot.dialects.bigquery import BigQuery
    from sqlglot.dialects.dialect import Dialect

MAKE_INTERVAL_KWARGS = ["year", "month", "day", "hour", "minute", "second"]


def _build_parse_timestamp(args: t.List) -> exp.StrToTime:
    this = build_formatted_time(exp.StrToTime, "bigquery")([seq_get(args, 1), seq_get(args, 0)])
    this.set("zone", seq_get(args, 2))
    return this


def _build_timestamp(args: t.List) -> exp.Timestamp:
    timestamp = exp.Timestamp.from_arg_list(args)
    timestamp.set("with_tz", True)
    return timestamp


def _build_date(args: t.List) -> exp.Date | exp.DateFromParts:
    expr_type = exp.DateFromParts if len(args) == 3 else exp.Date
    return expr_type.from_arg_list(args)


def _build_to_hex(args: t.List) -> exp.Hex | exp.MD5:
    # TO_HEX(MD5(..)) is common in BigQuery, so it's parsed into MD5 to simplify its transpilation
    arg = seq_get(args, 0)
    return exp.MD5(this=arg.this) if isinstance(arg, exp.MD5Digest) else exp.LowerHex(this=arg)


def _build_json_strip_nulls(args: t.List) -> exp.JSONStripNulls:
    expression = exp.JSONStripNulls(this=seq_get(args, 0))

    for arg in args[1:]:
        if isinstance(arg, exp.Kwarg):
            expression.set(arg.this.name.lower(), arg)
        else:
            expression.set("expression", arg)

    return expression


def _build_time(args: t.List) -> exp.Func:
    if len(args) == 1:
        return exp.TsOrDsToTime(this=args[0])
    if len(args) == 2:
        return exp.Time.from_arg_list(args)
    return exp.TimeFromParts.from_arg_list(args)


def _build_datetime(args: t.List) -> exp.Func:
    if len(args) == 1:
        return exp.TsOrDsToDatetime.from_arg_list(args)
    if len(args) == 2:
        return exp.Datetime.from_arg_list(args)
    return exp.TimestampFromParts.from_arg_list(args)


def build_date_diff(args: t.List) -> exp.Expr:
    expr = exp.DateDiff(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        unit=seq_get(args, 2),
        date_part_boundary=True,
    )

    # Normalize plain WEEK to WEEK(SUNDAY) to preserve the semantic in the AST to facilitate transpilation
    # This is done post exp.DateDiff construction since the TimeUnit mixin performs canonicalizations in its constructor too
    unit = expr.args.get("unit")

    if isinstance(unit, exp.Var) and unit.name.upper() == "WEEK":
        expr.set("unit", exp.WeekStart(this=exp.var("SUNDAY")))

    return expr


def _build_regexp_extract(
    expr_type: t.Type[E], default_group: t.Optional[exp.Expr] = None
) -> t.Callable[[t.List, BigQuery], E]:
    def _builder(args: t.List, dialect: BigQuery) -> E:
        try:
            group = re.compile(args[1].name).groups == 1
        except re.error:
            group = False

        # Default group is used for the transpilation of REGEXP_EXTRACT_ALL
        return expr_type(
            this=seq_get(args, 0),
            expression=seq_get(args, 1),
            position=seq_get(args, 2),
            occurrence=seq_get(args, 3),
            group=exp.Literal.number(1) if group else default_group,
            **(
                {"null_if_pos_overflow": dialect.REGEXP_EXTRACT_POSITION_OVERFLOW_RETURNS_NULL}
                if expr_type is exp.RegexpExtract
                else {}
            ),
        )

    return _builder


def _build_extract_json_with_default_path(expr_type: t.Type[E]) -> t.Callable[[t.List, Dialect], E]:
    def _builder(args: t.List, dialect: Dialect) -> E:
        if len(args) == 1:
            # The default value for the JSONPath is '$' i.e all of the data
            args.append(exp.Literal.string("$"))
        return parser.build_extract_json_with_path(expr_type)(args, dialect)

    return _builder


def _build_levenshtein(args: t.List) -> exp.Levenshtein:
    max_dist = seq_get(args, 2)
    return exp.Levenshtein(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        max_dist=max_dist.expression if max_dist else None,
    )


def _build_format_time(expr_type: t.Type[exp.Expr]) -> t.Callable[[t.List], exp.TimeToStr]:
    def _builder(args: t.List) -> exp.TimeToStr:
        formatted_time = build_formatted_time(exp.TimeToStr, "bigquery")(
            [expr_type(this=seq_get(args, 1)), seq_get(args, 0)]
        )
        formatted_time.set("zone", seq_get(args, 2))
        return formatted_time

    return _builder


def _build_contains_substring(args: t.List) -> exp.Contains:
    # Lowercase the operands in case of transpilation, as exp.Contains
    # is case-sensitive on other dialects
    this = exp.Lower(this=seq_get(args, 0))
    expr = exp.Lower(this=seq_get(args, 1))

    return exp.Contains(this=this, expression=expr, json_scope=seq_get(args, 2))


def _build_date_trunc(args: t.List) -> exp.DateTrunc:
    return exp.DateTrunc(
        unit=seq_get(args, 1),
        this=seq_get(args, 0),
        zone=seq_get(args, 2),
    )


def _build_length(args: t.List) -> exp.Length:
    return exp.Length(this=seq_get(args, 0), binary=True)


def _build_normalize_and_casefold(args: t.List) -> exp.Normalize:
    return exp.Normalize(
        this=seq_get(args, 0), form=seq_get(args, 1), is_casefold=True
    )


def _build_parse_date(args: t.List) -> exp.StrToDate:
    return build_formatted_time(exp.StrToDate, "bigquery")(
        [seq_get(args, 1), seq_get(args, 0)]
    )


def _build_parse_time(args: t.List) -> exp.ParseTime:
    return build_formatted_time(exp.ParseTime, "bigquery")(
        [seq_get(args, 1), seq_get(args, 0)]
    )


def _build_parse_datetime(args: t.List) -> exp.ParseDatetime:
    return build_formatted_time(exp.ParseDatetime, "bigquery")(
        [seq_get(args, 1), seq_get(args, 0)]
    )


def _build_sha256(args: t.List) -> exp.SHA2Digest:
    return exp.SHA2Digest(
        this=seq_get(args, 0), length=exp.Literal.number(256)
    )


def _build_sha512(args: t.List) -> exp.SHA2:
    return exp.SHA2(this=seq_get(args, 0), length=exp.Literal.number(512))


def _build_split(args: t.List) -> exp.Split:
    return exp.Split(
        # https://cloud.google.com/bigquery/docs/reference/standard-sql/string_functions#split
        this=seq_get(args, 0),
        expression=seq_get(args, 1) or exp.Literal.string(","),
    )


def _build_timestamp_micros(args: t.List) -> exp.UnixToTime:
    return exp.UnixToTime(
        this=seq_get(args, 0), scale=exp.UnixToTime.MICROS
    )


def _build_timestamp_millis(args: t.List) -> exp.UnixToTime:
    return exp.UnixToTime(
        this=seq_get(args, 0), scale=exp.UnixToTime.MILLIS
    )


def _build_timestamp_seconds(args: t.List) -> exp.UnixToTime:
    return exp.UnixToTime(this=seq_get(args, 0))


def _build_to_json(args: t.List) -> exp.JSONFormat:
    return exp.JSONFormat(
        this=seq_get(args, 0), options=seq_get(args, 1), to_json=True
    )


def _build_week(args: t.List) -> exp.WeekStart:
    return exp.WeekStart(this=exp.var(seq_get(args, 0)))


def _parse_array(self: Parser) -> exp.Array:
    return self.expression(
        exp.Array,
        expressions=[self._parse_statement()],
        struct_name_inheritance=True,
    )


def _parse_json_array(self: Parser) -> exp.JSONArray:
    return self.expression(
        exp.JSONArray, expressions=self._parse_csv(self._parse_bitwise)
    )


def _parse_make_interval(self: Parser) -> exp.MakeInterval:
    return self._parse_make_interval()


def _parse_predict(self: Parser) -> exp.Predict:
    return self._parse_ml(exp.Predict)


def _parse_translate(self: Parser) -> t.Union[exp.Translate, exp.MLTranslate]:
    return self._parse_translate()


def _parse_features_at_time(self: Parser) -> exp.FeaturesAtTime:
    return self._parse_features_at_time()


def _parse_generate_embedding(self: Parser) -> exp.GenerateEmbedding:
    return self._parse_ml(exp.GenerateEmbedding)


def _parse_generate_text_embedding(self: Parser) -> exp.GenerateEmbedding:
    return self._parse_ml(exp.GenerateEmbedding, is_text=True)


def _parse_vector_search(self: Parser) -> exp.VectorSearch:
    return self._parse_vector_search()


def _parse_forecast(self: Parser) -> exp.MLForecast:
    return self._parse_ml(exp.MLForecast)


def _parse_not_deterministic(self: Parser) -> exp.StabilityProperty:
    return self.expression(
        exp.StabilityProperty, this=exp.Literal.string("VOLATILE")
    )


def _parse_options_property(self: Parser):  # type: ignore
    return self._parse_with_property()  # type: ignore


def _parse_options_constraint(self: Parser) -> exp.Properties:
    return exp.Properties(expressions=self._parse_with_property())


def _parse_else_statement(self: Parser) -> exp.Command:
    return self._parse_as_command(self._prev)


def _parse_end_statement(self: Parser) -> exp.Command:
    return self._parse_as_command(self._prev)


def _parse_for_statement(self: Parser) -> t.Union[exp.ForIn, exp.Command]:
    return self._parse_for_in()


def _parse_export_statement(self: Parser) -> exp.Export:
    return self._parse_export_data()


def _parse_declare_statement(self: Parser) -> t.Union[exp.Declare, exp.Command]:
    return self._parse_declare()


class Parser(_Parser):
    PREFIXED_PIVOT_COLUMNS = True
    LOG_DEFAULTS_TO_LN = True
    SUPPORTS_IMPLICIT_UNNEST = True
    JOINS_HAVE_EQUAL_PRECEDENCE = True

    # BigQuery does not allow ASC/DESC to be used as an identifier, allows GRANT as an identifier
    ID_VAR_TOKENS = {
        *_ID_VAR_TOKENS,
        TokenType.GRANT,
    } - {TokenType.ASC, TokenType.DESC}

    ALIAS_TOKENS = {
        *_ALIAS_TOKENS,
        TokenType.GRANT,
    } - {TokenType.ASC, TokenType.DESC}

    TABLE_ALIAS_TOKENS = {
        *_TABLE_ALIAS_TOKENS,
        TokenType.GRANT,
    } - {TokenType.ASC, TokenType.DESC}

    COMMENT_TABLE_ALIAS_TOKENS = {
        *_COMMENT_TABLE_ALIAS_TOKENS,
        TokenType.GRANT,
    } - {TokenType.ASC, TokenType.DESC}

    UPDATE_ALIAS_TOKENS = {
        *_UPDATE_ALIAS_TOKENS,
        TokenType.GRANT,
    } - {TokenType.ASC, TokenType.DESC}

    FUNCTIONS = {
        **_FUNCTIONS,
        "APPROX_TOP_COUNT": exp.ApproxTopK.from_arg_list,
        "BIT_AND": exp.BitwiseAndAgg.from_arg_list,
        "BIT_OR": exp.BitwiseOrAgg.from_arg_list,
        "BIT_XOR": exp.BitwiseXorAgg.from_arg_list,
        "BIT_COUNT": exp.BitwiseCount.from_arg_list,
        "BOOL": exp.JSONBool.from_arg_list,
        "CONTAINS_SUBSTR": _build_contains_substring,
        "DATE": _build_date,
        "DATE_ADD": build_date_delta_with_interval(exp.DateAdd),
        "DATE_DIFF": build_date_diff,
        "DATE_SUB": build_date_delta_with_interval(exp.DateSub),
        "DATE_TRUNC": _build_date_trunc,
        "DATETIME": _build_datetime,
        "DATETIME_ADD": build_date_delta_with_interval(exp.DatetimeAdd),
        "DATETIME_SUB": build_date_delta_with_interval(exp.DatetimeSub),
        "DIV": binary_from_function(exp.IntDiv),
        "EDIT_DISTANCE": _build_levenshtein,
        "FORMAT_DATE": _build_format_time(exp.TsOrDsToDate),
        "GENERATE_ARRAY": exp.GenerateSeries.from_arg_list,
        "JSON_EXTRACT_SCALAR": _build_extract_json_with_default_path(exp.JSONExtractScalar),
        "JSON_EXTRACT_ARRAY": _build_extract_json_with_default_path(exp.JSONExtractArray),
        "JSON_EXTRACT_STRING_ARRAY": _build_extract_json_with_default_path(exp.JSONValueArray),
        "JSON_KEYS": exp.JSONKeysAtDepth.from_arg_list,
        "JSON_QUERY": parser.build_extract_json_with_path(exp.JSONExtract),
        "JSON_QUERY_ARRAY": _build_extract_json_with_default_path(exp.JSONExtractArray),
        "JSON_STRIP_NULLS": _build_json_strip_nulls,
        "JSON_VALUE": _build_extract_json_with_default_path(exp.JSONExtractScalar),
        "JSON_VALUE_ARRAY": _build_extract_json_with_default_path(exp.JSONValueArray),
        "LENGTH": _build_length,
        "MD5": exp.MD5Digest.from_arg_list,
        "SHA1": exp.SHA1Digest.from_arg_list,
        "NORMALIZE_AND_CASEFOLD": _build_normalize_and_casefold,
        "OCTET_LENGTH": exp.ByteLength.from_arg_list,
        "TO_HEX": _build_to_hex,
        "PARSE_DATE": _build_parse_date,
        "PARSE_TIME": _build_parse_time,
        "PARSE_TIMESTAMP": _build_parse_timestamp,
        "PARSE_DATETIME": _build_parse_datetime,
        "REGEXP_CONTAINS": exp.RegexpLike.from_arg_list,
        "REGEXP_EXTRACT": _build_regexp_extract(exp.RegexpExtract),
        "REGEXP_SUBSTR": _build_regexp_extract(exp.RegexpExtract),
        "REGEXP_EXTRACT_ALL": _build_regexp_extract(
            exp.RegexpExtractAll, default_group=exp.Literal.number(0)
        ),
        "SHA256": _build_sha256,
        "SHA512": _build_sha512,
        "SPLIT": _build_split,
        "STRPOS": exp.StrPosition.from_arg_list,
        "TIME": _build_time,
        "TIME_ADD": build_date_delta_with_interval(exp.TimeAdd),
        "TIME_SUB": build_date_delta_with_interval(exp.TimeSub),
        "TIMESTAMP": _build_timestamp,
        "TIMESTAMP_ADD": build_date_delta_with_interval(exp.TimestampAdd),
        "TIMESTAMP_SUB": build_date_delta_with_interval(exp.TimestampSub),
        "TIMESTAMP_MICROS": _build_timestamp_micros,
        "TIMESTAMP_MILLIS": _build_timestamp_millis,
        "TIMESTAMP_SECONDS": _build_timestamp_seconds,
        "TO_JSON": _build_to_json,
        "TO_JSON_STRING": exp.JSONFormat.from_arg_list,
        "FORMAT_DATETIME": _build_format_time(exp.TsOrDsToDatetime),
        "FORMAT_TIMESTAMP": _build_format_time(exp.TsOrDsToTimestamp),
        "FORMAT_TIME": _build_format_time(exp.TsOrDsToTime),
        "FROM_HEX": exp.Unhex.from_arg_list,
        "WEEK": _build_week,
    }
    # Remove SEARCH to avoid parameter routing issues - let it fall back to Anonymous function
    FUNCTIONS = {k: v for k, v in FUNCTIONS.items() if k != "SEARCH"}

    FUNCTION_PARSERS = {
        **_FUNCTION_PARSERS,
        "ARRAY": _parse_array,
        "JSON_ARRAY": _parse_json_array,
        "MAKE_INTERVAL": _parse_make_interval,
        "PREDICT": _parse_predict,
        "TRANSLATE": _parse_translate,
        "FEATURES_AT_TIME": _parse_features_at_time,
        "GENERATE_EMBEDDING": _parse_generate_embedding,
        "GENERATE_TEXT_EMBEDDING": _parse_generate_text_embedding,
        "VECTOR_SEARCH": _parse_vector_search,
        "FORECAST": _parse_forecast,
    }
    FUNCTION_PARSERS = {k: v for k, v in FUNCTION_PARSERS.items() if k != "TRIM"}

    NO_PAREN_FUNCTIONS = {
        **_NO_PAREN_FUNCTIONS,
        TokenType.CURRENT_DATETIME: exp.CurrentDatetime,
    }

    NESTED_TYPE_TOKENS = {
        *_NESTED_TYPE_TOKENS,
        TokenType.TABLE,
    }

    PROPERTY_PARSERS = {
        **_PROPERTY_PARSERS,
        "NOT DETERMINISTIC": _parse_not_deterministic,
        "OPTIONS": _parse_options_property,
    }

    CONSTRAINT_PARSERS = {
        **_CONSTRAINT_PARSERS,
        "OPTIONS": _parse_options_constraint,
    }

    RANGE_PARSERS = {k: v for k, v in _RANGE_PARSERS.items() if k != TokenType.OVERLAPS}

    DASHED_TABLE_PART_FOLLOW_TOKENS = {TokenType.DOT, TokenType.L_PAREN, TokenType.R_PAREN}

    STATEMENT_PARSERS = {
        **_STATEMENT_PARSERS,
        TokenType.ELSE: _parse_else_statement,
        TokenType.END: _parse_end_statement,
        TokenType.FOR: _parse_for_statement,
        TokenType.EXPORT: _parse_export_statement,
        TokenType.DECLARE: _parse_declare_statement,
    }

    BRACKET_OFFSETS = {
        "OFFSET": (0, False),
        "ORDINAL": (1, False),
        "SAFE_OFFSET": (0, True),
        "SAFE_ORDINAL": (1, True),
    }

    def _parse_for_in(self) -> t.Union[exp.ForIn, exp.Command]:
        index = self._index
        this = self._parse_range()
        self._match_text_seq("DO")
        if self._match(TokenType.COMMAND):
            self._retreat(index)
            return self._parse_as_command(self._prev)
        return self.expression(exp.ForIn, this=this, expression=self._parse_statement())

    def _parse_table_part(self, schema: bool = False) -> t.Optional[exp.Expr]:
        this = super()._parse_table_part(schema=schema) or self._parse_number()

        # https://cloud.google.com/bigquery/docs/reference/standard-sql/lexical#table_names
        if isinstance(this, exp.Identifier):
            table_name = this.name
            while self._match(TokenType.DASH, advance=False) and self._next:
                start = self._curr
                while self._is_connected() and not self._match_set(
                    self.DASHED_TABLE_PART_FOLLOW_TOKENS, advance=False
                ):
                    self._advance()

                if start == self._curr:
                    break

                table_name += self._find_sql(start, self._prev)

            this = exp.Identifier(
                this=table_name, quoted=this.args.get("quoted")
            ).update_positions(this)
        elif isinstance(this, exp.Literal):
            table_name = this.name

            if self._is_connected() and self._parse_var(any_token=True):
                table_name += self._prev.text

            this = exp.Identifier(this=table_name, quoted=True).update_positions(this)

        return this

    def _parse_table_parts(
        self, schema: bool = False, is_db_reference: bool = False, wildcard: bool = False
    ) -> exp.Table:
        from sqlglot.helper import split_num_words

        table = super()._parse_table_parts(
            schema=schema, is_db_reference=is_db_reference, wildcard=True
        )

        # proj-1.db.tbl -- `1.` is tokenized as a float so we need to unravel it here
        if not table.catalog:
            if table.db:
                previous_db = table.args["db"]
                parts = table.db.split(".")
                if len(parts) == 2 and not table.args["db"].quoted:
                    table.set(
                        "catalog", exp.Identifier(this=parts[0]).update_positions(previous_db)
                    )
                    table.set("db", exp.Identifier(this=parts[1]).update_positions(previous_db))
            else:
                previous_this = table.this
                parts = table.name.split(".")
                if len(parts) == 2 and not table.this.quoted:
                    table.set(
                        "db", exp.Identifier(this=parts[0]).update_positions(previous_this)
                    )
                    table.set(
                        "this", exp.Identifier(this=parts[1]).update_positions(previous_this)
                    )

        if isinstance(table.this, exp.Identifier) and any("." in p.name for p in table.parts):
            alias = table.this
            catalog, db, this, *rest = (
                exp.to_identifier(p, quoted=True)
                for p in split_num_words(".".join(p.name for p in table.parts), ".", 3)
            )

            for part in (catalog, db, this):
                if part:
                    part.update_positions(table.this)

            if rest and this:
                this = exp.Dot.build([this, *rest])  # type: ignore

            table = exp.Table(
                this=this, db=db, catalog=catalog, pivots=table.args.get("pivots")
            )
            table.meta["quoted_table"] = True
        else:
            alias = None

        # The `INFORMATION_SCHEMA` views in BigQuery need to be qualified by a region or
        # dataset, so if the project identifier is omitted we need to fix the ast so that
        # the `INFORMATION_SCHEMA.X` bit is represented as a single (quoted) Identifier.
        # Otherwise, we wouldn't correctly qualify a `Table` node that references these
        # views, because it would seem like the "catalog" part is set, when it'd actually
        # be the region/dataset. Merging the two identifiers into a single one is done to
        # avoid producing a 4-part Table reference, which would cause issues in the schema
        # module, when there are 3-part table names mixed with information schema views.
        #
        # See: https://cloud.google.com/bigquery/docs/information-schema-intro#syntax
        table_parts = table.parts
        if len(table_parts) > 1 and table_parts[-2].name.upper() == "INFORMATION_SCHEMA":
            # We need to alias the table here to avoid breaking existing qualified columns.
            # This is expected to be safe, because if there's an actual alias coming up in
            # the token stream, it will overwrite this one. If there isn't one, we are only
            # exposing the name that can be used to reference the view explicitly (a no-op).
            exp.alias_(
                table,
                t.cast(exp.Identifier, alias or table_parts[-1]),
                table=True,
                copy=False,
            )

            info_schema_view = f"{table_parts[-2].name}.{table_parts[-1].name}"
            new_this = exp.Identifier(this=info_schema_view, quoted=True).update_positions(
                line=table_parts[-2].meta.get("line"),
                col=table_parts[-1].meta.get("col"),
                start=table_parts[-2].meta.get("start"),
                end=table_parts[-1].meta.get("end"),
            )
            table.set("this", new_this)
            table.set("db", seq_get(table_parts, -3))
            table.set("catalog", seq_get(table_parts, -4))

        return table

    def _parse_column(self) -> t.Optional[exp.Expr]:
        from sqlglot.helper import split_num_words

        column = super()._parse_column()
        if isinstance(column, exp.Column):
            parts = column.parts
            if any("." in p.name for p in parts):
                catalog, db, table, this, *rest = (
                    exp.to_identifier(p, quoted=True)
                    for p in split_num_words(".".join(p.name for p in parts), ".", 4)
                )

                if rest and this:
                    this = exp.Dot.build([this, *rest])  # type: ignore

                column = exp.Column(this=this, table=table, db=db, catalog=catalog)
                column.meta["quoted_column"] = True

        return column

    @t.overload
    def _parse_json_object(self, agg: t.Literal[False]) -> exp.JSONObject: ...

    @t.overload
    def _parse_json_object(self, agg: t.Literal[True]) -> exp.JSONObjectAgg: ...

    def _parse_json_object(self, agg=False):
        json_object = super()._parse_json_object()
        array_kv_pair = seq_get(json_object.expressions, 0)

        # Converts BQ's "signature 2" of JSON_OBJECT into SQLGlot's canonical representation
        # https://cloud.google.com/bigquery/docs/reference/standard-sql/json_functions#json_object_signature2
        if (
            array_kv_pair
            and isinstance(array_kv_pair.this, exp.Array)
            and isinstance(array_kv_pair.expression, exp.Array)
        ):
            keys = array_kv_pair.this.expressions
            values = array_kv_pair.expression.expressions

            json_object.set(
                "expressions",
                [exp.JSONKeyValue(this=k, expression=v) for k, v in zip(keys, values)],
            )

        return json_object

    def _parse_bracket(self, this: t.Optional[exp.Expr] = None) -> t.Optional[exp.Expr]:
        bracket = super()._parse_bracket(this)

        if isinstance(bracket, exp.Array):
            bracket.set("struct_name_inheritance", True)

        if this is bracket:
            return bracket

        if isinstance(bracket, exp.Bracket):
            for expression in bracket.expressions:
                name = expression.name.upper()

                if name not in self.BRACKET_OFFSETS:
                    break

                offset, safe = self.BRACKET_OFFSETS[name]
                bracket.set("offset", offset)
                bracket.set("safe", safe)
                expression.replace(expression.expressions[0])

        return bracket

    def _parse_unnest(self, with_alias: bool = True) -> t.Optional[exp.Unnest]:
        unnest = super()._parse_unnest(with_alias=with_alias)

        if not unnest:
            return None

        unnest_expr = seq_get(unnest.expressions, 0)
        if unnest_expr:
            from sqlglot.optimizer.annotate_types import annotate_types

            unnest_expr = annotate_types(unnest_expr, dialect=self.dialect)

            # Unnesting a nested array (i.e array of structs) explodes the top-level struct fields,
            # in contrast to other dialects such as DuckDB which flattens only the array by default
            if unnest_expr.is_type(exp.DType.ARRAY) and any(
                array_elem.is_type(exp.DType.STRUCT)
                for array_elem in unnest_expr._type.expressions
            ):
                unnest.set("explode_array", True)

        return unnest

    def _parse_make_interval(self) -> exp.MakeInterval:
        expr = exp.MakeInterval()

        for arg_key in MAKE_INTERVAL_KWARGS:
            value = self._parse_lambda()

            if not value:
                break

            # Non-named arguments are filled sequentially, (optionally) followed by named arguments
            # that can appear in any order e.g MAKE_INTERVAL(1, minute => 5, day => 2)
            if isinstance(value, exp.Kwarg):
                arg_key = value.this.name

            expr.set(arg_key, value)

            self._match(TokenType.COMMA)

        return expr

    def _parse_ml(self, expr_type: t.Type[E], **kwargs) -> E:
        self._match_text_seq("MODEL")
        this = self._parse_table()

        self._match(TokenType.COMMA)
        self._match_text_seq("TABLE")

        # Certain functions like ML.FORECAST require a STRUCT argument but not a TABLE/SELECT one
        expression = (
            self._parse_table() if not self._match(TokenType.STRUCT, advance=False) else None
        )

        self._match(TokenType.COMMA)

        return self.expression(
            expr_type,
            this=this,
            expression=expression,
            params_struct=self._parse_bitwise(),
            **kwargs,
        )

    def _parse_translate(self) -> exp.Translate | exp.MLTranslate:
        # Check if this is ML.TRANSLATE by looking at previous tokens
        token = seq_get(self._tokens, self._index - 4)
        if token and token.text.upper() == "ML":
            return self._parse_ml(exp.MLTranslate)

        return exp.Translate.from_arg_list(self._parse_function_args())

    def _parse_features_at_time(self) -> exp.FeaturesAtTime:
        self._match(TokenType.TABLE)
        this = self._parse_table()

        expr = self.expression(exp.FeaturesAtTime, this=this)

        while self._match(TokenType.COMMA):
            arg = self._parse_lambda()

            # Get the LHS of the Kwarg and set the arg to that value, e.g
            # "num_rows => 1" sets the expr's `num_rows` arg
            if arg:
                expr.set(arg.this.name, arg)

        return expr

    def _parse_vector_search(self) -> exp.VectorSearch:
        self._match(TokenType.TABLE)
        base_table = self._parse_table()

        self._match(TokenType.COMMA)

        column_to_search = self._parse_bitwise()
        self._match(TokenType.COMMA)

        self._match(TokenType.TABLE)
        query_table = self._parse_table()

        expr = self.expression(
            exp.VectorSearch,
            this=base_table,
            column_to_search=column_to_search,
            query_table=query_table,
        )

        while self._match(TokenType.COMMA):
            # query_column_to_search can be named argument or positional
            if self._match(TokenType.STRING, advance=False):
                query_column = self._parse_string()
                expr.set("query_column_to_search", query_column)
            else:
                arg = self._parse_lambda()
                if arg:
                    expr.set(arg.this.name, arg)

        return expr

    def _parse_export_data(self) -> exp.Export:
        self._match_text_seq("DATA")

        return self.expression(
            exp.Export,
            connection=self._match_text_seq("WITH", "CONNECTION") and self._parse_table_parts(),
            options=self._parse_properties(),
            this=self._match_text_seq("AS") and self._parse_select(),
        )

    def _parse_column_ops(self, this: t.Optional[exp.Expr]) -> t.Optional[exp.Expr]:
        func_index = self._index + 1
        this = super()._parse_column_ops(this)

        if isinstance(this, exp.Dot) and isinstance(this.expression, exp.Func):
            prefix = this.this.name.upper()

            func: t.Optional[t.Type[exp.Func]] = None
            if prefix == "NET":
                func = exp.NetFunc
            elif prefix == "SAFE":
                func = exp.SafeFunc

            if func:
                # Retreat to try and parse a known function instead of an anonymous one,
                # which is parsed by the base column ops parser due to anonymous_func=true
                self._retreat(func_index)
                this = func(this=self._parse_function(any_token=True))

        return this

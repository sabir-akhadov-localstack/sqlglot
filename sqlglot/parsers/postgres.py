from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects.dialect import (
    binary_from_function,
    build_formatted_time,
    build_json_extract_path,
    build_timestamp_trunc,
)
from sqlglot.helper import seq_get
from sqlglot.parser import Parser as _Parser, binary_range_parser, _FUNCTIONS, _PROPERTY_PARSERS, _PLACEHOLDER_PARSERS, _NO_PAREN_FUNCTION_PARSERS, _NO_PAREN_FUNCTIONS, _FUNCTION_PARSERS, _BITWISE, _RANGE_PARSERS, _STATEMENT_PARSERS, _UNARY_PARSERS, _COLUMN_OPERATORS
from sqlglot.tokens import TokenType


def _build_generate_series(args: t.List) -> exp.ExplodingGenerateSeries:
    # The goal is to convert step values like '1 day' or INTERVAL '1 day' into INTERVAL '1' day
    # Note: postgres allows calls with just two arguments -- the "step" argument defaults to 1
    step = seq_get(args, 2)
    if step is not None:
        if step.is_string:
            args[2] = exp.to_interval(step.this)
        elif isinstance(step, exp.Interval) and not step.args.get("unit"):
            args[2] = exp.to_interval(step.this.this)

    return exp.ExplodingGenerateSeries.from_arg_list(args)


def _build_to_timestamp(args: t.List) -> exp.UnixToTime | exp.StrToTime:
    # TO_TIMESTAMP accepts either a single double argument or (text, text)
    if len(args) == 1:
        # https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-TABLE
        return exp.UnixToTime.from_arg_list(args)

    # https://www.postgresql.org/docs/current/functions-formatting.html
    return build_formatted_time(exp.StrToTime, "postgres")(args)


def _build_regexp_replace(args: t.List, dialect: t.Any = None) -> exp.RegexpReplace:
    from sqlglot.helper import is_int

    # The signature of REGEXP_REPLACE is:
    # regexp_replace(source, pattern, replacement [, start [, N ]] [, flags ])
    #
    # Any one of `start`, `N` and `flags` can be column references, meaning that
    # unless we can statically see that the last argument is a non-integer string
    # (eg. not '0'), then it's not possible to construct the correct AST
    regexp_replace = None
    if len(args) > 3:
        last = args[-1]
        if not is_int(last.name):
            if not last.type or last.is_type(exp.DType.UNKNOWN, exp.DType.NULL):
                from sqlglot.optimizer.annotate_types import annotate_types

                last = annotate_types(last, dialect=dialect)

            if last.is_type(*exp.DataType.TEXT_TYPES):
                regexp_replace = exp.RegexpReplace.from_arg_list(args[:-1])
                regexp_replace.set("modifiers", last)

    regexp_replace = regexp_replace or exp.RegexpReplace.from_arg_list(args)
    regexp_replace.set("single_replace", True)
    return regexp_replace


def _build_levenshtein_less_equal(args: t.List) -> exp.Levenshtein:
    # Postgres has two signatures for levenshtein_less_equal function, but in both cases
    # max_dist is the last argument
    # levenshtein_less_equal(source, target, ins_cost, del_cost, sub_cost, max_d)
    # levenshtein_less_equal(source, target, max_d)
    max_dist = args.pop()

    return exp.Levenshtein(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        ins_cost=seq_get(args, 2),
        del_cost=seq_get(args, 3),
        sub_cost=seq_get(args, 4),
        max_dist=max_dist,
    )


def _build_array_prepend(args: t.List) -> exp.ArrayPrepend:
    return exp.ArrayPrepend(this=seq_get(args, 1), expression=seq_get(args, 0))


def _build_div(args: t.List) -> exp.Cast:
    return exp.cast(binary_from_function(exp.IntDiv)(args), exp.DType.DECIMAL)


def _build_get_bit(args: t.List) -> exp.Getbit:
    return exp.Getbit(this=seq_get(args, 0), expression=seq_get(args, 1), zero_is_msb=True)


def _build_length(args: t.List) -> exp.Length:
    return exp.Length(this=seq_get(args, 0), encoding=seq_get(args, 1))


def _build_sha256(args: t.List) -> exp.SHA2:
    return exp.SHA2(this=seq_get(args, 0), length=exp.Literal.number(256))


def _build_sha384(args: t.List) -> exp.SHA2:
    return exp.SHA2(this=seq_get(args, 0), length=exp.Literal.number(384))


def _build_sha512(args: t.List) -> exp.SHA2:
    return exp.SHA2(this=seq_get(args, 0), length=exp.Literal.number(512))


def _build_json_object_agg(args: t.List) -> exp.JSONObjectAgg:
    return exp.JSONObjectAgg(expressions=args)


def _build_width_bucket(args: t.List) -> exp.WidthBucket:
    if len(args) == 2:
        return exp.WidthBucket(this=seq_get(args, 0), threshold=seq_get(args, 1))
    return exp.WidthBucket.from_arg_list(args)


def _property_set_parser(self: Parser) -> exp.SetConfigProperty:
    return self.expression(exp.SetConfigProperty, this=self._parse_set())


def _placeholder_jdbc_parser(self: Parser) -> exp.Placeholder:
    return self.expression(exp.Placeholder, jdbc=True)


def _placeholder_mod_parser(self: Parser) -> t.Optional[exp.Expr]:
    return self._parse_query_parameter()


def _no_paren_variadic(self: Parser) -> exp.Variadic:
    return self.expression(exp.Variadic, this=self._parse_bitwise())


def _date_part_parser(self: Parser) -> exp.Expr:
    return self._parse_date_part()


def _json_agg_parser(self: Parser) -> exp.JSONArrayAgg:
    return self.expression(
        exp.JSONArrayAgg,
        this=self._parse_lambda(),
        order=self._parse_order(),
    )


def _jsonb_exists_parser(self: Parser) -> exp.JSONBExists:
    return self._parse_jsonb_exists()


def _range_dat_parser(self: Parser, this: exp.Expr) -> exp.MatchAgainst:
    return self.expression(
        exp.MatchAgainst, this=self._parse_bitwise(), expressions=[this]
    )


def _end_statement_parser(self: Parser) -> t.Optional[exp.Expr]:
    return self._parse_commit_or_rollback()


def _unary_rlike_parser(self: Parser) -> exp.BitwiseNot:
    return self.expression(exp.BitwiseNot, this=self._parse_unary())


def _column_op_arrow(self: Parser, this: exp.Expr, path: exp.Expr) -> exp.Expr:
    return self.validate_expression(
        build_json_extract_path(
            exp.JSONExtract, arrow_req_json_type=self.JSON_ARROWS_REQUIRE_JSON_TYPE
        )([this, path])
    )


def _column_op_darrow(self: Parser, this: exp.Expr, path: exp.Expr) -> exp.Expr:
    return self.validate_expression(
        build_json_extract_path(
            exp.JSONExtractScalar, arrow_req_json_type=self.JSON_ARROWS_REQUIRE_JSON_TYPE
        )([this, path])
    )


class Parser(_Parser):
    SUPPORTS_OMITTED_INTERVAL_SPAN_UNIT = True

    PROPERTY_PARSERS = {
        **{k: v for k, v in _PROPERTY_PARSERS.items() if k != "INPUT"},
        "SET": _property_set_parser,
    }

    PLACEHOLDER_PARSERS = {
        **_PLACEHOLDER_PARSERS,
        TokenType.PLACEHOLDER: _placeholder_jdbc_parser,
        TokenType.MOD: _placeholder_mod_parser,
    }

    FUNCTIONS = {
        **_FUNCTIONS,
        "ARRAY_PREPEND": _build_array_prepend,
        "BIT_AND": exp.BitwiseAndAgg.from_arg_list,
        "BIT_OR": exp.BitwiseOrAgg.from_arg_list,
        "BIT_XOR": exp.BitwiseXorAgg.from_arg_list,
        "VERSION": exp.CurrentVersion.from_arg_list,
        "DATE_TRUNC": build_timestamp_trunc,
        "DIV": _build_div,
        "GENERATE_SERIES": _build_generate_series,
        "GET_BIT": _build_get_bit,
        "JSON_EXTRACT_PATH": build_json_extract_path(exp.JSONExtract),
        "JSON_EXTRACT_PATH_TEXT": build_json_extract_path(exp.JSONExtractScalar),
        "LENGTH": _build_length,
        "MAKE_TIME": exp.TimeFromParts.from_arg_list,
        "MAKE_TIMESTAMP": exp.TimestampFromParts.from_arg_list,
        "NOW": exp.CurrentTimestamp.from_arg_list,
        "REGEXP_REPLACE": _build_regexp_replace,
        "TO_CHAR": build_formatted_time(exp.TimeToStr, "postgres"),
        "TO_DATE": build_formatted_time(exp.StrToDate, "postgres"),
        "TO_TIMESTAMP": _build_to_timestamp,
        "UNNEST": exp.Explode.from_arg_list,
        "SHA256": _build_sha256,
        "SHA384": _build_sha384,
        "SHA512": _build_sha512,
        "LEVENSHTEIN_LESS_EQUAL": _build_levenshtein_less_equal,
        "JSON_OBJECT_AGG": _build_json_object_agg,
        "JSONB_OBJECT_AGG": exp.JSONBObjectAgg.from_arg_list,
        "WIDTH_BUCKET": _build_width_bucket,
    }

    NO_PAREN_FUNCTION_PARSERS = {
        **_NO_PAREN_FUNCTION_PARSERS,
        "VARIADIC": _no_paren_variadic,
    }

    NO_PAREN_FUNCTIONS = {
        **_NO_PAREN_FUNCTIONS,
        TokenType.CURRENT_SCHEMA: exp.CurrentSchema,
    }

    FUNCTION_PARSERS = {
        **_FUNCTION_PARSERS,
        "DATE_PART": _date_part_parser,
        "JSON_AGG": _json_agg_parser,
        "JSONB_EXISTS": _jsonb_exists_parser,
    }

    BITWISE = {
        **_BITWISE,
        TokenType.HASH: exp.BitwiseXor,
    }

    EXPONENT = {
        TokenType.CARET: exp.Pow,
    }

    RANGE_PARSERS = {
        **_RANGE_PARSERS,
        TokenType.DAMP: binary_range_parser(exp.ArrayOverlaps),
        TokenType.DAT: _range_dat_parser,
    }

    STATEMENT_PARSERS = {
        **_STATEMENT_PARSERS,
        TokenType.END: _end_statement_parser,
    }

    UNARY_PARSERS = {
        **_UNARY_PARSERS,
        # The `~` token is remapped from TILDE to RLIKE in Postgres due to the binary REGEXP LIKE operator
        TokenType.RLIKE: _unary_rlike_parser,
    }

    JSON_ARROWS_REQUIRE_JSON_TYPE = True

    COLUMN_OPERATORS = {
        **_COLUMN_OPERATORS,
        TokenType.ARROW: _column_op_arrow,
        TokenType.DARROW: _column_op_darrow,
    }

    ARG_MODE_TOKENS = {TokenType.IN, TokenType.OUT, TokenType.INOUT, TokenType.VARIADIC}

    def _parse_parameter_mode(self) -> t.Optional[TokenType]:
        """
        Parse PostgreSQL function parameter mode (IN, OUT, INOUT, VARIADIC).

        Disambiguates between mode keywords and identifiers with the same name:
        - MODE TYPE      → keyword is identifier (e.g., "out INT")
        - MODE NAME TYPE → keyword is mode (e.g., "OUT x INT")

        Returns:
            Mode token type if current token is a mode keyword, None otherwise.
        """
        if not self._match_set(self.ARG_MODE_TOKENS, advance=False) or not self._next:
            return None

        mode_token = self._curr

        # Check Pattern 1: MODE TYPE
        # Try parsing next token as a built-in type (not UDT)
        # If successful, the keyword is an identifier, not a mode
        is_followed_by_builtin_type = self._try_parse(
            lambda: self._advance()  # type: ignore
            or self._parse_types(check_func=False, allow_identifiers=False),
            retreat=True,
        )
        if is_followed_by_builtin_type:
            return None  # Pattern: "out INT" → out is parameter name

        # Check Pattern 2: MODE NAME TYPE
        # If next token is an identifier, check if there's a type after it
        # The type can be built-in or user-defined (allow_identifiers=True)
        if self._next.token_type not in self.ID_VAR_TOKENS:
            return None

        is_followed_by_any_type = self._try_parse(
            lambda: self._advance(2)  # type: ignore
            or self._parse_types(check_func=False, allow_identifiers=True),
            retreat=True,
        )

        if is_followed_by_any_type:
            return mode_token.token_type  # Pattern: "OUT x INT" → OUT is mode

        return None

    def _create_mode_constraint(self, param_mode: TokenType) -> exp.InOutColumnConstraint:
        """
        Create parameter mode constraint for function parameters.

        Args:
            param_mode: The parameter mode token (IN, OUT, INOUT, or VARIADIC).

        Returns:
            InOutColumnConstraint expression representing the parameter mode.
        """
        return self.expression(
            exp.InOutColumnConstraint,
            input_=(param_mode in {TokenType.IN, TokenType.INOUT}),
            output=(param_mode in {TokenType.OUT, TokenType.INOUT}),
            variadic=(param_mode == TokenType.VARIADIC),
        )

    def _parse_function_parameter(self) -> t.Optional[exp.Expr]:
        param_mode = self._parse_parameter_mode()

        if param_mode:
            self._advance()

        # Parse parameter name and type
        param_name = self._parse_id_var()
        column_def = self._parse_column_def(this=param_name, computed_column=False)

        # Attach mode as constraint
        if param_mode and column_def:
            constraint = self._create_mode_constraint(param_mode)
            if not column_def.args.get("constraints"):
                column_def.set("constraints", [])
            column_def.args["constraints"].insert(0, constraint)

        return column_def

    def _parse_query_parameter(self) -> t.Optional[exp.Expr]:
        this = (
            self._parse_wrapped(self._parse_id_var)
            if self._match(TokenType.L_PAREN, advance=False)
            else None
        )
        self._match_text_seq("S")
        return self.expression(exp.Placeholder, this=this)

    def _parse_date_part(self) -> exp.Expr:
        part = self._parse_type()
        self._match(TokenType.COMMA)
        value = self._parse_bitwise()

        if part and isinstance(part, (exp.Column, exp.Literal)):
            part = exp.var(part.name)

        return self.expression(exp.Extract, this=part, expression=value)

    def _parse_unique_key(self) -> t.Optional[exp.Expr]:
        return None

    def _parse_jsonb_exists(self) -> exp.JSONBExists:
        return self.expression(
            exp.JSONBExists,
            this=self._parse_bitwise(),
            path=self._match(TokenType.COMMA)
            and self.dialect.to_json_path(self._parse_bitwise()),
        )

    def _parse_generated_as_identity(
        self,
    ) -> (
        exp.GeneratedAsIdentityColumnConstraint
        | exp.ComputedColumnConstraint
        | exp.GeneratedAsRowColumnConstraint
    ):
        this = super()._parse_generated_as_identity()

        if self._match_text_seq("STORED"):
            this = self.expression(exp.ComputedColumnConstraint, this=this.expression)

        return this

    def _parse_user_defined_type(self, identifier: exp.Identifier) -> t.Optional[exp.Expr]:
        udt_type: exp.Identifier | exp.Dot = identifier

        while self._match(TokenType.DOT):
            part = self._parse_id_var()
            if part:
                udt_type = exp.Dot(this=udt_type, expression=part)

        return exp.DataType.build(udt_type, udt=True)

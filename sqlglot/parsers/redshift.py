from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.dialects.dialect import map_date_part
from sqlglot.dialects.postgres import Postgres
from sqlglot.helper import seq_get
from sqlglot.parsers.postgres import Parser as _PostgresParser
from sqlglot.parser import build_convert_timezone
from sqlglot.tokens import TokenType

if t.TYPE_CHECKING:
    from sqlglot._typing import E


def _build_date_delta(expr_type: t.Type[E]) -> t.Callable[[t.List], E]:
    def _builder(args: t.List) -> E:
        expr = expr_type(
            this=seq_get(args, 2),
            expression=seq_get(args, 1),
            unit=map_date_part(seq_get(args, 0)),
        )
        if expr_type is exp.TsOrDsAdd:
            expr.set("return_type", exp.DataType.build("TIMESTAMP"))

        return expr

    return _builder


def _build_add_months(args: t.List) -> exp.TsOrDsAdd:
    return exp.TsOrDsAdd(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        unit=exp.var("month"),
        return_type=exp.DataType.build("TIMESTAMP"),
    )


def _build_convert_timezone(args: t.List) -> exp.Expr:
    return build_convert_timezone(args, "UTC")


def _build_regexp_substr(args: t.List) -> exp.RegexpExtract:
    return exp.RegexpExtract(
        this=seq_get(args, 0),
        expression=seq_get(args, 1),
        position=seq_get(args, 2),
        occurrence=seq_get(args, 3),
        parameters=seq_get(args, 4),
    )


def _build_split_to_array(args: t.List) -> exp.StringToArray:
    return exp.StringToArray(
        this=seq_get(args, 0), expression=seq_get(args, 1) or exp.Literal.string(",")
    )


def _approximate_parser(self: "Parser") -> t.Optional[exp.ApproxDistinct]:
    return self._parse_approximate_count()


def _sysdate_parser(self: "Parser") -> exp.CurrentTimestamp:
    return self.expression(exp.CurrentTimestamp, sysdate=True)


class Parser(_PostgresParser):
    FUNCTIONS = {
        **Postgres.Parser.FUNCTIONS,
        "ADD_MONTHS": _build_add_months,
        "CONVERT_TIMEZONE": _build_convert_timezone,
        "DATEADD": _build_date_delta(exp.TsOrDsAdd),
        "DATE_ADD": _build_date_delta(exp.TsOrDsAdd),
        "DATEDIFF": _build_date_delta(exp.TsOrDsDiff),
        "DATE_DIFF": _build_date_delta(exp.TsOrDsDiff),
        "GETDATE": exp.CurrentTimestamp.from_arg_list,
        "LISTAGG": exp.GroupConcat.from_arg_list,
        "REGEXP_SUBSTR": _build_regexp_substr,
        "SPLIT_TO_ARRAY": _build_split_to_array,
        "STRTOL": exp.FromBase.from_arg_list,
    }
    FUNCTIONS = {k: v for k, v in FUNCTIONS.items() if k != "GET_BIT"}

    NO_PAREN_FUNCTION_PARSERS = {
        **Postgres.Parser.NO_PAREN_FUNCTION_PARSERS,
        "APPROXIMATE": _approximate_parser,
        "SYSDATE": _sysdate_parser,
    }

    SUPPORTS_IMPLICIT_UNNEST = True

    def _parse_table(
        self,
        schema: bool = False,
        joins: bool = False,
        alias_tokens: t.Optional[t.Collection[TokenType]] = None,
        parse_bracket: bool = False,
        is_db_reference: bool = False,
        parse_partition: bool = False,
        consume_pipe: bool = False,
    ) -> t.Optional[exp.Expr]:
        # Redshift supports UNPIVOTing SUPER objects, e.g. `UNPIVOT foo.obj[0] AS val AT attr`
        unpivot = self._match(TokenType.UNPIVOT)
        table = super()._parse_table(
            schema=schema,
            joins=joins,
            alias_tokens=alias_tokens,
            parse_bracket=parse_bracket,
            is_db_reference=is_db_reference,
        )

        return self.expression(exp.Pivot, this=table, unpivot=True) if unpivot else table

    def _parse_convert(
        self, strict: bool, safe: t.Optional[bool] = None
    ) -> t.Optional[exp.Expr]:
        to = self._parse_types()
        self._match(TokenType.COMMA)
        this = self._parse_bitwise()
        return self.expression(exp.TryCast, this=this, to=to, safe=safe)

    def _parse_approximate_count(self) -> t.Optional[exp.ApproxDistinct]:
        index = self._index - 1
        func = self._parse_function()

        if isinstance(func, exp.Count) and isinstance(func.this, exp.Distinct):
            return self.expression(exp.ApproxDistinct, this=seq_get(func.this.expressions, 0))
        self._retreat(index)
        return None

    def _parse_projections(self) -> t.Tuple[t.List[exp.Expr], t.List[exp.Expr]]:
        projections, _ = super()._parse_projections()
        if self._prev and self._prev.text.upper() == "EXCLUDE" and self._curr:
            self._retreat(self._index - 1)

        # EXCLUDE clause always comes at the end of the projection list and applies to it as a whole
        exclude = (
            self._parse_wrapped_csv(self._parse_expression, optional=True)
            if self._match_text_seq("EXCLUDE")
            else []
        )

        if (
            exclude
            and isinstance(expr := projections[-1], exp.Alias)
            and expr.alias.upper() == "EXCLUDE"
        ):
            projections[-1] = expr.this.pop()

        return projections, exclude

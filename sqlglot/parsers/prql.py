from __future__ import annotations

import typing as t

from sqlglot import exp, parser
from sqlglot.helper import seq_get
from sqlglot.parser import (
    Parser as _Parser,
    _CONJUNCTION,
    _DISJUNCTION,
    _FUNCTIONS,
)
from sqlglot.tokens import TokenType


def _select_all(table: exp.Expr) -> t.Optional[exp.Select]:
    return exp.select("*").from_(table, copy=False) if table else None


def _transform_derive(self: "Parser", query: exp.Query) -> exp.Query:
    return self._parse_selection(query)


def _transform_select(self: "Parser", query: exp.Query) -> exp.Query:
    return self._parse_selection(query, append=False)


def _transform_take(self: "Parser", query: exp.Query) -> t.Optional[exp.Query]:
    return self._parse_take(query)


def _transform_filter(self: "Parser", query: exp.Query) -> exp.Query:
    return query.where(self._parse_disjunction())


def _transform_append(self: "Parser", query: exp.Query) -> exp.Query:
    return query.union(
        _select_all(self._parse_table()), distinct=False, copy=False  # type: ignore
    )


def _transform_remove(self: "Parser", query: exp.Query) -> exp.Query:
    return query.except_(
        _select_all(self._parse_table()), distinct=False, copy=False  # type: ignore
    )


def _transform_intersect(self: "Parser", query: exp.Query) -> exp.Query:
    return query.intersect(
        _select_all(self._parse_table()), distinct=False, copy=False  # type: ignore
    )


def _transform_sort(self: "Parser", query: exp.Select) -> t.Optional[exp.Query]:
    return self._parse_order_by(query)


def _transform_aggregate(self: "Parser", query: exp.Query) -> exp.Query:
    return self._parse_selection(
        query, parse_method=self._parse_aggregate, append=False
    )


def _build_sum(args: t.List) -> exp.Expr:
    return exp.func("COALESCE", exp.Sum(this=seq_get(args, 0)), 0)


class Parser(_Parser):
    CONJUNCTION = {
        **_CONJUNCTION,
        TokenType.DAMP: exp.And,
    }

    DISJUNCTION = {
        **_DISJUNCTION,
        TokenType.DPIPE: exp.Or,
    }

    TRANSFORM_PARSERS = {
        "DERIVE": _transform_derive,
        "SELECT": _transform_select,
        "TAKE": _transform_take,
        "FILTER": _transform_filter,
        "APPEND": _transform_append,
        "REMOVE": _transform_remove,
        "INTERSECT": _transform_intersect,
        "SORT": _transform_sort,
        "AGGREGATE": _transform_aggregate,
    }

    FUNCTIONS = {
        **_FUNCTIONS,
        "AVERAGE": exp.Avg.from_arg_list,
        "SUM": _build_sum,
    }

    def _parse_equality(self) -> t.Optional[exp.Expr]:
        eq = self._parse_tokens(self._parse_comparison, self.EQUALITY)
        if not isinstance(eq, (exp.EQ, exp.NEQ)):
            return eq

        # https://prql-lang.org/book/reference/spec/null.html
        if isinstance(eq.expression, exp.Null):
            is_exp = exp.Is(this=eq.this, expression=eq.expression)
            return is_exp if isinstance(eq, exp.EQ) else exp.Not(this=is_exp)
        if isinstance(eq.this, exp.Null):
            is_exp = exp.Is(this=eq.expression, expression=eq.this)
            return is_exp if isinstance(eq, exp.EQ) else exp.Not(this=is_exp)
        return eq

    def _parse_statement(self) -> t.Optional[exp.Expr]:
        expression = self._parse_expression()
        expression = expression if expression else self._parse_query()
        return expression

    def _parse_query(self) -> t.Optional[exp.Query]:
        from_ = self._parse_from()

        if not from_:
            return None

        query = exp.select("*").from_(from_, copy=False)

        while self._match_texts(self.TRANSFORM_PARSERS):
            query = self.TRANSFORM_PARSERS[self._prev.text.upper()](self, query)  # type: ignore

        return query

    def _parse_selection(
        self,
        query: exp.Query,
        parse_method: t.Optional[t.Callable] = None,
        append: bool = True,
    ) -> exp.Query:
        parse_method = parse_method if parse_method else self._parse_expression
        if self._match(TokenType.L_BRACE):
            selects = self._parse_csv(parse_method)

            if not self._match(TokenType.R_BRACE, expression=query):
                self.raise_error("Expecting }")
        else:
            expression = parse_method()
            selects = [expression] if expression else []

        projections = {
            select.alias_or_name: select.this if isinstance(select, exp.Alias) else select
            for select in query.selects
        }

        selects = [
            select.transform(
                lambda s: (projections[s.name].copy() if s.name in projections else s)
                if isinstance(s, exp.Column)
                else s,
                copy=False,
            )
            for select in selects
        ]

        return query.select(*selects, append=append, copy=False)

    def _parse_take(self, query: exp.Query) -> t.Optional[exp.Query]:
        num = self._parse_number()  # TODO: TAKE for ranges a..b
        return query.limit(num) if num else None

    def _parse_ordered(
        self, parse_method: t.Optional[t.Callable] = None
    ) -> t.Optional[exp.Ordered]:
        asc = self._match(TokenType.PLUS)
        desc = self._match(TokenType.DASH) or (asc and False)
        term = term = super()._parse_ordered(parse_method=parse_method)
        if term and desc:
            term.set("desc", True)
            term.set("nulls_first", False)
        return term

    def _parse_order_by(self, query: exp.Select) -> t.Optional[exp.Query]:
        l_brace = self._match(TokenType.L_BRACE)
        expressions = self._parse_csv(self._parse_ordered)
        if l_brace and not self._match(TokenType.R_BRACE):
            self.raise_error("Expecting }")
        return query.order_by(self.expression(exp.Order, expressions=expressions), copy=False)

    def _parse_aggregate(self) -> t.Optional[exp.Expr]:
        alias = None
        if self._next and self._next.token_type == TokenType.ALIAS:
            alias = self._parse_id_var(any_token=True)
            self._match(TokenType.ALIAS)

        name = self._curr and self._curr.text.upper()
        func_builder = self.FUNCTIONS.get(name)
        if func_builder:
            self._advance()
            args = self._parse_column()
            func = func_builder([args])
        else:
            self.raise_error(f"Unsupported aggregation function {name}")
        if alias:
            return self.expression(exp.Alias, this=func, alias=alias)
        return func

    def _parse_expression(self) -> t.Optional[exp.Expr]:
        if self._next and self._next.token_type == TokenType.ALIAS:
            alias = self._parse_id_var(True)
            self._match(TokenType.ALIAS)
            return self.expression(exp.Alias, this=self._parse_assignment(), alias=alias)
        return self._parse_assignment()

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
        return self._parse_table_parts()

    def _parse_from(
        self,
        joins: bool = False,
        skip_from_token: bool = False,
        consume_pipe: bool = False,
    ) -> t.Optional[exp.From]:
        if not skip_from_token and not self._match(TokenType.FROM):
            return None

        return self.expression(
            exp.From, comments=self._prev_comments, this=self._parse_table(joins=joins)
        )

from __future__ import annotations

import typing as t

from sqlglot import exp, parser
from sqlglot.parser import (
    Parser as _Parser,
    binary_range_parser,
    _FUNCTIONS,
    _STATEMENT_PARSERS,
    _RANGE_PARSERS,
)
from sqlglot.tokens import TokenType


def _build_strftime(args: t.List) -> exp.Anonymous | exp.TimeToStr:
    if len(args) == 1:
        args.append(exp.CurrentTimestamp())
    if len(args) == 2:
        return exp.TimeToStr(this=exp.TsOrDsToTimestamp(this=args[1]), format=args[0])
    return exp.Anonymous(this="STRFTIME", expressions=args)


def _build_datetime(args: t.List) -> exp.Anonymous:
    return exp.Anonymous(this="DATETIME", expressions=args)


def _build_json_group_object(args: t.List) -> exp.JSONObjectAgg:
    return exp.JSONObjectAgg(expressions=args)


def _build_time(args: t.List) -> exp.Anonymous:
    return exp.Anonymous(this="TIME", expressions=args)


def _attach_statement(self: "Parser") -> exp.Attach | exp.Detach:
    return self._parse_attach_detach()


def _detach_statement(self: "Parser") -> exp.Attach | exp.Detach:
    return self._parse_attach_detach(is_attach=False)


class Parser(_Parser):
    STRING_ALIASES = True
    ALTER_RENAME_REQUIRES_COLUMN = False
    JOINS_HAVE_EQUAL_PRECEDENCE = True
    ADD_JOIN_ON_TRUE = True

    FUNCTIONS = {
        **_FUNCTIONS,
        "DATETIME": _build_datetime,
        "EDITDIST3": exp.Levenshtein.from_arg_list,
        "JSON_GROUP_ARRAY": exp.JSONArrayAgg.from_arg_list,
        "JSON_GROUP_OBJECT": _build_json_group_object,
        "STRFTIME": _build_strftime,
        "SQLITE_VERSION": exp.CurrentVersion.from_arg_list,
        "TIME": _build_time,
    }

    STATEMENT_PARSERS = {
        **_STATEMENT_PARSERS,
        TokenType.ATTACH: _attach_statement,
        TokenType.DETACH: _detach_statement,
    }

    RANGE_PARSERS = {
        **_RANGE_PARSERS,
        # https://www.sqlite.org/lang_expr.html
        TokenType.MATCH: binary_range_parser(exp.Match),
    }

    def _parse_unique(self) -> exp.UniqueColumnConstraint:
        # Do not consume more tokens if UNIQUE is used as a standalone constraint, e.g:
        # CREATE TABLE foo (bar TEXT UNIQUE REFERENCES baz ...)
        if self._curr.text.upper() in self.CONSTRAINT_PARSERS:
            return self.expression(exp.UniqueColumnConstraint)

        return super()._parse_unique()

    def _parse_attach_detach(self, is_attach=True) -> exp.Attach | exp.Detach:
        self._match(TokenType.DATABASE)
        this = self._parse_expression()

        return (
            self.expression(exp.Attach, this=this)
            if is_attach
            else self.expression(exp.Detach, this=this)
        )

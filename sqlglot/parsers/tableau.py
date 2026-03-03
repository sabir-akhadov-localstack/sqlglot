import typing as t

from sqlglot import exp
from sqlglot.helper import seq_get
from sqlglot.parser import Parser as _Parser, _FUNCTIONS


def _build_countd(args: t.List) -> exp.Count:
    return exp.Count(this=exp.Distinct(expressions=args))


def _build_findnth(args: t.List) -> exp.StrPosition:
    return exp.StrPosition(
        this=seq_get(args, 0), substr=seq_get(args, 1), occurrence=seq_get(args, 2)
    )


class Parser(_Parser):
    FUNCTIONS = {
        **_FUNCTIONS,
        "COUNTD": _build_countd,
        "FIND": exp.StrPosition.from_arg_list,
        "FINDNTH": _build_findnth,
    }
    NO_PAREN_IF_COMMANDS = False

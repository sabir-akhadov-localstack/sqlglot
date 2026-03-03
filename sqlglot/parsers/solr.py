from sqlglot import exp
from sqlglot.parser import Parser as _Parser, _DISJUNCTION
from sqlglot.tokens import TokenType


class Parser(_Parser):
    DISJUNCTION = {
        **_DISJUNCTION,
        TokenType.DPIPE: exp.Or,
    }

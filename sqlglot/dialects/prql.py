from __future__ import annotations

import typing as t

from sqlglot import exp, tokens
from sqlglot.dialects.dialect import Dialect
from sqlglot.parsers.prql import Parser as _PRQLParser
from sqlglot.tokens import TokenType


class PRQL(Dialect):
    DPIPE_IS_STRING_CONCAT = False

    class Tokenizer(tokens.Tokenizer):
        IDENTIFIERS = ["`"]
        QUOTES = ["'", '"']

        SINGLE_TOKENS = {
            **tokens.Tokenizer.SINGLE_TOKENS,
            "=": TokenType.ALIAS,
            "'": TokenType.QUOTE,
            '"': TokenType.QUOTE,
            "`": TokenType.IDENTIFIER,
            "#": TokenType.COMMENT,
        }

        KEYWORDS = {
            **tokens.Tokenizer.KEYWORDS,
        }

    Parser = _PRQLParser

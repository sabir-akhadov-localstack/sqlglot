from __future__ import annotations


from sqlglot import exp
from sqlglot.dialects.trino import Trino
from sqlglot.parsers.dune import Parser as _DuneParser


class Dune(Trino):
    Parser = _DuneParser

    class Tokenizer(Trino.Tokenizer):
        HEX_STRINGS = ["0x", ("X'", "'")]

    class Generator(Trino.Generator):
        TRANSFORMS = {
            **Trino.Generator.TRANSFORMS,
            exp.HexString: lambda self, e: f"0x{e.this}",
        }

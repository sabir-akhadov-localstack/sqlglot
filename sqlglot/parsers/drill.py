from sqlglot import exp
from sqlglot.dialects.dialect import build_formatted_time
from sqlglot.parser import Parser as _Parser, _FUNCTIONS


class Parser(_Parser):
    STRICT_CAST = False

    FUNCTIONS = {
        **_FUNCTIONS,
        "REPEATED_COUNT": exp.ArraySize.from_arg_list,
        "TO_TIMESTAMP": exp.TimeStrToTime.from_arg_list,
        "TO_CHAR": build_formatted_time(exp.TimeToStr, "drill"),
        "LEVENSHTEIN_DISTANCE": exp.Levenshtein.from_arg_list,
    }

    LOG_DEFAULTS_TO_LN = True

"""Company and role normalization for application keys (research R8)."""

import re

LEGAL_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "corp",
        "corporation",
        "co",
        "company",
        "gmbh",
        "plc",
        "pvt",
        "private",
        "sa",
        "ag",
        "bv",
    }
)

_PUNCTUATION = re.compile(r"[^\w\s]|_")
_EDGES = re.compile(r"^[\W_]+|[\W_]+$")


def norm_company(s: str) -> str:
    words = _PUNCTUATION.sub(" ", s.casefold().replace("&", " and ")).split()
    while len(words) > 1 and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def norm_role(s: str | None) -> str:
    if not s:
        return ""
    return _EDGES.sub("", " ".join(s.casefold().split()))


def make_key(ck: str, rk: str) -> str:
    return f"{ck}|{rk}"

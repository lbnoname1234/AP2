from __future__ import annotations
import re
from dataclasses import dataclass

from ifp_ast import (
    CHARS,
    CHARS_DECODED,
    TBinOp,
    TBool,
    TIf,
    TInt,
    TLam,
    TString,
    TUnOp,
    TVar,
    Term,
)


@dataclass(frozen=True)
class ParseError(Exception):
    kind: str
    index: int | None = None
    ch: str | None = None

    def __str__(self) -> str:
        if self.kind == "UnexpectedChar":
            return f"UnexpectedChar({self.ch!r}, {self.index})"
        if self.kind == "UnusedInput":
            return f"UnusedInput({self.index})"
        return "UnexpectedEOF"


# Reverse of printer._ENCODE_MAP: encoded char -> human-readable char.
_DECODE_MAP = dict(zip(CHARS, CHARS_DECODED))
 
# base-94 digit value for each encoded character ('!' -> 0, ... '~' -> 93).
_BASE94_DIGITS = {c: i for i, c in enumerate(CHARS)}
 
 
def _tokenize(inp: str) -> list[tuple[str, int]]:
    """Split input into (token_text, start_index) pairs on whitespace runs."""
    return [(m.group(0), m.start()) for m in re.finditer(r"\S+", inp)]
 
 
def _decode_base94(body: str, body_start: int) -> int:
    if not body:
        raise ParseError(kind="UnexpectedEOF")
    value = 0
    for offset, ch in enumerate(body):
        if ch not in _BASE94_DIGITS:
            raise ParseError(kind="UnexpectedChar", index=body_start + offset, ch=ch)
        value = value * 94 + _BASE94_DIGITS[ch]
    return value
 
 
def _decode_string(body: str, body_start: int) -> str:
    out: list[str] = []
    for offset, ch in enumerate(body):
        if ch not in _DECODE_MAP:
            raise ParseError(kind="UnexpectedChar", index=body_start + offset, ch=ch)
        out.append(_DECODE_MAP[ch])
    return "".join(out)
 
 
class _Parser:
    def __init__(self, tokens: list[tuple[str, int]]):
        self.tokens = tokens
        self.pos = 0
 
    def _peek(self) -> tuple[str, int]:
        if self.pos >= len(self.tokens):
            raise ParseError(kind="UnexpectedEOF")
        return self.tokens[self.pos]
 
    def _advance(self) -> tuple[str, int]:
        tok = self._peek()
        self.pos += 1
        return tok
 
    def parse_term(self) -> Term:
        text, start = self._advance()
        indicator = text[0]
        body = text[1:]
        body_start = start + 1
 
        if indicator == "T":
            self._require_empty_body(body, body_start)
            return TBool(True)
 
        if indicator == "F":
            self._require_empty_body(body, body_start)
            return TBool(False)
 
        if indicator == "I":
            return TInt(_decode_base94(body, body_start))
 
        if indicator == "S":
            return TString(_decode_string(body, body_start))
 
        if indicator == "v":
            return TVar(_decode_base94(body, body_start))
 
        if indicator == "L":
            var = _decode_base94(body, body_start)
            inner = self.parse_term()
            return TLam(var, inner)
 
        if indicator == "U":
            op = self._require_single_char_op(body, body_start)
            operand = self.parse_term()
            return TUnOp(op, operand)
 
        if indicator == "B":
            op = self._require_single_char_op(body, body_start)
            left = self.parse_term()
            right = self.parse_term()
            return TBinOp(left, op, right)
 
        if indicator == "?":
            self._require_empty_body(body, body_start)
            cond = self.parse_term()
            true_branch = self.parse_term()
            false_branch = self.parse_term()
            return TIf(cond, true_branch, false_branch)
 
        raise ParseError(kind="UnexpectedChar", index=start, ch=indicator)
 
    @staticmethod
    def _require_empty_body(body: str, body_start: int) -> None:
        if body:
            raise ParseError(kind="UnexpectedChar", index=body_start, ch=body[0])
 
    @staticmethod
    def _require_single_char_op(body: str, body_start: int) -> str:
        if not body:
            raise ParseError(kind="UnexpectedEOF")
        if len(body) > 1:
            raise ParseError(kind="UnexpectedChar", index=body_start + 1, ch=body[1])
        return body
 
 
def p_term(inp: str) -> Term:
    tokens = _tokenize(inp)
    if not tokens:
        raise ParseError(kind="UnexpectedEOF")
 
    parser = _Parser(tokens)
    term = parser.parse_term()
 
    if parser.pos < len(parser.tokens):
        _, idx = parser.tokens[parser.pos]
        raise ParseError(kind="UnusedInput", index=idx)
 
    return term
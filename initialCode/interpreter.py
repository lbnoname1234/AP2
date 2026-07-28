from __future__ import annotations

from dataclasses import dataclass

from ifp_ast import CHARS, CHARS_DECODED, TBinOp, TBool, TIf, TInt, TLam, TString, TUnOp, TVar, Term
from printer import encode_string, to_base94


MAX_STEPS = 10_000_000


class InterpreterError(Exception):
    pass


class BetaReductionLimit(InterpreterError):
    pass


class ScopeError(InterpreterError):
    pass


class TypeError_(InterpreterError):
    pass


class ArithmeticError_(InterpreterError):
    pass


class UnknownUnOp(InterpreterError):
    def __init__(self, op: str):
        super().__init__(f"Unknown unary operator: {op}")
        self.op = op


class UnknownBinOp(InterpreterError):
    def __init__(self, op: str):
        super().__init__(f"Unknown binary operator: {op}")
        self.op = op


@dataclass
class VInt:
    value: int


@dataclass
class VBool:
    value: bool


@dataclass
class VString:
    value: str


@dataclass
class VClosure:
    var: int
    body: Term
    env: dict[int, "Thunk"]


Value = VInt | VBool | VString | VClosure


@dataclass
class Thunk:
    kind: str
    value: Value | None = None
    steps: int = 0
    term: Term | None = None
    env: dict[int, "Thunk"] | None = None


def _to_term(v: Value) -> Term:
    if isinstance(v, VInt):
        return TInt(v.value)
    if isinstance(v, VBool):
        return TBool(v.value)
    if isinstance(v, VString):
        return TString(v.value)
    if isinstance(v, VClosure):
        return TLam(v.var, v.body)
    raise TypeError(f"Unknown value type: {type(v).__name__}")

_DECODE_MAP = dict(zip(CHARS, CHARS_DECODED))
 
 
def _string_body_to_int(body: str) -> int:
    value = 0
    for ch in body:
        value = value * 94 + (ord(ch) - 33)
    return value
 
 
def _int_to_string_body(n: int) -> str:
    b94 = to_base94(n)
    if b94 is None:
        raise TypeError_("Cannot convert a negative integer to a string")
    return b94
 
 
def _decode_string_body(body: str) -> str:
    return "".join(_DECODE_MAP[ch] for ch in body)
 
 
def _trunc_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q
 
 
def _trunc_mod(a: int, b: int) -> int:
    return a - b * _trunc_div(a, b)
 
 
def _require_ints(a: Value, b: Value, op: str) -> None:
    if not isinstance(a, VInt) or not isinstance(b, VInt):
        raise TypeError_(f"Operator {op!r} requires integer operands")
 
 
def _require_bools(a: Value, b: Value, op: str) -> None:
    if not isinstance(a, VBool) or not isinstance(b, VBool):
        raise TypeError_(f"Operator {op!r} requires boolean operands")
 
 
def _require_strings(a: Value, b: Value, op: str) -> None:
    if not isinstance(a, VString) or not isinstance(b, VString):
        raise TypeError_(f"Operator {op!r} requires string operands")
 
 
def _values_equal(a: Value, b: Value) -> bool:
    if isinstance(a, VInt) and isinstance(b, VInt):
        return a.value == b.value
    if isinstance(a, VBool) and isinstance(b, VBool):
        return a.value == b.value
    if isinstance(a, VString) and isinstance(b, VString):
        return a.value == b.value
    raise TypeError_("Operator '=' requires both operands to be of the same type")
 
 
def _eval_unop(op: str, operand: Value) -> Value:
    if op == "-":
        if not isinstance(operand, VInt):
            raise TypeError_("Unary '-' requires an integer operand")
        return VInt(-operand.value)
 
    if op == "!":
        if not isinstance(operand, VBool):
            raise TypeError_("Unary '!' requires a boolean operand")
        return VBool(not operand.value)
 
    if op == "#":
        if not isinstance(operand, VString):
            raise TypeError_("Unary '#' requires a string operand")
        encoded_body = encode_string(operand.value)
        return VInt(_string_body_to_int(encoded_body))
 
    if op == "$":
        if not isinstance(operand, VInt):
            raise TypeError_("Unary '$' requires an integer operand")
        body = _int_to_string_body(operand.value)
        return VString(_decode_string_body(body))
 
    raise UnknownUnOp(op)
 
 
def _eval_binop(op: str, left: Value, right: Value) -> Value:
    if op == "+":
        _require_ints(left, right, op)
        return VInt(left.value + right.value)
 
    if op == "-":
        _require_ints(left, right, op)
        return VInt(left.value - right.value)
 
    if op == "*":
        _require_ints(left, right, op)
        return VInt(left.value * right.value)
 
    if op == "/":
        _require_ints(left, right, op)
        if right.value == 0:
            raise ArithmeticError_("Division by zero")
        return VInt(_trunc_div(left.value, right.value))
 
    if op == "%":
        _require_ints(left, right, op)
        if right.value == 0:
            raise ArithmeticError_("Modulo by zero")
        return VInt(_trunc_mod(left.value, right.value))
 
    if op == "<":
        _require_ints(left, right, op)
        return VBool(left.value < right.value)
 
    if op == ">":
        _require_ints(left, right, op)
        return VBool(left.value > right.value)
 
    if op == "=":
        return VBool(_values_equal(left, right))
 
    if op == "|":
        _require_bools(left, right, op)
        return VBool(left.value or right.value)
 
    if op == "&":
        _require_bools(left, right, op)
        return VBool(left.value and right.value)
 
    if op == ".":
        _require_strings(left, right, op)
        return VString(left.value + right.value)
 
    if op == "T":
        if not isinstance(left, VInt) or not isinstance(right, VString):
            raise TypeError_("Operator 'T' requires (int, string) operands")
        return VString(right.value[: left.value])
 
    if op == "D":
        if not isinstance(left, VInt) or not isinstance(right, VString):
            raise TypeError_("Operator 'D' requires (int, string) operands")
        return VString(right.value[left.value :])
 
    raise UnknownBinOp(op)


def interpret(check_max: bool, term: Term) -> tuple[Term, int]:
    steps = 0
    def force(thunk: Thunk) -> Value:
        # NOTE: intentionally NOT caching thunk.value here (testing hypothesis)
        assert thunk.term is not None and thunk.env is not None
        return eval_term(thunk.term, thunk.env)
    def eval_term(t: Term, env: dict[int, Thunk]) -> Value:
        # TODO
        nonlocal steps
 
        if isinstance(t, TInt):
            return VInt(t.value)
 
        if isinstance(t, TBool):
            return VBool(t.value)
 
        if isinstance(t, TString):
            return VString(t.value)
 
        if isinstance(t, TVar):
            if t.value not in env:
                raise ScopeError(f"Unbound variable: v{t.value}")
            return force(env[t.value])
 
        if isinstance(t, TLam):
            return VClosure(t.var, t.body, env)
 
        if isinstance(t, TUnOp):
            operand = eval_term(t.term, env)
            return _eval_unop(t.op, operand)
 
        if isinstance(t, TIf):
            cond = eval_term(t.cond, env)
            if not isinstance(cond, VBool):
                raise TypeError_("Condition of '?' must be a boolean")
            branch = t.true_branch if cond.value else t.false_branch
            return eval_term(branch, env)
 
        if isinstance(t, TBinOp):
            if t.op == "$":
                steps += 1
                if check_max and steps > MAX_STEPS:
                    raise BetaReductionLimit(
                        f"Exceeded maximum beta reduction steps ({MAX_STEPS})"
                    )
 
                func = eval_term(t.left, env)
                if not isinstance(func, VClosure):
                    raise TypeError_(
                        "Left-hand side of function application ('$') must be a lambda"
                    )
 
                arg_thunk = Thunk(kind="thunk", term=t.right, env=env)
                new_env = dict(func.env)
                new_env[func.var] = arg_thunk
                return eval_term(func.body, new_env)
 
            left = eval_term(t.left, env)
            right = eval_term(t.right, env)
            return _eval_binop(t.op, left, right)

        raise TypeError(f"Unknown term type: {type(t).__name__}")

    result = eval_term(term, {})
    return _to_term(result), steps

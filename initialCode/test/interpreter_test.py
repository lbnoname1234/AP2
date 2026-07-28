"""
Standalone test script for interpreter.py (IFP evaluator).

Run directly:

    python3 interpreter_test.py

(Also pytest-compatible: `pytest interpreter_test.py -v` works too, since
every check function is named test_*.)

Place this file in the same directory as ifp_ast.py, parser.py, printer.py,
and interpreter.py.
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import traceback

from ifp_ast import TBinOp, TBool, TIf, TInt, TLam, TString, TUnOp, TVar
from parser import p_term
from interpreter import (
    interpret,
    InterpreterError,
    BetaReductionLimit,
    ScopeError,
    TypeError_,
    ArithmeticError_,
    UnknownUnOp,
    UnknownBinOp,
)
import interpreter as interpreter_module


def run(program: str):
    """Parse + evaluate a program string, return (result_term, steps)."""
    term = p_term(program)
    return interpret(check_max=True, term=term)


def run_term(term):
    """Evaluate an already-built Term (bypassing the parser)."""
    return interpret(check_max=True, term=term)


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

def test_literal_bool_true():
    result, steps = run("T")
    assert result == TBool(True)
    assert steps == 0


def test_literal_bool_false():
    result, steps = run("F")
    assert result == TBool(False)


def test_literal_int():
    result, steps = run("I/6")
    assert result == TInt(1337)


def test_literal_string():
    result, steps = run("S" + __import__("printer").encode_string("Hello World!"))
    assert result == TString("Hello World!")


# ---------------------------------------------------------------------------
# Unary operators (spec 3.4)
# ---------------------------------------------------------------------------

def test_unop_negation():
    result, _ = run("U- I$")
    assert result == TInt(-3)


def test_unop_boolean_not():
    result, _ = run("U! T")
    assert result == TBool(False)


def test_unop_str_to_int():
    result, _ = run("U# S4%34")
    assert result == TInt(15818151)


def test_unop_int_to_str():
    result, _ = run("U$ I4%34")
    assert result == TString("test")


def test_unop_str_int_roundtrip():
    # Roundtrip holds EXCEPT for strings starting with 'a', because 'a' is
    # the character mapped to base-94 digit 0 -- and to_base94() does not
    # preserve leading zero digits (same reason "007" as an int prints
    # back as "7"). This is inherent to the format, not an interpreter bug.
    for s in ["test", "hello", "xyz123"]:
        as_int, _ = run_term(TUnOp("#", TString(s)))
        back, _ = run_term(TUnOp("$", as_int))
        assert back == TString(s), f"roundtrip failed for {s!r}"


def test_unop_str_int_roundtrip_leading_a_loses_leading_zero_digit():
    # Documents the known non-invertibility: "abc123" starts with 'a'
    # (base-94 digit 0), so converting to int and back drops it.
    as_int, _ = run_term(TUnOp("#", TString("abc123")))
    back, _ = run_term(TUnOp("$", as_int))
    assert back == TString("bc123")


def test_unop_str_int_roundtrip_empty_string_becomes_a():
    # Same root cause, extreme case: "" encodes to an empty body -> int 0.
    # But to_base94(0) always returns exactly one digit ('!', never ""),
    # since an "I" token's body must be non-empty (spec 3.2). So U$ (U# "")
    # produces "a", not "".
    as_int, _ = run_term(TUnOp("#", TString("")))
    assert as_int == TInt(0)
    back, _ = run_term(TUnOp("$", as_int))
    assert back == TString("a")


# ---------------------------------------------------------------------------
# Binary operators (spec 3.5)
# ---------------------------------------------------------------------------

def test_binop_addition():
    result, _ = run("B+ I# I$")
    assert result == TInt(5)


def test_binop_subtraction():
    result, _ = run("B- I$ I#")
    assert result == TInt(1)


def test_binop_multiplication():
    result, _ = run("B* I$ I#")
    assert result == TInt(6)


def test_binop_division_truncates_toward_zero():
    result, _ = run("B/ U- I( I#")
    assert result == TInt(-3)  # -7 / 2 == -3 (not -4, i.e. truncation not floor)


def test_binop_modulo_matches_truncating_division():
    result, _ = run("B% U- I( I#")
    assert result == TInt(-1)  # -7 % 2 == -1


def test_binop_less_than():
    result, _ = run("B< I$ I#")
    assert result == TBool(False)  # 3 < 2 -> false


def test_binop_greater_than():
    result, _ = run("B> I$ I#")
    assert result == TBool(True)  # 3 > 2 -> true


def test_binop_equality_true_and_false():
    result_eq, _ = run("B= I$ I$")
    assert result_eq == TBool(True)
    result_neq, _ = run("B= I$ I#")
    assert result_neq == TBool(False)


def test_binop_or():
    assert run("B| T F")[0] == TBool(True)
    assert run("B| F F")[0] == TBool(False)


def test_binop_and():
    assert run("B& T F")[0] == TBool(False)
    assert run("B& T T")[0] == TBool(True)


def test_binop_string_concat():
    result, _ = run("B. S4% S34")
    assert result == TString("test")


def test_binop_take_first_x_chars():
    result, _ = run("BT I$ S4%34")
    assert result == TString("tes")


def test_binop_drop_first_x_chars():
    result, _ = run("BD I$ S4%34")
    assert result == TString("t")


# ---------------------------------------------------------------------------
# Conditional (spec 3.6) -- must only evaluate the selected branch
# ---------------------------------------------------------------------------

def test_conditional_selects_true_branch():
    result, _ = run('? T I! I"')
    assert result == TInt(0)


def test_conditional_selects_false_branch():
    result, _ = run('? F I! I"')
    assert result == TInt(1)


def test_conditional_spec_example():
    result, _ = run("? B> I# I$ S9%3 S./")
    assert result == TString("no")


def test_conditional_does_not_evaluate_unselected_branch():
    # If the false-branch (division by zero) were evaluated, this would
    # raise ArithmeticError_. Since the condition picks the true-branch,
    # it must not be touched at all.
    term = TIf(TBool(True), TInt(42), TBinOp(TInt(1), "/", TInt(0)))
    result, _ = run_term(term)
    assert result == TInt(42)

    # And the reverse: selecting the false-branch must not evaluate a
    # failing true-branch either.
    term2 = TIf(TBool(False), TBinOp(TInt(1), "/", TInt(0)), TInt(99))
    result2, _ = run_term(term2)
    assert result2 == TInt(99)


# ---------------------------------------------------------------------------
# Lambda / application (spec 3.7, 3.8)
# ---------------------------------------------------------------------------

def test_identity_application():
    result, _ = run("B$ L# v# I!")
    assert result == TInt(0)


def test_spec_hello_world_application():
    program = "B$ B$ L# L$ v# B. SB%,,/ S}Q/2,$_ IK"
    result, steps = run(program)
    assert result == TString("Hello World!")
    assert steps == 2  # two "$" applications


def test_variable_shadowing():
    # (\x -> \x -> x) 111 222  -- inner x shadows outer, result is 222
    term = TBinOp(
        TBinOp(TLam(0, TLam(0, TVar(0))), "$", TInt(111)),
        "$",
        TInt(222),
    )
    result, _ = run_term(term)
    assert result == TInt(222)


def test_k_combinator_ignores_second_argument():
    # (\x -> \y -> x) 1 2  -- should return 1, ignoring y entirely
    term = TBinOp(
        TBinOp(TLam(1, TLam(2, TVar(1))), "$", TInt(1)),
        "$",
        TInt(2),
    )
    result, _ = run_term(term)
    assert result == TInt(1)


def test_reused_closure_applied_twice_does_not_corrupt():
    # twice = \f -> \x -> f (f x); twice (\y -> y + 1) 5  ->  7
    F, X, Y = 100, 101, 102
    inc = TLam(Y, TBinOp(TVar(Y), "+", TInt(1)))
    twice_body = TBinOp(TVar(F), "$", TBinOp(TVar(F), "$", TVar(X)))
    twice = TLam(F, TLam(X, twice_body))
    term = TBinOp(TBinOp(twice, "$", inc), "$", TInt(5))
    result, _ = run_term(term)
    assert result == TInt(7)


# ---------------------------------------------------------------------------
# Call-by-name semantics: repeated variable use, spec worked examples
# ---------------------------------------------------------------------------

def test_call_by_name_repeated_variable_use():
    # Spec 3.9 example reduction: v" (var 1) is used twice in the body,
    # each occurrence independently reduces "B* I$ I#" (3*2=6), then
    # 6 + 6 = 12.
    program = 'B$ L# B$ L" B+ v" v" B* I$ I# v8'
    result, _ = run(program)
    assert result == TInt(12)


def test_spec_big_recursive_example_result_and_step_count():
    # Spec 3.10: this exact program must evaluate to 16 using EXACTLY
    # 109 reduction steps (confirms plain, non-memoized call-by-name).
    program = (
        'B$ B$ L" B$ L# B$ v" B$ v# v# L# B$ v" B$ v# v# L" L# ? B= v# I! I"\n'
        'B$ L$ B+ B$ v" v$ B$ v" v$ B- v# I" I%'
    )
    result, steps = run(program)
    assert result == TInt(16), f"expected 16, got {result}"
    assert steps == 109, f"expected 109 steps, got {steps}"


# ---------------------------------------------------------------------------
# Execution limits (spec 3.10)
# ---------------------------------------------------------------------------

def test_beta_reduction_limit_enforced():
    # Omega combinator: (\x -> x x) (\x -> x x) -- never terminates.
    # Temporarily lower MAX_STEPS so the test runs quickly.
    original_max_steps = interpreter_module.MAX_STEPS
    interpreter_module.MAX_STEPS = 50
    try:
        term = p_term("B$ L! B$ v! v! L! B$ v! v!")
        try:
            interpret(check_max=True, term=term)
            raise AssertionError("expected BetaReductionLimit to be raised")
        except BetaReductionLimit:
            pass
    finally:
        interpreter_module.MAX_STEPS = original_max_steps


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_type_error_on_mismatched_operand_types():
    term = p_term("B+ I$ T")
    try:
        interpret(check_max=True, term=term)
        raise AssertionError("expected TypeError_")
    except TypeError_:
        pass


def test_type_error_on_equality_mismatched_types():
    term = p_term("B= I! T")
    try:
        interpret(check_max=True, term=term)
        raise AssertionError("expected TypeError_")
    except TypeError_:
        pass


def test_scope_error_on_unbound_variable():
    term = p_term("v!")
    try:
        interpret(check_max=True, term=term)
        raise AssertionError("expected ScopeError")
    except ScopeError:
        pass


def test_arithmetic_error_on_division_by_zero():
    term = p_term("B/ I$ I!")
    try:
        interpret(check_max=True, term=term)
        raise AssertionError("expected ArithmeticError_")
    except ArithmeticError_:
        pass


def test_arithmetic_error_on_modulo_by_zero():
    term = p_term("B% I$ I!")
    try:
        interpret(check_max=True, term=term)
        raise AssertionError("expected ArithmeticError_")
    except ArithmeticError_:
        pass


def test_unknown_unop_raises():
    term = p_term("UZ I!")
    try:
        interpret(check_max=True, term=term)
        raise AssertionError("expected UnknownUnOp")
    except UnknownUnOp:
        pass


def test_unknown_binop_raises():
    term = p_term("BZ I! I!")
    try:
        interpret(check_max=True, term=term)
        raise AssertionError("expected UnknownBinOp")
    except UnknownBinOp:
        pass


def test_application_of_non_function_raises_type_error():
    # I! $ I! -- applying a plain integer as if it were a function
    term = p_term("B$ I! I!")
    try:
        interpret(check_max=True, term=term)
        raise AssertionError("expected TypeError_")
    except TypeError_:
        pass


# ---------------------------------------------------------------------------
# Runner -- no pytest required
# ---------------------------------------------------------------------------

def run_all() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]

    passed, failed = 0, 0
    failures: list[tuple[str, str]] = []

    print(f"Running {len(tests)} tests for interpreter.py\n" + "-" * 60)
    for name, fn in tests:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            failed += 1
            short_reason = str(e) or e.__class__.__name__
            print(f"[FAIL] {name}: {short_reason}")
            failures.append((name, traceback.format_exc()))
        else:
            passed += 1
            print(f"[PASS] {name}")

    print("-" * 60)
    print(f"Result: {passed} passed, {failed} failed, {len(tests)} total")

    if failures:
        print("\nFirst failure traceback (for debugging):")
        print(failures[0][1])

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all())
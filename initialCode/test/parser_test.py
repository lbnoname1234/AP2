"""
Standalone test script for parser.py (Interstellar Functional Program parser).

Unlike a normal pytest file, this can be run directly and prints PASS/FAIL
results to the console immediately -- no need to install or invoke pytest:

    python3 parser_test.py

(It is still pytest-compatible: `pytest parser_test.py -v` also works, since
every check function is named test_*.)

NOTE: parser.py currently only contains a stub for `p_term` (see the
`# TODO` marker in parser.py). Most tests below are EXPECTED TO FAIL until
`p_term` is properly implemented -- that is the point: this script tells you
exactly which parts of the spec are not yet handled.
"""

from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import traceback

from ifp_ast import TBool, TInt, TString, TVar, TLam, TUnOp, TBinOp, TIf, Term
from parser import p_term, ParseError
from printer import pp_term, encode_string


# ---------------------------------------------------------------------------
# Helper: build an IFP token string from a Term using the already-implemented
# printer, then parse it back. Gives strong coverage without hand-computing
# base-94 digits for every case.
# ---------------------------------------------------------------------------

def roundtrip(term: Term) -> Term:
    encoded = pp_term(term)
    return p_term(encoded)


# ---------------------------------------------------------------------------
# Literals
# ---------------------------------------------------------------------------

def test_bool_true():
    assert p_term("T") == TBool(True)


def test_bool_false():
    assert p_term("F") == TBool(False)


def test_int_roundtrip_various_values():
    for value in [0, 1, 3, 7, 93, 94, 1337, 15818151, 1_000_000]:
        assert roundtrip(TInt(value)) == TInt(value), f"failed for value={value}"


def test_int_spec_example_I_slash_6():
    # Spec 3.2: "I/6 represents the number 1337"
    assert p_term("I/6") == TInt(1337)


def test_int_zero():
    assert p_term("I!") == TInt(0)


def test_int_negative_encodes_as_unop_negation():
    # printer.py cannot encode a negative int as a plain "I" token (base-94
    # digits are non-negative), so it falls back to "U- I<abs(value)>".
    # Parsing that back must therefore yield a TUnOp node, NOT a raw TInt.
    assert roundtrip(TInt(-3)) == TUnOp("-", TInt(3))


def test_string_roundtrip_various_values():
    for value in ["", "a", "test", "Hello World!", "Hello\nWorld", "ABC123 xyz!?"]:
        assert roundtrip(TString(value)) == TString(value), f"failed for value={value!r}"


def test_string_spec_example_hello_world():
    token = "S" + encode_string("Hello World!")
    assert p_term(token) == TString("Hello World!")


def test_variable_roundtrip_various_ids():
    for var_id in [0, 1, 2, 8, 93, 94, 200]:
        assert roundtrip(TVar(var_id)) == TVar(var_id), f"failed for var_id={var_id}"


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

def test_unop_spec_example_negation():
    # Spec 3.4: "U- I$ -> -3" (I$ decodes to 3)
    assert p_term("U- I$") == TUnOp("-", TInt(3))


def test_unop_spec_example_boolean_not():
    # Spec 3.4: "U! T -> false"
    assert p_term("U! T") == TUnOp("!", TBool(True))


def test_unop_spec_example_str_to_int():
    # Spec 3.4: "U# S4%34 -> 15818151" (S4%34 decodes to "test")
    assert p_term("U# S4%34") == TUnOp("#", TString("test"))


def test_unop_spec_example_int_to_str():
    # Spec 3.4: "U$ I4%34 -> test" (I4%34 == 15818151)
    assert p_term("U$ I4%34") == TUnOp("$", TInt(15818151))


def test_unop_roundtrip_all_ops():
    for op in ["-", "!", "#", "$"]:
        original = TUnOp(op, TInt(5))
        assert roundtrip(original) == original, f"failed for op={op!r}"


def test_binop_roundtrip_all_ops():
    for op in ["+", "-", "*", "/", "%", "<", ">", "=", "|", "&", ".", "T", "D", "$"]:
        original = TBinOp(TInt(2), op, TInt(3))
        assert roundtrip(original) == original, f"failed for op={op!r}"


def test_binop_spec_example_addition():
    # Spec 3.5: "B+ I# I$ -> 5" (I#=2, I$=3)
    assert p_term("B+ I# I$") == TBinOp(TInt(2), "+", TInt(3))


def test_binop_spec_example_division_with_nested_unop():
    # Spec 3.5: "B/ U- I( I# -> -3" (I(=7, I#=2)
    term = p_term("B/ U- I( I#")
    assert term == TBinOp(TUnOp("-", TInt(7)), "/", TInt(2))


def test_binop_spec_example_string_concat():
    # Spec 3.5: "B. S4% S34 -> test"
    term = p_term("B. S4% S34")
    assert isinstance(term, TBinOp)
    assert term.op == "."
    assert isinstance(term.left, TString)
    assert isinstance(term.right, TString)


def test_conditional_simple():
    assert p_term('? T I! I"') == TIf(TBool(True), TInt(0), TInt(1))


def test_conditional_roundtrip_nested():
    original = TIf(
        TBinOp(TInt(1), ">", TInt(2)),
        TString("yes"),
        TString("no"),
    )
    assert roundtrip(original) == original


def test_lambda_identity_function():
    assert p_term("L! v!") == TLam(0, TVar(0))


def test_lambda_roundtrip_nested():
    original = TLam(2, TLam(3, TVar(2)))
    assert roundtrip(original) == original


def test_lambda_application_of_identity():
    assert p_term("B$ L# v# I!") == TBinOp(TLam(2, TVar(2)), "$", TInt(0))


# ---------------------------------------------------------------------------
# Full programs taken directly from the spec (section 3.8 / 3.9)
# ---------------------------------------------------------------------------

def test_spec_program_hello_world_application():
    # Spec 3.8: ((\v2 -> \v3 -> v2) ("Hello" . " World!")) 42
    program = "B$ B$ L# L$ v# B. SB%,,/ S}Q/2,$_ IK"
    term = p_term(program)
    assert term == TBinOp(
        TBinOp(
            TLam(2, TLam(3, TVar(2))),
            "$",
            TBinOp(TString("Hello"), ".", TString(" World!")),
        ),
        "$",
        TInt(42),
    )


def test_spec_program_call_by_name_shape():
    # Spec 3.9 example reduction; just check outer application shape (the
    # interpreter test suite covers actual reduction/evaluation).
    program = 'B$ L# B$ L" B+ v" v" B* I$ I# v8'
    term = p_term(program)
    assert isinstance(term, TBinOp)
    assert term.op == "$"
    assert isinstance(term.left, TLam)


# ---------------------------------------------------------------------------
# Whitespace handling
# ---------------------------------------------------------------------------

def test_whitespace_single_space_separated_tokens():
    assert p_term('B+ I! I"') == TBinOp(TInt(0), "+", TInt(1))


def test_whitespace_no_extra_padding_required():
    assert p_term("T") == TBool(True)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_error_empty_input_raises_eof():
    try:
        p_term("")
    except ParseError as e:
        assert e.kind == "UnexpectedEOF"
        return
    raise AssertionError("expected ParseError for empty input")


def test_error_unknown_indicator_raises_unexpected_char():
    try:
        p_term("Z!")
    except ParseError as e:
        assert e.kind == "UnexpectedChar"
        assert e.ch == "Z"
        assert e.index == 0
        return
    raise AssertionError("expected ParseError for unknown indicator 'Z'")


def test_error_trailing_unused_input_raises():
    try:
        p_term("T T")
    except ParseError as e:
        assert e.kind == "UnusedInput"
        return
    raise AssertionError("expected ParseError for trailing unused input")


def test_error_truncated_binary_op_raises():
    try:
        p_term("B+ I!")
    except ParseError:
        return
    raise AssertionError("expected ParseError for truncated binary op")


def test_error_truncated_conditional_raises():
    try:
        p_term("? T I!")
    except ParseError:
        return
    raise AssertionError("expected ParseError for truncated conditional")


def test_error_truncated_unary_op_raises():
    try:
        p_term("U-")
    except ParseError:
        return
    raise AssertionError("expected ParseError for truncated unary op")


def test_error_str_formatting():
    err1 = ParseError(kind="UnexpectedChar", index=5, ch="Z")
    assert str(err1) == "UnexpectedChar('Z', 5)"

    err2 = ParseError(kind="UnusedInput", index=3)
    assert str(err2) == "UnusedInput(3)"

    err3 = ParseError(kind="UnexpectedEOF")
    assert str(err3) == "UnexpectedEOF"


# ---------------------------------------------------------------------------
# Runner -- no pytest required
# ---------------------------------------------------------------------------

def run_all() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]

    passed, failed = 0, 0
    failures: list[tuple[str, str]] = []

    print(f"Running {len(tests)} tests for parser.py\n" + "-" * 60)
    for name, fn in tests:
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - want to catch AssertionError and others
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
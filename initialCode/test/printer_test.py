"""
Standalone test script for printer.py (IFP pretty-printer / encoder).

Run directly:

    python3 printer_test.py

(Also pytest-compatible: `pytest printer_test.py -v` works too.)

Place this file in the same directory as ifp_ast.py and printer.py.
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import traceback

from ifp_ast import TBinOp, TBool, TIf, TInt, TLam, TString, TUnOp, TVar
from printer import to_base94, encode_string, pp_term


# ---------------------------------------------------------------------------
# to_base94
# ---------------------------------------------------------------------------

def test_to_base94_zero():
    assert to_base94(0) == "!"


def test_to_base94_single_digit_values():
    # digit d -> chr(33 + d)
    assert to_base94(1) == '"'
    assert to_base94(93) == "~"


def test_to_base94_multi_digit_value():
    # spec 3.2: I/6 represents 1337
    assert to_base94(1337) == "/6"


def test_to_base94_boundary_93_to_94():
    # 93 is the last single-digit value; 94 requires two digits ("\"!" = 1*94+0)
    assert to_base94(93) == "~"
    assert to_base94(94) == '"!'


def test_to_base94_negative_returns_none():
    assert to_base94(-1) is None
    assert to_base94(-1000) is None


def test_to_base94_large_value_roundtrips_via_manual_decode():
    value = 15818151
    encoded = to_base94(value)
    # manually decode back using the inverse arithmetic to confirm it's
    # a valid base-94 representation (no lookup table needed)
    decoded = 0
    for ch in encoded:
        decoded = decoded * 94 + (ord(ch) - 33)
    assert decoded == value


# ---------------------------------------------------------------------------
# encode_string
# ---------------------------------------------------------------------------

def test_encode_string_empty():
    assert encode_string("") == ""


def test_encode_string_spec_example():
    # spec 3.3: body "B%,,/}Q/2,$_" decodes to "Hello World!"
    assert encode_string("Hello World!") == "B%,,/}Q/2,$_"


def test_encode_string_contains_newline():
    encoded = encode_string("a\nb")
    assert len(encoded) == 3


def test_encode_string_rejects_unsupported_characters():
    # '{' and '}' are explicitly excluded from the string alphabet (spec 3.3
    # / ifp_ast.py CHARS_DECODED excludes them) -- braces are reserved.
    try:
        encode_string("{")
        raise AssertionError("expected ValueError for unsupported character '{'")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# pp_term -- literals
# ---------------------------------------------------------------------------

def test_pp_term_bool():
    assert pp_term(TBool(True)) == "T"
    assert pp_term(TBool(False)) == "F"


def test_pp_term_positive_int():
    assert pp_term(TInt(1337)) == "I/6"
    assert pp_term(TInt(0)) == "I!"


def test_pp_term_negative_int_falls_back_to_unop():
    # printer.py cannot encode negative ints directly as an "I" token
    # (base-94 digits are non-negative), so it emits "U- I<abs(value)>".
    assert pp_term(TInt(-3)) == "U- I$"


def test_pp_term_string():
    assert pp_term(TString("Hello World!")) == "SB%,,/}Q/2,$_"
    assert pp_term(TString("")) == "S"


def test_pp_term_variable():
    assert pp_term(TVar(0)) == "v!"
    assert pp_term(TVar(23)) == "v8"


def test_pp_term_variable_negative_raises():
    try:
        pp_term(TVar(-1))
        raise AssertionError("expected ValueError for negative variable id")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# pp_term -- compound terms
# ---------------------------------------------------------------------------

def test_pp_term_lambda():
    assert pp_term(TLam(0, TVar(0))) == "L! v!"


def test_pp_term_nested_lambda():
    assert pp_term(TLam(2, TLam(3, TVar(2)))) == "L# L$ v#"


def test_pp_term_lambda_negative_var_raises():
    try:
        pp_term(TLam(-1, TInt(0)))
        raise AssertionError("expected ValueError for negative lambda var id")
    except ValueError:
        pass


def test_pp_term_unop():
    assert pp_term(TUnOp("-", TInt(3))) == "U- I$"
    assert pp_term(TUnOp("!", TBool(True))) == "U! T"


def test_pp_term_binop():
    assert pp_term(TBinOp(TInt(2), "+", TInt(3))) == "B+ I# I$"


def test_pp_term_binop_nested():
    assert pp_term(TBinOp(TUnOp("-", TInt(7)), "/", TInt(2))) == "B/ U- I( I#"


def test_pp_term_conditional():
    result = pp_term(TIf(TBool(True), TInt(0), TInt(1)))
    assert result == '? T I! I"'


def test_pp_term_spec_hello_world_program():
    # spec 3.8 worked example
    term = TBinOp(
        TBinOp(
            TLam(2, TLam(3, TVar(2))),
            "$",
            TBinOp(TString("Hello"), ".", TString(" World!")),
        ),
        "$",
        TInt(42),
    )
    assert pp_term(term) == "B$ B$ L# L$ v# B. SB%,,/ S}Q/2,$_ IK"


def test_pp_term_unknown_type_raises():
    class NotATerm:
        pass

    try:
        pp_term(NotATerm())  # type: ignore[arg-type]
        raise AssertionError("expected TypeError for unknown term type")
    except TypeError:
        pass


# ---------------------------------------------------------------------------
# Runner -- no pytest required
# ---------------------------------------------------------------------------

def run_all() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]

    passed, failed = 0, 0
    failures: list[tuple[str, str]] = []

    print(f"Running {len(tests)} tests for printer.py\n" + "-" * 60)
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
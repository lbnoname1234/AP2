"""
Standalone test script for main.py (CLI entry point).

Run directly:

    python3 main_test.py

(Also pytest-compatible: `pytest main_test.py -v` works too.)

Place this file in the same directory as ifp_ast.py, parser.py, printer.py,
interpreter.py, and main.py.
"""

from __future__ import annotations

import io
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import traceback
from contextlib import redirect_stdout, redirect_stderr

from ifp_ast import TBool, TInt, TLam, TString, TVar
from main import cmd_eval, main, _render_value


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def capture_cmd_eval(program: str, check_max: bool = True):
    """Run cmd_eval, capturing stdout/stderr and the exit code."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        exit_code = cmd_eval(program, check_max=check_max)
    return exit_code, out.getvalue(), err.getvalue()


def capture_main(stdin_text: str):
    """Run main(), feeding it stdin_text, capturing stdout/stderr/exit code."""
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin_text)
    try:
        with redirect_stdout(out), redirect_stderr(err):
            exit_code = main()
    finally:
        sys.stdin = old_stdin
    return exit_code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# _render_value
# ---------------------------------------------------------------------------

def test_render_value_int():
    assert _render_value(TInt(42)) == "42"


def test_render_value_negative_int():
    assert _render_value(TInt(-3)) == "-3"


def test_render_value_bool_true():
    assert _render_value(TBool(True)) == "true"


def test_render_value_bool_false():
    assert _render_value(TBool(False)) == "false"


def test_render_value_string():
    assert _render_value(TString("Hello World!")) == "Hello World!"


def test_render_value_falls_back_to_pp_term_for_other_terms():
    # A term that's neither TInt/TBool/TString (e.g. a lambda) should be
    # rendered via pp_term instead of crashing.
    result = _render_value(TLam(0, TVar(0)))
    assert result == "L! v!"


# ---------------------------------------------------------------------------
# cmd_eval -- success paths
# ---------------------------------------------------------------------------

def test_cmd_eval_success_int_result():
    code, out, err = capture_cmd_eval("B+ I# I$")
    assert code == 0
    assert err == ""
    assert "Result (human): 5" in out
    assert "Result (encoded term): I&" in out
    assert "Steps: 0" in out


def test_cmd_eval_success_bool_result():
    code, out, err = capture_cmd_eval("U! T")
    assert code == 0
    assert "Result (human): false" in out


def test_cmd_eval_success_string_result():
    code, out, err = capture_cmd_eval("B. S4% S34")
    assert code == 0
    assert "Result (human): test" in out


def test_cmd_eval_reports_step_count():
    program = "B$ B$ L# L$ v# B. SB%,,/ S}Q/2,$_ IK"
    code, out, err = capture_cmd_eval(program)
    assert code == 0
    assert "Steps: 2" in out


# ---------------------------------------------------------------------------
# cmd_eval -- error paths
# ---------------------------------------------------------------------------

def test_cmd_eval_parse_error_returns_exit_code_2():
    code, out, err = capture_cmd_eval("Z!")
    assert code == 2
    assert "Parse error:" in err
    assert out == ""


def test_cmd_eval_empty_input_returns_exit_code_2():
    code, out, err = capture_cmd_eval("")
    assert code == 2
    assert "Parse error:" in err


def test_cmd_eval_interpreter_error_returns_exit_code_3():
    # division by zero -> ArithmeticError_, a subclass of InterpreterError
    code, out, err = capture_cmd_eval("B/ I$ I!")
    assert code == 3
    assert "Interpreter error:" in err
    assert out == ""


def test_cmd_eval_scope_error_returns_exit_code_3():
    code, out, err = capture_cmd_eval("v!")
    assert code == 3
    assert "Interpreter error:" in err


def test_cmd_eval_beta_reduction_limit_returns_exit_code_3():
    import interpreter as interpreter_module

    original_max_steps = interpreter_module.MAX_STEPS
    interpreter_module.MAX_STEPS = 20
    try:
        code, out, err = capture_cmd_eval(
            "B$ L! B$ v! v! L! B$ v! v!", check_max=True
        )
        assert code == 3
        assert "Interpreter error:" in err
    finally:
        interpreter_module.MAX_STEPS = original_max_steps


# ---------------------------------------------------------------------------
# main() -- stdin handling
# ---------------------------------------------------------------------------

def test_main_reads_program_from_stdin_and_succeeds():
    code, out, err = capture_main("T\n")
    assert code == 0
    assert "Enter encoded phrase to evaluate:" in out
    assert "Result (human): true" in out


def test_main_strips_surrounding_whitespace():
    code, out, err = capture_main("   T   \n")
    assert code == 0
    assert "Result (human): true" in out


def test_main_empty_line_returns_exit_code_1():
    code, out, err = capture_main("\n")
    assert code == 1
    assert "No input program provided." in err


def test_main_eof_with_no_input_returns_exit_code_1():
    code, out, err = capture_main("")
    assert code == 1
    assert "No input program provided." in err


def test_main_propagates_parse_error_exit_code():
    code, out, err = capture_main("Z!\n")
    assert code == 2
    assert "Parse error:" in err


# ---------------------------------------------------------------------------
# Runner -- no pytest required
# ---------------------------------------------------------------------------

def run_all() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]

    passed, failed = 0, 0
    failures: list[tuple[str, str]] = []

    print(f"Running {len(tests)} tests for main.py\n" + "-" * 60)
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
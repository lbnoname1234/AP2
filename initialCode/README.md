# IFP — Interstellar Functional Program Interpreter

This folder contains a standalone implementation of **IFP (Interstellar Functional Program)**: a tiny
lambda calculus whose surface syntax is a sequence of space-separated tokens
encoded in base-94. The implementation includes a parser, evaluator, printer,
and a full test suite, plus several real correctness bugs that were found and
fixed during development (see [Key design decisions](#key-design-decisions--things-that-broke)
below).

```
Enter encoded phrase to evaluate:
B$ B$ L# L$ v# B. SB%,,/ S}Q/2,$_ IK
Result (human): Hello World!
Result (encoded term): SB%,,/}Q/2,$_
Steps: 2
```

## Contents

- [Quick start](#quick-start)
- [Project structure](#project-structure)
- [Pipeline](#pipeline)
- [How IFP encoding/decoding works](#how-ifp-encodingdecoding-works)
- [File-by-file guide](#file-by-file-guide)
- [Running the tests](#running-the-tests)
- [Key design decisions & things that broke](#key-design-decisions--things-that-broke)
- [Known limitations](#known-limitations)
- [FAQ](#faq)

## Quick start

Requires Python 3.10+ (no third-party dependencies for the interpreter
itself; `pytest` is optional — every test file also runs standalone).

```bash
python main.py
```

Paste an encoded IFP program at the prompt and press Enter, for example:

```
B$ B$ L# L$ v# B. SB%,,/ S}Q/2,$_ IK
```

which should print `Hello World!` (see the
[worked example](#putting-it-together-one-full-worked-example) below for
how that string decodes token by token).

## Project structure

```
.
├── ifp_ast.py           # AST node definitions (Term subclasses)
├── parser.py            # tokenizer + recursive-descent parser -> AST
├── printer.py            # AST -> encoded token string, base-94 helpers
├── interpreter.py         # AST -> value (call-by-name evaluator)
├── main.py                # CLI entry point
├── test/
│   ├── parser_test.py          # standalone test suite (34 checks)
│   ├── printer_test.py          # standalone test suite (25 checks)
│   ├── interpreter_test.py       # standalone test suite (45 checks)
│   └── main_test.py                # standalone test suite (20 checks)
```

Every `*_test.py` file runs two ways:

```bash
python test/parser_test.py          # standalone, no dependencies, prints PASS/FAIL per check
pytest test/parser_test.py -v       # also works if you have pytest installed
```

## Pipeline

1. `main.py` reads one line of encoded text from stdin.
2. `parser.py` tokenizes it and builds an AST out of the node types in
   `ifp_ast.py`.
3. `interpreter.py` evaluates that AST to a value, using a **call-by-name**
   strategy (arguments are not evaluated until they're actually needed).
4. `printer.py` renders the resulting value both as a human-readable string
   and back into IFP's own encoded token format.

## How IFP encoding/decoding works

This is the part that trips people up first, so it gets its own section.
An IFP program is **one line of space-separated tokens**. Every token is
made only of printable ASCII characters `!` (code 33) through `~` (code 126) — 94 possible characters, which is where "base-94" comes from. Every
token splits into exactly two parts:

```
indicator  body
   ↓        ↓
   I       /6
```

- **Indicator** — the first character. It tells you _what kind_ of token
  this is (integer, string, boolean, operator, ...).
- **Body** — everything after the indicator (possibly empty). What it
  means depends entirely on the indicator.

That's the whole grammar. There's no separate tokenizer/lexer step
beyond splitting on whitespace — `parser.py`'s `p_term` reads one token,
looks at its indicator, and immediately knows how many more tokens (if
any) it needs to consume next to finish parsing this expression.

### Indicator reference

| Indicator | Meaning                  | Body                     | Followed by                      |
| --------- | ------------------------ | ------------------------ | -------------------------------- |
| `T` / `F` | boolean `true` / `false` | empty                    | nothing                          |
| `I`       | integer                  | base-94 digits (§below)  | nothing                          |
| `S`       | string                   | string alphabet (§below) | nothing                          |
| `v`       | variable reference       | base-94 var id           | nothing                          |
| `L`       | lambda (`\x -> ...`)     | base-94 var id           | 1 expression (the body)          |
| `U`       | unary operator           | 1 char, the operator     | 1 expression (the operand)       |
| `B`       | binary operator          | 1 char, the operator     | 2 expressions (left, right)      |
| `?`       | conditional              | empty                    | 3 expressions (cond, then, else) |

### Decoding integers: base-94

An integer's body is a base-94 number, most-significant digit first. Each
character's digit value is just its position in the printable-ASCII
range: `!` → 0, `"` → 1, `#` → 2, ... `~` → 93 (i.e. `ord(ch) - 33`).
Decode it exactly like decoding any positional number system, just with
base 94 instead of base 10:

```
I/6
   body = "/6"
   '/' → ord('/') - 33 = 47 - 33 = 14
   '6' → ord('6') - 33 = 54 - 33 = 21
   value = 14 * 94 + 21 = 1337
```

This matches the spec's own example (`I/6` → `1337`) exactly. Encoding
(`to_base94` in `printer.py`) is the same process in reverse: repeated
`divmod` by 94, collecting remainders from least-significant digit up,
then reversing.

### Decoding strings: a _different_ alphabet

Strings use their own ordered alphabet — **not** the base-94 digit
values — mapped position-for-position onto the same 94 printable
characters:

```
abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789
!"#$%&'()*+,-./:;<=>?@[\]^_`|~<space><newline>
```

The first character of this alphabet (`a`) lines up with the first
printable ASCII character (`!`), the second (`b`) with `"`, and so on.
So decoding a string body means: for each character in the body, find
its position in the 94-character printable range, then look up the
character at that same position in the alphabet above.

```
S B % , , /
  'B' is the 34th printable char (index 33)  -> alphabet[33] = 'H'
  '%' is the 5th printable char  (index 4)    -> alphabet[4]  = 'e'
  ',' is the 12th printable char (index 11)   -> alphabet[11] = 'l'
  ',' → 'l'
  '/' is the 15th printable char (index 14)   -> alphabet[14] = 'o'

  "B%,,/" decodes to "Hello"
```

This is exactly what `ifp_ast.CHARS_DECODED` is: the alphabet string
above, built once and shared by both `parser.py` (decode direction) and
`printer.py` (encode direction), so the two can't accidentally drift out
of sync with each other.

Two consequences worth knowing about, both covered by
`printer_test.py`/`interpreter_test.py`:

- `{` and `}` are deliberately excluded from the string alphabet
  (reserved), so they can't appear inside an encoded string body.
- Since `a` (the first alphabet character) maps to base-94 **digit 0**,
  a string that _starts_ with `a` loses that leading digit if you
  convert it to an integer (`U#`) and back to a string (`U$`) — the same
  reason `int("007")` printed back gives `"7"`. This is a property of
  the format, not a bug (see [Known limitations](#known-limitations)).

### Decoding operators, variables, and lambdas

- **`U`/`B` (unary/binary operators):** the body is _always exactly one
  character_ — the operator symbol itself (`-`, `!`, `#`, `$`, `+`, `.`,
  `T`, `D`, ...). It's followed by one expression (`U`) or two (`B`) in
  the token stream, which is why the parser needs to _recursively_ parse
  more tokens right after reading a `U`/`B` token — the operator's
  operands aren't self-contained, they're just "whatever comes next".
- **`v` (variable) / `L` (lambda):** the body is a base-94 number, decoded
  exactly like an integer body, but it's used as a **variable id**, not a
  value. `L`'s token is additionally followed by one expression — its
  body.
- **`?` (conditional):** empty body, followed by exactly three
  expressions in sequence: condition, then-branch, else-branch.

### Putting it together: one full worked example

The spec's own function-application example, read left to right, one
token at a time:

```
B$ B$ L# L$ v# B. SB%,,/ S}Q/2,$_ IK
```

| Token      | Indicator   | Decoded meaning                                              |
| ---------- | ----------- | ------------------------------------------------------------ |
| `B$`       | `B`, op=`$` | binary op "apply function to argument", needs 2 exprs next   |
| `B$`       | `B`, op=`$` | (nested) another application, needs 2 exprs next             |
| `L#`       | `L`, var=2  | lambda binding variable `v2`, needs 1 expr (its body) next   |
| `L$`       | `L`, var=3  | (nested) lambda binding `v3`, needs 1 expr next              |
| `v#`       | `v`, id=2   | reference to variable `v2` — this is the inner lambda's body |
| `B.`       | `B`, op=`.` | string concatenation, needs 2 exprs next                     |
| `SB%,,/`   | `S`         | decodes to `"Hello"`                                         |
| `S}Q/2,$_` | `S`         | decodes to `" World!"`                                       |
| `IK`       | `I`         | decodes to `42`                                              |

Reassembling the tree from the indentation of "needs N exprs next"
above gives exactly:

```
((\v2 -> \v3 -> v2) ("Hello" . " World!")) 42
```

which evaluates to `"Hello World!"` — matching the spec's example and
`interpreter_test.py`'s `test_spec_hello_world_application`.

## File-by-file guide

### `ifp_ast.py`

Defines the AST node types as frozen dataclasses: `TInt`, `TString`,
`TBool`, `TVar`, `TLam`, `TUnOp`, `TBinOp`, `TIf`. Also defines the two
shared character tables (`CHARS`, the 94 printable ASCII symbols; and
`CHARS_DECODED`, the human-readable alphabet used for string literals)
that both `parser.py` and `printer.py` build their encode/decode maps
from — kept in one place so the two directions of the mapping can't
silently drift apart.

### `parser.py`

Tokenizes on whitespace, then a recursive-descent parser (`p_term`) walks
the tokens and builds the AST directly — no separate lexer pass. Reports
three kinds of `ParseError` (`UnexpectedChar`, `UnusedInput`,
`UnexpectedEOF`) with the exact character index of the problem, mirroring
what a hand-rolled parser generator would give you.

### `printer.py`

The inverse direction: base-94 encoding (`to_base94`), string-literal
encoding (`encode_string`), and `pp_term` to serialize an AST node back
into IFP's token syntax. Note that `to_base94` returns `None` for negative
numbers — IFP's `I` token can't represent them directly, so negative
integers get printed as a `U-` (negation) node wrapping the positive
value instead. `pp_term` handles that fallback automatically.

### `interpreter.py`

The evaluator. Uses an **environment of `(variable id) -> Thunk`**
mappings rather than literal AST substitution — this is what makes
variable-capture avoidance basically free (see below). Deliberately
**does not memoize** thunks; see
[Key design decisions](#key-design-decisions--things-that-broke) for why.
Exposes `InterpreterError` and five subclasses (`BetaReductionLimit`,
`ScopeError`, `TypeError_`, `ArithmeticError_`, `UnknownUnOp`/`UnknownBinOp`)
so callers can distinguish failure kinds.

### `main.py`

Thin CLI wrapper: reads a line, calls `parser.p_term` then
`interpreter.interpret`, and prints the human-readable result, the
re-encoded result, and the beta-reduction step count. Exit codes:
`0` success, `2` parse error, `3` interpreter error.

## Running the tests

```bash
python test/parser_test.py
python test/printer_test.py
python test/interpreter_test.py
python test/main_test.py
```

124 checks total (34 + 25 + 45 + 20), all passing. No test file requires
`pytest` to run, though all of them are pytest-compatible if you'd rather
use that.

A few of the interpreter tests are worth calling out because they test
_properties_, not just examples:

- The exact worked example from the spec (a self-application recursion
  that must evaluate to `16` in **exactly 109** beta-reduction steps) is
  run as a literal regression test — this is what pinned down the
  non-memoization decision below.
- A conditional branch that would raise a division-by-zero error if
  evaluated is deliberately placed on the _unselected_ side of an `if`,
  to prove the interpreter never touches it.
- A closure is captured once and applied twice within the same
  evaluation (`twice = \f -> \x -> f (f x)`), to catch any accidental
  shared-mutable-state bug between the two applications.

## Key design decisions & things that broke

These were the non-obvious parts — the kind of thing worth mentioning if
you're explaining this project to someone else.

**Environments instead of literal substitution.** Rather than literally
replacing a variable with its argument expression inside the AST (which
needs alpha-renaming to avoid variable capture), each `VClosure` just
carries the environment it was created in, and application extends a
_copy_ of that environment with one new binding. A variable is always
looked up in the environment it was actually bound in, so capture simply
can't happen — no renaming logic needed.

**Call-by-name must NOT be memoized, or the step count is wrong.** The
spec includes one worked example with an exact expected result (`16`)
and step count (`109`). Implementing environment-based evaluation with a
memoizing `Thunk` (cache the value the first time a variable is forced,
reuse it after) gives the right _result_ but only **57** steps — because
sharing a computed value avoids re-doing beta reductions that occur
inside it. Removing the cache and re-evaluating a variable's bound
expression from scratch every time it's referenced reproduces the exact 109. This is the textbook difference between call-by-name (no sharing)
and call-by-need (sharing) — the spec calls for the former, even though
it's the less efficient of the two.

**Non-memoized call-by-name can stack-overflow well before 10,000,000
steps.** A straightforward recursive tree-walking `eval_term` blew
Python's default recursion limit (1000 frames) on a self-application
countdown recursing only ~1,500 levels deep — nowhere near the spec's
step ceiling. Two fixes were needed:

1. **Trampolining** the genuinely tail-recursive cases (application,
   `if`-branch selection, variable dereference) into an explicit `while`
   loop, so those don't grow the call stack at all.
2. Running evaluation on a **worker thread with a raised recursion limit
   and a larger stack** (512 MB) for the cases that are _not_ tail
   position — because without memoization, forcing a variable that's
   been "aged" through many recursive calls means evaluating a long
   chain of nested arithmetic (e.g. `((...((n-1)-1)...)-1)`), and that's
   inherently non-tail-recursive.

This raises the crash threshold a lot, but doesn't remove an inherent
cost: forcing that chain from scratch, every time, means deep linear
recursion costs **O(depth²)** time, not O(depth). That's a genuine
property of non-memoized call-by-name (part of why call-by-need exists
as an alternative), not a bug — see
[Known limitations](#known-limitations).

**Two "roundtrip" test assumptions turned out to be wrong, not the code.**
While writing tests, `roundtrip(TInt(-3)) == TInt(-3)` and
`roundtrip(TString("abc123")) == TString("abc123")` (round-tripping
through `pp_term` then `p_term`, or through `U#` then `U$`) both failed —
correctly. Negative integers have no direct token representation (`I`
bodies are base-94 digits, which are non-negative), so `pp_term` encodes
them as a `U-` negation node instead; parsing that back correctly yields
a `TUnOp` node, not a `TInt`. Similarly, any string starting with `'a'`
(the character mapped to base-94 digit 0) loses that leading digit when
round-tripped through an integer, the same way `int("007")` printed back
gives `"7"`. Both are documented in the test files rather than "fixed",
since the original assumption — not the implementation — was the bug.

## Known limitations

- **O(depth²) time for deep, non-memoized linear recursion.** A
  self-application countdown recursing a few thousand levels deep is
  noticeably slow (single-digit seconds); tens of thousands of levels is
  impractical. This is inherent to matching the spec's exact
  (non-memoized) step counts, not something the thread/stack fix
  addresses.
- **`U#`/`U$` (string ⇄ integer) are not true inverses for all strings** —
  see the leading-zero-digit case above. This matches the spec's
  definition of the two operators; it's not something to "fix".

## FAQ

1. **What is an AST?**
   Search for "Abstract Syntax Tree" — it's a foundational concept in
   parsing and compiler/interpreter design, worth understanding
   independent of this project.

2. **I haven't studied Principles of Programming Languages — can I still
   work through this?**
   Yes. Concepts from Fundamental Programming and Data Structures &
   Algorithms are enough to get started; budget extra time for parsing,
   ASTs, and interpreter design if they're new to you.

3. **Why does the interpreter run evaluation in a separate thread?**
   See [Key design decisions](#key-design-decisions--things-that-broke) —
   short version: Python's default call stack is too small for deep
   recursive IFP programs, and non-memoized call-by-name (required to
   match the spec's exact step counts) can't avoid that recursion in
   general.

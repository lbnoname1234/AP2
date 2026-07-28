# IFP Playground Project

This workspace contains a small browser-based playground for the Interstellar Functional Program (IFP) language, along with the reference Python implementation used to power the parser, interpreter, and printer logic.

## Project Structure

- [initialCode](initialCode/) — Python reference implementation and tests
  - [initialCode/ifp_ast.py](initialCode/ifp_ast.py)
  - [initialCode/parser.py](initialCode/parser.py)
  - [initialCode/interpreter.py](initialCode/interpreter.py)
  - [initialCode/printer.py](initialCode/printer.py)
  - [initialCode/test](initialCode/test/)
- [playground](playground/) — browser-based IFP playground UI
  - [playground/ifp_playground.html](playground/ifp_playground.html)
  - [playground/ifp_core.js](playground/ifp_core.js)
  - [playground/ifp_examples.js](playground/ifp_examples.js)
- [playgr_design](playgr_design/) — styling for the playground
  - [playgr_design/playground.css](playgr_design/playground.css)

## What this project does

The project lets you enter encoded IFP programs, parse them, evaluate them using a call-by-name interpreter, and view the resulting AST and reduction steps. The browser version mirrors the behavior of the reference Python implementation.

## How to use it

1. Open [playground/ifp_playground.html](playground/ifp_playground.html) in a browser.
2. Enter an IFP program in the input box or choose one of the example programs.
3. Click Run to parse and evaluate the program.

## Python reference implementation

The Python files in [initialCode](initialCode/) provide the core language model and evaluator logic. You can run the tests in that folder with:

```bash
pytest
```

## Notes

- The browser version uses JavaScript and is designed to be lightweight and self-contained.
- The project is intended as a learning and demonstration environment for functional language parsing and evaluation.

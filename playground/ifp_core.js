// IFP core: tokenizer, parser, interpreter, printer -- ported from the
// Python reference implementation (ifp_ast.py / parser.py / interpreter.py
// / printer.py). Uses BigInt throughout for arbitrary-precision integers.

// ---------------------------------------------------------------------
// Shared alphabet (mirrors ifp_ast.py)
// ---------------------------------------------------------------------

function buildCharsDecoded() {
  const lower = "abcdefghijklmnopqrstuvwxyz";
  const upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const digits = "0123456789";
  let chars = "";
  for (let i = 33; i < 127; i++) chars += String.fromCharCode(i);
  const charsNoBraces = Array.from(chars)
    .filter((c) => c !== "{" && c !== "}")
    .join("");
  const raw = lower + upper + digits + charsNoBraces + " \n";
  const seen = new Set();
  let out = "";
  for (const ch of raw) {
    if (!seen.has(ch)) {
      seen.add(ch);
      out += ch;
    }
  }
  return out;
}

let CHARS = "";
for (let i = 33; i < 127; i++) CHARS += String.fromCharCode(i);
const CHARS_DECODED = buildCharsDecoded();

const DECODE_MAP = {}; // encoded token char -> human char
const ENCODE_MAP = {}; // human char -> encoded token char
for (let i = 0; i < CHARS.length; i++) {
  DECODE_MAP[CHARS[i]] = CHARS_DECODED[i];
  ENCODE_MAP[CHARS_DECODED[i]] = CHARS[i];
}

// ---------------------------------------------------------------------
// Printer (mirrors printer.py)
// ---------------------------------------------------------------------

function toBase94(x) {
  // x: BigInt. Returns string or null if negative.
  if (x < 0n) return null;
  if (x === 0n) return String.fromCharCode(33);
  let out = [];
  let n = x;
  while (n > 0n) {
    const m = n % 94n;
    n = n / 94n;
    out.push(String.fromCharCode(Number(m) + 33));
  }
  out.reverse();
  return out.join("");
}

function encodeString(s) {
  let out = "";
  for (const ch of s) {
    if (!(ch in ENCODE_MAP)) {
      throw new Error(
        `Unexpected character in string encoding: ${JSON.stringify(ch)}`,
      );
    }
    out += ENCODE_MAP[ch];
  }
  return out;
}

function decodeStringBody(body) {
  let out = "";
  for (const ch of body) out += DECODE_MAP[ch];
  return out;
}

function ppTerm(term) {
  switch (term.kind) {
    case "Int": {
      const b94 = toBase94(term.value);
      if (b94 !== null) return "I" + b94;
      return ppTerm({
        kind: "UnOp",
        op: "-",
        term: { kind: "Int", value: -term.value },
      });
    }
    case "String":
      return "S" + encodeString(term.value);
    case "Bool":
      return term.value ? "T" : "F";
    case "Var": {
      const b94 = toBase94(BigInt(term.value));
      if (b94 === null) throw new Error("Negative variable found");
      return "v" + b94;
    }
    case "Lam": {
      const b94 = toBase94(BigInt(term.var));
      if (b94 === null) throw new Error("Negative variable found");
      return "L" + b94 + " " + ppTerm(term.body);
    }
    case "UnOp":
      return "U" + term.op + " " + ppTerm(term.term);
    case "BinOp":
      return "B" + term.op + " " + ppTerm(term.left) + " " + ppTerm(term.right);
    case "If":
      return (
        "? " +
        ppTerm(term.cond) +
        " " +
        ppTerm(term.true_branch) +
        " " +
        ppTerm(term.false_branch)
      );
    default:
      throw new Error(`Unknown term kind: ${term.kind}`);
  }
}

// ---------------------------------------------------------------------
// Parser (mirrors parser.py)
// ---------------------------------------------------------------------

class ParseError extends Error {
  constructor(kind, index = null, ch = null) {
    let msg;
    if (kind === "UnexpectedChar")
      msg = `UnexpectedChar(${JSON.stringify(ch)}, ${index})`;
    else if (kind === "UnusedInput") msg = `UnusedInput(${index})`;
    else msg = "UnexpectedEOF";
    super(msg);
    this.name = "ParseError";
    this.kind = kind;
    this.index = index;
    this.ch = ch;
  }
}

function tokenize(input) {
  const tokens = [];
  const re = /\S+/g;
  let m;
  while ((m = re.exec(input)) !== null) {
    tokens.push([m[0], m.index]);
  }
  return tokens;
}

function decodeBase94(body, bodyStart) {
  if (body.length === 0) throw new ParseError("UnexpectedEOF");
  let value = 0n;
  for (let offset = 0; offset < body.length; offset++) {
    const ch = body[offset];
    const digit = ch.charCodeAt(0) - 33;
    if (digit < 0 || digit > 93) {
      throw new ParseError("UnexpectedChar", bodyStart + offset, ch);
    }
    value = value * 94n + BigInt(digit);
  }
  return value;
}

function decodeStringToken(body, bodyStart) {
  let out = "";
  for (let offset = 0; offset < body.length; offset++) {
    const ch = body[offset];
    if (!(ch in DECODE_MAP))
      throw new ParseError("UnexpectedChar", bodyStart + offset, ch);
    out += DECODE_MAP[ch];
  }
  return out;
}

class Parser {
  constructor(tokens) {
    this.tokens = tokens;
    this.pos = 0;
  }
  peek() {
    if (this.pos >= this.tokens.length)
      throw new ParseError("UnexpectedEOF");
    return this.tokens[this.pos];
  }
  advance() {
    const tok = this.peek();
    this.pos += 1;
    return tok;
  }
  requireEmptyBody(body, bodyStart) {
    if (body.length > 0)
      throw new ParseError("UnexpectedChar", bodyStart, body[0]);
  }
  requireSingleCharOp(body, bodyStart) {
    if (body.length === 0) throw new ParseError("UnexpectedEOF");
    if (body.length > 1)
      throw new ParseError("UnexpectedChar", bodyStart + 1, body[1]);
    return body;
  }
  parseTerm() {
    const [text, start] = this.advance();
    const indicator = text[0];
    const body = text.slice(1);
    const bodyStart = start + 1;

    if (indicator === "T") {
      this.requireEmptyBody(body, bodyStart);
      return { kind: "Bool", value: true };
    }
    if (indicator === "F") {
      this.requireEmptyBody(body, bodyStart);
      return { kind: "Bool", value: false };
    }
    if (indicator === "I") {
      return { kind: "Int", value: decodeBase94(body, bodyStart) };
    }
    if (indicator === "S") {
      return {
        kind: "String",
        value: decodeStringToken(body, bodyStart),
      };
    }
    if (indicator === "v") {
      return {
        kind: "Var",
        value: Number(decodeBase94(body, bodyStart)),
      };
    }
    if (indicator === "L") {
      const varId = Number(decodeBase94(body, bodyStart));
      const inner = this.parseTerm();
      return { kind: "Lam", var: varId, body: inner };
    }
    if (indicator === "U") {
      const op = this.requireSingleCharOp(body, bodyStart);
      const operand = this.parseTerm();
      return { kind: "UnOp", op, term: operand };
    }
    if (indicator === "B") {
      const op = this.requireSingleCharOp(body, bodyStart);
      const left = this.parseTerm();
      const right = this.parseTerm();
      return { kind: "BinOp", left, op, right };
    }
    if (indicator === "?") {
      this.requireEmptyBody(body, bodyStart);
      const cond = this.parseTerm();
      const trueBranch = this.parseTerm();
      const falseBranch = this.parseTerm();
      return {
        kind: "If",
        cond,
        true_branch: trueBranch,
        false_branch: falseBranch,
      };
    }
    throw new ParseError("UnexpectedChar", start, indicator);
  }
}

function pTerm(input) {
  const tokens = tokenize(input);
  if (tokens.length === 0) throw new ParseError("UnexpectedEOF");
  const parser = new Parser(tokens);
  const term = parser.parseTerm();
  if (parser.pos < parser.tokens.length) {
    const [, idx] = parser.tokens[parser.pos];
    throw new ParseError("UnusedInput", idx);
  }
  return term;
}

// ---------------------------------------------------------------------
// Interpreter (mirrors interpreter.py) -- plain call-by-name, NOT memoized
// (verified against spec section 3.10: memoizing gives 57 steps instead
// of the spec's documented 109 for the worked recursive example).
// ---------------------------------------------------------------------

class InterpreterError extends Error {
  constructor(message) {
    super(message);
    this.name = "InterpreterError";
  }
}
class BetaReductionLimit extends InterpreterError {}
class ScopeError extends InterpreterError {}
class TypeError_ extends InterpreterError {}
class ArithmeticError_ extends InterpreterError {}
class UnknownUnOp extends InterpreterError {
  constructor(op) {
    super(`Unknown unary operator: ${op}`);
    this.op = op;
  }
}
class UnknownBinOp extends InterpreterError {
  constructor(op) {
    super(`Unknown binary operator: ${op}`);
    this.op = op;
  }
}

const MAX_STEPS_DEFAULT = 10_000_000;

function toTerm(v) {
  if (v.kind === "VInt") return { kind: "Int", value: v.value };
  if (v.kind === "VBool") return { kind: "Bool", value: v.value };
  if (v.kind === "VString") return { kind: "String", value: v.value };
  if (v.kind === "VClosure")
    return { kind: "Lam", var: v.var, body: v.body };
  throw new Error(`Unknown value kind: ${v.kind}`);
}

function stringBodyToInt(body) {
  let value = 0n;
  for (const ch of body)
    value = value * 94n + BigInt(ch.charCodeAt(0) - 33);
  return value;
}

function intToStringBody(n) {
  const b94 = toBase94(n);
  if (b94 === null)
    throw new TypeError_("Cannot convert a negative integer to a string");
  return b94;
}

function requireInts(a, b, op) {
  if (a.kind !== "VInt" || b.kind !== "VInt")
    throw new TypeError_(`Operator '${op}' requires integer operands`);
}
function requireBools(a, b, op) {
  if (a.kind !== "VBool" || b.kind !== "VBool")
    throw new TypeError_(`Operator '${op}' requires boolean operands`);
}
function requireStrings(a, b, op) {
  if (a.kind !== "VString" || b.kind !== "VString")
    throw new TypeError_(`Operator '${op}' requires string operands`);
}
function valuesEqual(a, b) {
  if (a.kind === "VInt" && b.kind === "VInt") return a.value === b.value;
  if (a.kind === "VBool" && b.kind === "VBool")
    return a.value === b.value;
  if (a.kind === "VString" && b.kind === "VString")
    return a.value === b.value;
  throw new TypeError_(
    "Operator '=' requires both operands to be of the same type",
  );
}

function evalUnOp(op, operand) {
  if (op === "-") {
    if (operand.kind !== "VInt")
      throw new TypeError_("Unary '-' requires an integer operand");
    return { kind: "VInt", value: -operand.value };
  }
  if (op === "!") {
    if (operand.kind !== "VBool")
      throw new TypeError_("Unary '!' requires a boolean operand");
    return { kind: "VBool", value: !operand.value };
  }
  if (op === "#") {
    if (operand.kind !== "VString")
      throw new TypeError_("Unary '#' requires a string operand");
    const encoded = encodeString(operand.value);
    return { kind: "VInt", value: stringBodyToInt(encoded) };
  }
  if (op === "$") {
    if (operand.kind !== "VInt")
      throw new TypeError_("Unary '$' requires an integer operand");
    const body = intToStringBody(operand.value);
    return { kind: "VString", value: decodeStringBody(body) };
  }
  throw new UnknownUnOp(op);
}

function evalBinOp(op, left, right) {
  if (op === "+") {
    requireInts(left, right, op);
    return { kind: "VInt", value: left.value + right.value };
  }
  if (op === "-") {
    requireInts(left, right, op);
    return { kind: "VInt", value: left.value - right.value };
  }
  if (op === "*") {
    requireInts(left, right, op);
    return { kind: "VInt", value: left.value * right.value };
  }
  if (op === "/") {
    requireInts(left, right, op);
    if (right.value === 0n)
      throw new ArithmeticError_("Division by zero");
    return { kind: "VInt", value: left.value / right.value }; // BigInt truncates toward zero
  }
  if (op === "%") {
    requireInts(left, right, op);
    if (right.value === 0n) throw new ArithmeticError_("Modulo by zero");
    return { kind: "VInt", value: left.value % right.value }; // BigInt remainder follows dividend sign
  }
  if (op === "<") {
    requireInts(left, right, op);
    return { kind: "VBool", value: left.value < right.value };
  }
  if (op === ">") {
    requireInts(left, right, op);
    return { kind: "VBool", value: left.value > right.value };
  }
  if (op === "=")
    return { kind: "VBool", value: valuesEqual(left, right) };
  if (op === "|") {
    requireBools(left, right, op);
    return { kind: "VBool", value: left.value || right.value };
  }
  if (op === "&") {
    requireBools(left, right, op);
    return { kind: "VBool", value: left.value && right.value };
  }
  if (op === ".") {
    requireStrings(left, right, op);
    return { kind: "VString", value: left.value + right.value };
  }
  if (op === "T") {
    if (left.kind !== "VInt" || right.kind !== "VString")
      throw new TypeError_("Operator 'T' requires (int, string) operands");
    return {
      kind: "VString",
      value: right.value.slice(0, Number(left.value)),
    };
  }
  if (op === "D") {
    if (left.kind !== "VInt" || right.kind !== "VString")
      throw new TypeError_("Operator 'D' requires (int, string) operands");
    return {
      kind: "VString",
      value: right.value.slice(Number(left.value)),
    };
  }
  throw new UnknownBinOp(op);
}

function interpret(checkMax, term, maxSteps = MAX_STEPS_DEFAULT) {
  let steps = 0;

  function force(thunk) {
    // Intentionally NOT memoized -- see module comment above.
    return evalTerm(thunk.term, thunk.env);
  }

  function evalTerm(t, env) {
    switch (t.kind) {
      case "Int":
        return { kind: "VInt", value: t.value };
      case "Bool":
        return { kind: "VBool", value: t.value };
      case "String":
        return { kind: "VString", value: t.value };
      case "Var": {
        const thunk = env.get(t.value);
        if (thunk === undefined)
          throw new ScopeError(`Unbound variable: v${t.value}`);
        return force(thunk);
      }
      case "Lam":
        return { kind: "VClosure", var: t.var, body: t.body, env };
      case "UnOp":
        return evalUnOp(t.op, evalTerm(t.term, env));
      case "If": {
        const cond = evalTerm(t.cond, env);
        if (cond.kind !== "VBool")
          throw new TypeError_("Condition of '?' must be a boolean");
        return evalTerm(cond.value ? t.true_branch : t.false_branch, env);
      }
      case "BinOp": {
        if (t.op === "$") {
          steps += 1;
          if (checkMax && steps > maxSteps) {
            throw new BetaReductionLimit(
              `Exceeded maximum beta reduction steps (${maxSteps})`,
            );
          }
          const func = evalTerm(t.left, env);
          if (func.kind !== "VClosure")
            throw new TypeError_(
              "Left-hand side of function application ('$') must be a lambda",
            );
          const argThunk = { term: t.right, env };
          const newEnv = new Map(func.env);
          newEnv.set(func.var, argThunk);
          return evalTerm(func.body, newEnv);
        }
        const left = evalTerm(t.left, env);
        const right = evalTerm(t.right, env);
        return evalBinOp(t.op, left, right);
      }
      default:
        throw new Error(`Unknown term kind: ${t.kind}`);
    }
  }

  const result = evalTerm(term, new Map());
  return { result: toTerm(result), steps };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    toBase94,
    encodeString,
    decodeStringBody,
    ppTerm,
    pTerm,
    ParseError,
    interpret,
    InterpreterError,
    BetaReductionLimit,
    ScopeError,
    TypeError_,
    ArithmeticError_,
    UnknownUnOp,
    UnknownBinOp,
  };
}

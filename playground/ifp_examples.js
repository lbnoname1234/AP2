const EXAMPLES = [
  {
    label: "Hello World (application)",
    note: '((\\v2 -> \\v3 -> v2) ("Hello" . " World!")) 42',
    program: "B$ B$ L# L$ v# B. SB%,,/ S}Q/2,$_ IK",
  },
  {
    label: "Recursive doubling (109 steps)",
    note: "Self-application recursion. Spec says: result 16, exactly 109 beta-reduction steps.",
    program:
      'B$ B$ L" B$ L# B$ v" B$ v# v# L# B$ v" B$ v# v# L" L# ? B= v# I! I"\n' +
      'B$ L$ B+ B$ v" v$ B$ v" v$ B- v# I" I%',
  },
  {
    label: "Call-by-name (repeated variable)",
    note: 'v" is used twice; each occurrence re-evaluates its bound expression independently.',
    program: 'B$ L# B$ L" B+ v" v" B* I$ I# v8',
  },
  {
    label: "Truncating division",
    note: "-7 / 2 must truncate toward zero: -3, not -4 (floor division).",
    program: "B/ U- I( I#",
  },
  {
    label: "Conditional (lazy branch)",
    note: "Only the selected branch is evaluated; the other is never touched.",
    program: "? B> I# I$ S9%3 S./",
  },
  {
    label: "Infinite loop (hits step limit)",
    note: "The omega combinator: (\\x -> x x) (\\x -> x x). Never terminates -- demonstrates the reduction-step limit.",
    program: "B$ L! B$ v! v! L! B$ v! v!",
  },
  {
    label: "Type error demo",
    note: "Adding an integer and a boolean is a type error.",
    program: "B+ I$ T",
  },
];

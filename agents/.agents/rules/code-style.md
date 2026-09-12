# Code style

Done when every changed file satisfies the rules below.

- Initiate a refactor only when a new reader can understand the result without extra explanation. The result has fewer lines, or each added line names or separates a concept the code was hiding.
- Use concrete, repeated patterns. Introduce an abstraction only when it makes the meaning more visible than the repeated code.
- Prefer declarative over imperative: a stream, comprehension, or query states the result where a loop builds it step by step. Keep the loop when the stepping is the logic (early exit, index arithmetic, multiple accumulators).
- Let the code state `what`; add a one-line comment for every `why`, `trade-off`, or `caution` the code does not already show.

# Code Lens

Additional questions for the five lenses when the work involves code changes.

## Lens 1 Additions: Is This Real?

- Is this a bug or a misunderstanding of the API contract?
- Does the error message accurately describe the problem, or is it misleading?
- Is the "fix" already in place but behind a flag or config?

## Lens 2 Additions: What's Actually Going On?

- Is the error handling the problem, not the error itself?
- Is a race condition or timing issue masquerading as a logic bug?
- Is the test wrong rather than the code?

## Lens 3 Additions: What Else Can We Fix?

- Are exception handlers swallowing errors that should propagate?
- Is there dead code adjacent to the change that should be removed?
- Can we add types or validation to prevent this class of bug?
- Are there missing tests that would have caught this?

## Lens 4 Additions: Should We Rethink?

- Would a Result type replace scattered try/catch?
- Would dependency injection replace the tight coupling causing the bug?
- Would an event-driven approach replace the fragile sequential flow?

## Lens 5 Additions: Better Way?

- Can we use a library/stdlib function instead of custom code?
- Can we make the compiler/type system catch this automatically?
- Can we add a linter rule to prevent recurrence?

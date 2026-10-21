# Testing guide

Keep the maintained test suite small, reliable, and valuable. Tests should protect important behavior without becoming a maintenance burden.

## Experiment freely; retain selectively

Use temporary tests, scripts, and experiments as needed to understand and validate a change. Keep them outside the maintained suite until they demonstrate lasting value.

Retain or extend a test only when it protects:

- user-visible behavior, a public contract, or an important invariant;
- a meaningful edge case or plausible regression not already covered; and
- that value at a reasonable cost in runtime, complexity, and fragility.

A code change alone is not a reason to add a permanent test. For bug fixes, keep a regression test only when the failure could plausibly recur and is not already covered. Do not preserve a one-off reproduction solely because it helped diagnose the issue.

Before finalizing a change, review new tests and keep only those that provide distinct value. Remove only temporary artifacts you created; do not delete existing tests merely to reduce their number.

## Write high-value tests

- Test observable behavior at a stable boundary, such as outputs, persisted state, recovery behavior, or visible UI state.
- Avoid implementation-mirroring tests: private attributes, source text, incidental call order, or assertions that mainly verify mock setup.
- Prefer extending focused existing coverage over adding overlapping tests. Do not create files named for a review, issue, PR, or agent session.
- Use independent oracles. For numerical code, prefer small synthetic data with analytically known results; calling the same implementation twice is not a correctness check.
- Keep data and runtime minimal. Use only the dimensions, frames, and cases needed to expose distinct behavior.
- Justify floating-point or lossy-image tolerances. Never weaken an assertion just to make a failing test pass.
- For configuration, test the policy owner and verify that meaningful nondefault values, including `False` and `0`, survive persistence and forwarding. Assert exact defaults only when the default is an intended product contract.
- Use real small, deterministic collaborators. Substitute only expensive, nondeterministic, interactive, external, or unavailable boundaries.

## Keep tests isolated and deterministic

- Use temporary directories and redirect application state before constructing objects that may save. Never touch a user's projects, app settings, or recent-project history.
- Use local seeded random generators instead of global random state.
- Synchronize asynchronous work with signals, events, barriers, or bounded waits rather than fixed sleeps.
- Clean up workers, timers, threads, files, patches, and Qt widgets even when a test fails.
- Run Qt tests offscreen and use one `QApplication` per process. Native rendering, scaling, GPU, or platform integration changes may still require a short manual check.
- Keep ordinary tests independent of network access, model downloads, accelerator hardware, and large or user-provided fixtures. Clearly separate and explain any optional hardware, model, benchmark, or native UI checks.

## Organize and maintain the suite

- Put tests with the module or subsystem that owns the behavior.
- Put shared helpers in non-test support modules; never import one `test_*.py` module from another.
- Do not commit downloaded models, user images or projects, scratch implementations, or large generated outputs.
- When behavior changes intentionally, update tests to reflect the new contract. When a test is flaky or slow, fix the cause or reduce the case; do not hide it with retries, arbitrary sleeps, or blanket skips.
- Consolidate redundant coverage only when the distinct contracts remain protected. Test counts and coverage percentages are not goals in themselves.

## Report validation

Run the checks relevant to the change, then broaden only when the changed behavior or shared code warrants it. Report what was checked, what could not be run, and what any retained tests protect. If no permanent test is warranted, explain how the change was validated.
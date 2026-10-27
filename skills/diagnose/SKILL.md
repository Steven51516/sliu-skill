---
name: diagnose
description: Diagnosis loop for hard bugs in research code, broken runs, and results that look wrong (NaN, a metric that cannot be right, a leak, a crash, a slowdown). Use when the user says "diagnose" / "debug this", reports something broken, or before a fix is called done.
---

# Diagnose

Skip a phase only with a stated reason. Read the project's `GLOSSARY.md` (if any) for the names of the moving parts.

**Redact** every secret in commands and outputs you show: write `<REDACTED>`. Keep credentials in the environment.

## Phase 1: Build a feedback loop
**This is the skill.** With a **tight** pass/fail signal that goes **red** on *this* bug, the cause will be found;
without one, reading code will not find it. Spend disproportionate effort here.

Ways to build one, roughly in this order:
1. **Tiny-config run** of the real entry point (a few steps, a fixed batch, a fixed seed) that asserts the exact symptom:
   NaN at step k, loss above a bound, wrong row count, wrong shape, step time over a bound.
2. **Replay a captured input.** Save the offending row, batch, document or checkpoint to disk; push it alone through the
   code path.
3. **Differential loop.** The same input through two configs, two code versions or two checkpoints; diff the outputs.
4. **Invariant probe.** A check of a property that must hold: perturb document A and assert document B's states move by
   exactly 0; decode the native tokens and assert TM ≥ 0.99; assert every shard row is covered.
5. **Property loop.** Many random rows or seeds when the bug is "sometimes wrong"; raise the reproduction rate until it is
   debuggable (a 50% flake is debuggable, 1% is not).
6. **Bisection.** Between a known-good and a known-bad state (commit, data version, checkpoint), automate check-and-step.
7. **Throwaway harness.** The smallest subset of the system (one module, fake inputs) that reaches the bug with one call.

**Tighten** the loop: faster (cache setup, smaller config), sharper (assert the specific symptom, not "didn't crash"),
deterministic (pin seeds, data order, GPU count).

**Done when** you can name **one command**, already run at least once (show it and its output), that is:
- [ ] **red-capable**: drives the real code path and asserts the user's exact symptom;
- [ ] **deterministic**: same verdict every run (or a pinned, high reproduction rate);
- [ ] **fast**: seconds to a few minutes, on one GPU or the CPU;
- [ ] **agent-runnable** unattended.

If you catch yourself building a theory from code before this command exists, stop: that is the failure this skill
prevents. If no loop can be built, say so, list what you tried, and ask for access, a captured artifact, or permission to
add instrumentation.

## Phase 2: Reproduce and minimise
Run the loop and watch it go red. Confirm it is the failure the **user** described, not a nearby one, and capture the exact
symptom. Then cut inputs, config, data and steps **one at a time**, re-running after each cut, until every remaining element
is load-bearing.

## Phase 3: Hypothesise
Write **3–5 ranked, falsifiable hypotheses** before testing any: "If X is the cause, then changing Y makes the symptom
disappear / changing Z makes it worse." A hypothesis with no prediction is discarded or sharpened. Show the list to the user
before testing (they often re-rank it at once); proceed with your ranking if they are away.

## Phase 4: Instrument
Each probe maps to one prediction. **Change one variable at a time.** Prefer a REPL or debugger on the captured input, then
targeted logs at the boundaries that separate hypotheses, never "log everything and grep". Tag every debug line with a
unique prefix (`[DEBUG-a4f2]`) so cleanup is one grep. **Slowdowns:** measure a baseline first (step time, tokens/s, GPU
memory bandwidth), then bisect; logs rarely find them.

## Phase 5: Fix and lock it down
1. Keep the minimised loop as a **check script** (in the ticket folder, or `common/checks/` when shared code is at fault) and
   watch it go red before the fix.
2. Fix. Watch it go green.
3. Re-run the loop on the **original, un-minimised scenario on the production path**: the real launcher, real shards, real
   GPU count. A fix proven only in a unit-sized harness is not proven.
4. If no seam lets a check reach the real bug pattern, that is a finding: record it, and consider `improve-codebase-architecture`.

## Phase 6: Clean up and record
- [ ] the original scenario no longer reproduces
- [ ] the check script passes, and is named in the project's preflight list if the bug can recur
- [ ] all `[DEBUG-…]` lines removed (grep the prefix); throwaway harnesses deleted or clearly marked
- [ ] the hypothesis that turned out correct, the check command and its before/after output are in the ticket's Log

A bug that invalidated results is a failure class (`execution` / `measurement` / `data`), not a negative result: say which
verdicts it touches and which runs must be redone, before anything is relaunched.

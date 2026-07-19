# Step 7 — Independent verification pass

## Context

After several epics of feature work, it's worth an independent pass that isn't just "the same
session that wrote the code checking its own work." This step is agent-based (see
`../../agents/README.md` for how agents are defined in this repo) — four narrow, independent
checks rather than one broad "review everything" pass, so each one can go deep without diluting
into a generic sweep.

## Prompt

```
Run four independent verification passes on the current state of the app:

1. QA: run the full automated test suite, then a manual end-to-end golden-path check covering
   every major flow (ingest → configure rules → per-end-user scoping → autosave → cross-user
   accumulation on publish → tamper rejection). Report pass/fail with specifics; don't fix
   anything, just report.

2. Product/intent check: compare what's actually been built against the original requirements
   and any documented product decisions. Flag anything that's drifted from stated intent, and
   flag anything ambiguous that got implemented as a guess rather than a confirmed decision.

3. Frontend: check the UI actually works end-to-end in a real browser (not just that the code
   compiles), and check that styling is consistent — no hardcoded colors outside the design
   tokens, no dead tokens, error states visually distinguishable from success states.

4. Backend/architecture: verify every documented invariant still holds (cite file:line for
   each), and give a scalability assessment — what's the first thing that breaks under real
   load, in priority order, not just a generic list of concerns.

Use separate agents for each so they're independent of each other and of the session that wrote
the code.
```

## Expect / confirm

- Each pass should report findings, not silently fix them — you want visibility into what's
  actually wrong before code changes happen, especially since these are meant to be independent
  checks.
- Take any bug the frontend/backend passes find seriously even if QA's golden-path missed it —
  a golden-path test walks the expected sequence; a fresh functional pass is more likely to hit
  an edge case like a column literally named the same as a reserved word.

## Checklist after this step

- [ ] All four reports collected and read — not just "tests passed," the product/frontend/
      architecture passes too.
- [ ] Any concrete bug found gets fixed and covered by a regression test before being marked
      done.
- [ ] Scalability findings get written down somewhere durable (see
      `enterprise-readiness-template.md`) even if you're not acting on them yet — a POC that
      might go live later shouldn't lose this context.

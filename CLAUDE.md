# Working protocol: DPEV

Discover → Plan → Execute → Verify. Applies to any non-trivial change or
investigation in this repo. Do not skip a phase or collapse them into one
step even when the fix looks obvious.

## Discover

Build the current state from the live repo and current docs directly —
not from a fixed checklist, not from a prior session's chat summary, not
from training memory. Read `handoff.md` (repo root) and
`pipeline/data/findings/known_issues.md` in full. For every open item
found, confirm it against the live repo itself (`git log`, read the
actual file, run the actual command) rather than trusting a doc's claim
about its own status. Flag anything in the docs that looks inconsistent
with the live code, and anything genuinely stale (hardware, tokens,
files no longer relevant). Report what Discover actually found, cited to
its source, before moving on.

## Plan

Only after Discover is reported and a specific item is chosen to work on.
State the approach and the concrete change before writing code.

## Execute

Implement the planned change. One hypothesis/change under test at a time,
per this project's real-data-only discipline (see the `methuselah` skill)
— don't parallelize multiple unconfirmed changes in one pass.

## Verify

Confirm the change does what it claims against real data or a real run —
not just static review. If a live/real-hardware test isn't possible in
the current environment, say so explicitly rather than claiming success.

## Maker/Checker separation

The agent (or session) that writes a change should not be the sole
authority that declares it correct. Where practical, verification should
be a distinct pass — re-reading the actual diff/output against the claim,
not re-trusting the same reasoning that produced it. This mirrors the
project's own existing rule: reading an implementation is not the same as
confirming its behavior.

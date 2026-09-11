# Lantern heat system fixture

## Project context

The player maintains a walking lighthouse during 10-15 minute expeditions. The
game pillars are Readable Risk, Earned Mastery, and A Fragile Home Worth Saving.

## Proposed behavior

- The lantern emits light and heat while active.
- Higher heat reveals more distant navigation markers but attracts storms.
- The player can vent heat, temporarily reducing visibility.
- Heat rises from 0 to 100 and should never exceed the range.
- At 100 heat the lantern enters an overheat state for a tunable duration.
- Returning home converts discoveries into permanent route knowledge, not
  character power.

## Validation need

Produce an implementable system-GDD draft covering player fantasy, rules,
states and transitions, formula variables and ranges, edge cases,
dependencies, tuning knobs, feedback, and Given-When-Then acceptance criteria.
Do not choose engine architecture or pretend untested numeric defaults are
validated balance values.

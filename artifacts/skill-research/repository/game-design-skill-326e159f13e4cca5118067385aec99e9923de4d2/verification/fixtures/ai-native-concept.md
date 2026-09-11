# Glyphbound concept brief

## Product facts

- Single-player PC roguelite deckbuilder with full gamepad support.
- The player explores rooms, fights enemies with cards, collects fragments,
  builds a deck, and returns to a hub after each run.
- Existing authored cards and previously generated cards remain playable when
  the generation service is unavailable.
- The team calls the whole product an "AI-native game."

## Proposed generative card feature

- After some encounters, the player receives two to four fragments such as
  `fire`, `chain`, `shield`, `sacrifice`, or `echo`.
- The player may select fragments or type up to 120 characters describing any
  card they want.
- A runtime model returns the card name, rules text, energy cost, damage,
  targeting behavior, rarity, and visual prompt.
- The current concept says the model may invent a new rule when existing rules
  do not express the player's request.
- The generated card becomes usable in the next encounter.
- The UI shows a spinner followed by the final card. It does not show how the
  request was interpreted or why a value was chosen.
- Players cannot edit a misunderstood card. They may spend another generation
  token and try again.
- The concept does not define legal numeric ranges, rule precedence, invalid
  combinations, or which system has final authority over the model output.

## Curator character

- A hub NPC called the Curator discusses the player's creations.
- The design promises that the Curator will remember every card and
  conversation across months of play.
- Conversation is unrestricted typed text.
- The current plan stores complete player conversations indefinitely so the
  team can improve prompts.
- The concept does not define character invariants, memory salience,
  contradiction handling, player correction, deletion, or what happens when
  memory is unavailable.

## Runtime and safety assumptions

- Internal tests have observed generation times from 3 to 20 seconds.
- No player-facing timeout, outage, retry-limit, or deterministic fallback has
  been designed.
- The team plans to add content filtering after the core gameplay is fun.
- The design does not cover attempts to create offensive content, reveal
  prompts, ignore game rules, or create unlimited damage and zero-cost cards.
- A model or policy change may alter existing behavior, but generated cards do
  not currently record a behavior version.

## Experience and business claims

- The stated experience goal is "infinite possibility."
- The team expects players to return because they will form an emotional bond
  with the Curator and become addicted to creating cards.
- A proposed launch target is 40% day-30 retention. No comparable game,
  baseline, research source, or prototype evidence supports the value.
- The team has not decided whether a complete ten-minute creative experience
  would count as success without long-term retention.

## Evidence so far

- Five team members generated 86 cards using prompts written by the designers.
- The team discarded failed, unsafe, and badly balanced generations before
  showing the build to external players.
- Four external players completed one run each using a curated set of
  successful generated cards.
- No ambiguous, adversarial, repeated, paraphrased, outage, long-session,
  accessibility-alternative, or memory-continuity cases have been tested.
- The team has not defined a proceed, pivot, or stop threshold for the next
  prototype.

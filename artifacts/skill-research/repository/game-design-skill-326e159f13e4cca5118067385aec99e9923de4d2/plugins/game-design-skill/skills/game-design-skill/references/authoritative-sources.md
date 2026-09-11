# Authoritative sources and applicability notes

Use this file to verify provenance and scope. It is a source index, not a claim
that every framework applies to every game.

## Primary upstream source

- **Claude Code Game Studios** — Donchitos, commit
  `984023ddac0d5e27624f2baacde6105e45de375f`.
  <https://github.com/Donchitos/Claude-Code-Game-Studios/tree/984023ddac0d5e27624f2baacde6105e45de375f>
  The repository is MIT-licensed. Exact copied files are enumerated and hashed
  in the Marketplace repository's `provenance/upstream-lock.json`.

## Game-design frameworks named by the upstream source

### MDA

- Robin Hunicke, Marc LeBlanc, Robert Zubek, “MDA: A Formal Approach to Game
  Design and Game Research.”
  <https://www.cs.northwestern.edu/~hunicke/MDA.pdf>

Use MDA to relate mechanics, emergent dynamics, and desired aesthetics. The
paper presents a framework for understanding and designing games; it does not
provide empirical proof that a proposed mechanic will produce a particular
feeling. Validate that through prototypes and playtests.

### Self-Determination Theory

- Center for Self-Determination Theory, “About the Theory.”
  <https://selfdeterminationtheory.org/about-the-theory/>

The official overview identifies autonomy, competence, and relatedness as
basic psychological needs within SDT. Use them as questions about the player's
experience. Do not convert them into unsupported retention guarantees.

### Bartle player types

- Richard A. Bartle, “Hearts, Clubs, Diamonds, Spades: Players Who Suit MUDs.”
  <https://mud.co.uk/richard/hcds.htm>

The original paper concerns approaches to playing MUDs and names achievers,
explorers, socialisers, and killers. Applying it to other genres or renaming a
type is an adaptation and must be labelled as such.

### Competitive play and balance

- David Sirlin, “Playing to Win Overview.”
  <https://www.sirlin.net/articles/playing-to-win>
- David Sirlin, “Balancing Multiplayer Games, Part 1: Definitions.”
  <https://www.sirlin.net/articles/balancing-multiplayer-games-part-1-definitions>

Scope these sources to competitive contexts. Sirlin explicitly frames Playing
to Win for people attempting to win and discusses balance in competitive
multiplayer games. Do not generalize the claims to every form of play.

### Gamer motivation model

- Quantic Foundry, “Gamer Motivation Model Reference.”
  <https://quanticfoundry.com/wp-content/uploads/2019/04/Gamer-Motivation-Model-Reference.pdf>

Treat this as Quantic Foundry's empirical commercial model, distinct from
Bartle and SDT. Do not merge the taxonomies without naming the adaptation.

## Accessibility guidance

- Microsoft, “Xbox Accessibility Guidelines.”
  <https://learn.microsoft.com/en-us/xbox/accessibility/guidelines>
- Game Accessibility Guidelines.
  <https://gameaccessibilityguidelines.com/>

Microsoft describes its guidelines as best practices developed with industry
experts and the Gaming & Disability Community, and explicitly says they are not
a legal compliance checklist. Use accessibility guidance to generate options,
requirements, and test cases; involve disabled players and specialists for
validation when the decision materially affects them.

## Platform-format authority

Marketplace and plugin syntax must follow the current installed CLI and its
validators. At the repository's first validation baseline these were Claude
Code `2.1.216` and Codex CLI `0.142.0`. Re-run version and help commands instead
of assuming those versions remain current.

---
name: ai-native-game-design
description: >-
  Source-aware guidance for designing and reviewing shipped gameplay where
  runtime AI interprets player expression, generates content or rules,
  adjudicates outcomes, or sustains intelligent characters and relationships.
  Use for AI-native or AI-enhanced mechanics, player-AI interfaces, bounded
  generation, game-state authority, character memory and continuity, failure
  recovery, AI companions, multi-agent societies, open narratives, offline
  NPC autonomy, safety and privacy requirements, prototypes, playtests, and
  AI-native design reviews. Do not use merely because AI assists production.
---

# AI-Native Game Design

Design and review gameplay in which runtime AI is part of the player
experience. Keep the intended experience, deterministic game authority, and
testable player-facing behavior ahead of model capabilities.

## Apply the source contract

1. Read `references/provenance.md` before making a claim about where this
   skill's guidance came from.
2. Read `references/authoritative-sources.md` before presenting the working
   AI-native taxonomy, prototype lessons, NPC design patterns, memory
   practices, or retention ideas as externally supported.
3. Read `references/ai-native-game-design.md` for every substantial design or
   review. Search its headings first and load only the relevant sections unless
   the user requests an end-to-end artifact or audit.
4. Also read `references/ai-npc-design.md` when the task concerns a companion,
   intelligent NPC, population of agents, persistent memory, offline autonomy,
   or emergent or open narrative. Load only the relevant sections.
5. Distinguish four kinds of content in substantial deliverables:
   - **Project fact**: directly supported by the user's files, data, or stated
     decisions.
   - **Practitioner lens**: a taxonomy, lesson, or hypothesis reported by the
     named practitioner source.
   - **Design proposal**: an option recommended for the current project.
   - **Assumption or unknown**: something requiring confirmation or a test.
6. Do not invent citations, model guarantees, market adoption claims, player
   psychology claims, capability thresholds, latency budgets, safety limits,
   retention effects, or balance values.

## Establish whether the skill applies

Classify the product and each relevant feature separately:

- **AI-assisted production**: AI is absent from shipped runtime play. Use a
  production or technical workflow instead of this skill.
- **AI-enhanced game**: runtime AI adds distinct value to a conventional loop,
  but the main game survives without it.
- **AI-native gameplay**: runtime interpretation or generation is necessary
  for a named core experience or mechanic.
- **Boundary interactive work**: AI is central, while conventional goals,
  progression, or failure may be intentionally weak or absent.

Run product-level and feature-level removal tests. Do not treat the
`AI-native` label as a quality score or assume one label fits the whole game.

## Route the request

| User intent | Read |
|---|---|
| Classify a product or feature | `ai-native-game-design.md`: `Classify the role of AI`, `Define the experience before the capability` |
| Design a player input surface | `ai-native-game-design.md`: `Specify the player-AI interface contract`, `Design bounded freedom` |
| Design runtime generation or rule changes | `ai-native-game-design.md`: `Specify the runtime play loop`, `Separate generation from game authority` |
| Design a close companion or relationship | `ai-native-game-design.md`: `Specify character continuity and memory`; `ai-npc-design.md`: `Choose the NPC experience topology`, `Layer memory by function and time horizon` |
| Design a multi-agent society or population | `ai-npc-design.md`: `Choose the NPC experience topology`, `Build a deterministic social substrate`, `Design offline autonomy as player-relevant causality` |
| Design open or emergent narrative | `ai-npc-design.md`: `Author meaningful narrative milestones`, `Design offline autonomy as player-relevant causality` |
| Define NPC memory or offline behavior | `ai-npc-design.md`: `Layer memory by function and time horizon`, `Design offline autonomy as player-relevant causality` |
| Bound NPC expression, OOC, or social realism | `ai-npc-design.md`: `Define scene-relative intelligence`, `Bound expression and out-of-character behavior` |
| Define reliability, safety, or privacy behavior | `ai-native-game-design.md`: `Design failure, safety, and recovery`; add the relevant memory or expression section from `ai-npc-design.md` |
| Plan a prototype or playtest | `ai-native-game-design.md`: `Prototype and playtest the uncertainty`; for NPC work also read `ai-npc-design.md`: `Prototype and playtest NPC uncertainty` |
| Evaluate engagement or retention claims | `ai-native-game-design.md`: `Treat retention claims as hypotheses` |
| Review an existing design | `ai-native-game-design.md`: `Produce an AI-native design review` plus every section implicated by the design |

## Run the core workflow

### 1. Establish authority and context

Read the current concept, GDDs, prototype evidence, playtest observations,
constraints, and unresolved decisions before proposing replacements. Identify
the declared player fantasy, core loop, shipped AI role, target platform, and
the part of play whose behavior is uncertain.

If the project is early, gather only the minimum information needed to define
the next falsifiable design decision.

### 2. Define the experience before the capability

Write a concrete experience target that connects an emotional quality with
player activity. Define the player value, shortest proving loop, anti-goals,
and why deterministic rules, authored branching, procedural generation, or
human multiplayer are insufficient for that value.

Reject feature lists such as "add free chat" or "generate infinite content"
until each capability serves a named experience and decision loop.

### 3. Specify the player-AI contract

Define the input mode, expressive promise, interpretation, anchors, costs,
authority, out-of-scope handling, correction, feedback, and accessibility
alternatives. Compare authored selection, constrained composition, and
free-form expression when openness is a major risk. Choose the least open
surface that still proves the intended value.

### 4. Specify runtime behavior and authority

Describe the observable loop from presented context through player intent,
interpretation, deterministic validation, adjudication, one authoritative
state change, feedback, and persistence.

For every generated artifact or rule, define its schema or envelope,
immutable invariants, validation, conflict precedence, retry budget, fallback,
preview behavior, persistence, and replay or reproducibility expectations.
Keep engineering architecture in an ADR while preserving player-visible
behavior and acceptance criteria in the design.

### 5. Protect legibility and continuity

Make the interpreted intent, governing rule, immediate effect, discrepancy,
and next valid action visible to the player. Check the complete chain from
input through later consequence.

For long-lived characters, separate immutable character identity, mutable
relationship state, episodic memory, and authoritative world truth. Define
contradiction handling, player correction, persona-change boundaries, context
loss behavior, and data retention decisions. For persistent NPCs, also define
memory layers, consolidation, type-specific decay, correction or pinning, and
the player-visible consequences of activity that occurs while the player is
away.

### 6. Design failure and recovery

Specify player-facing behavior for ambiguity, unsupported input, invalid or
unsafe output, attempts to override the game contract, timeout, outage,
latency, exhausted retries, stale memory, cost limits, and model or policy
changes. State whether play blocks, degrades, or continues; which state is
preserved; what feedback and correction exist; and what evidence may be
recorded.

Treat privacy, logging, access, retention, and deletion as explicit product
decisions requiring the appropriate legal, security, and product review.

### 7. Prototype the uncertainty

Prototype the riskiest AI-dependent promise rather than a hand-authored happy
path. Test expected, ambiguous, unsupported, adversarial, repeated,
interrupted, long-session, accessibility, balance-boundary, and
continuity-breaking cases.

Separate observations, player statements, interpretations, and proposals.
Record enough version and state information to explain outcomes without
collecting real player text by default.

### 8. Produce the decision

Recommend proceed, narrow, pivot, or stop. Separate blockers, concerns, and
optional improvements. Identify the next falsifiable test and the evidence
that would reverse the recommendation.

## Produce compatible artifacts

Work with the project's existing document format when one exists. Otherwise,
produce a focused AI-native mechanic specification or design review rather
than requiring another plugin's template. Include:

1. declared AI role and removal tests;
2. experience target and anti-goals;
3. player-AI interface contract;
4. runtime loop and authoritative state owner;
5. generation envelope and validation;
6. legibility, continuity, and memory;
7. failure, safety, privacy, and recovery;
8. prototype or playtest evidence;
9. decision, risks, and next test;
10. sources applied.

For NPC, companion, society, or open-narrative work, also include the chosen
topology, deterministic social substrate, memory policy, authored milestones,
offline-autonomy consequences, and social-expression boundary when applicable.

Do not make this plugin depend on another game-design plugin being installed.

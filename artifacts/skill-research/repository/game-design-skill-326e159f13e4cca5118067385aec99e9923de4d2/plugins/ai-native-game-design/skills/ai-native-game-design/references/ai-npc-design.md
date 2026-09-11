# AI NPC, companion, and society design

Use this reference when runtime AI sustains one character, a long-lived
relationship, a population of agents, an open narrative, or NPC activity that
continues outside direct player interaction.

## Contents

1. [Source status](#source-status)
2. [Choose the NPC experience topology](#choose-the-npc-experience-topology)
3. [Build a deterministic social substrate](#build-a-deterministic-social-substrate)
4. [Author meaningful narrative milestones](#author-meaningful-narrative-milestones)
5. [Define scene-relative intelligence](#define-scene-relative-intelligence)
6. [Layer memory by function and time horizon](#layer-memory-by-function-and-time-horizon)
7. [Design offline autonomy as player-relevant causality](#design-offline-autonomy-as-player-relevant-causality)
8. [Bound expression and out-of-character behavior](#bound-expression-and-out-of-character-behavior)
9. [Scaffold participation for different players](#scaffold-participation-for-different-players)
10. [Prototype and playtest NPC uncertainty](#prototype-and-playtest-npc-uncertainty)
11. [Produce an AI NPC design specification](#produce-an-ai-npc-design-specification)

## Source status

This is repository-authored guidance synthesized from the Tencent Game
Institute EP.02 practitioner panel listed in `authoritative-sources.md`,
combined with the source-safety, authority, memory, privacy, and playtest
contracts in `ai-native-game-design.md`. It is not a transcript, research
paper, benchmark, or universal architecture.

Use the panel as a practitioner lens for:

- contrasting a population ecology with a close companion;
- combining authored social structure with generative variation;
- adding authored milestones to otherwise flat forward simulation;
- layering, compressing, consolidating, and forgetting memory;
- treating intelligence and appropriate expression as scene-relative;
- bounding out-of-character behavior and reviewing generated output;
- testing whether autonomous NPC activity matters to the player.

Do not turn the panel's project-specific model sizes, quality scores, deployment
contexts, or observations about particular models into general requirements.
Choose systems through current project evidence and scene-specific tests.

## Choose the NPC experience topology

Choose the relationship structure before choosing model behavior. Review these
topologies separately:

| Topology | Primary player value | Required substrate | Main risk |
|---|---|---|---|
| Population ecology | Observe, influence, or belong to a society whose members affect one another | Shared time, roles, resources, institutions, prices, hierarchy, incentives, and world-state rules | Many fluent NPCs produce noise without group-level consequences |
| Close companion | Build trust, friction, dependence, or mutual history with one character or small team | Stable identity, knowledge boundary, relationship state, shared goals, memory, and role-appropriate voice | A convincing line masks inconsistent behavior or invasive intimacy |
| Hybrid | Form a close relationship that remains situated in a changing society | Both substrates plus explicit propagation between personal and population state | The companion and society become two disconnected simulations |

Do not use NPC count as a design goal. State whether the intended experience
depends on:

- depth with one character;
- emergence among many characters;
- movement between personal and social scales;
- or a conventional authored NPC with a narrower adaptive layer.

Run a topology removal test. If removing population simulation preserves the
same player value, do not fund a society. If removing persistent relationship
state preserves the same value, do not promise a lifelong companion.

## Build a deterministic social substrate

Generative variation needs a stable social world to vary within. For a
population ecology, define:

- shared clock and update cadence;
- roles, affiliations, obligations, and authority;
- scarce resources, ownership, prices, wages, or rewards where relevant;
- legal actions and state-transition rules;
- communication reach and information asymmetry;
- goals, incentives, and conflict sources;
- institution-level state and group outcomes;
- resource, compute, and action budgets;
- how player actions enter and alter the system.

Keep authoritative social facts in deterministic state. Let AI propose plans,
interpret events, select from valid actions, or express consequences, but
validate every authoritative transition.

Judge the population by group behavior and player-visible consequences, not by
isolated dialogue quality. Test whether institutions, alliances, prices,
territories, or shared beliefs change coherently and whether the player can
understand and influence those changes.

## Author meaningful narrative milestones

Unbounded forward simulation often produces locally smooth activity without
meaningful stages, reversals, or remembered turning points. Add authored
milestones when the intended experience needs dramatic structure.

For each milestone, define:

1. causal prerequisites in authoritative world state;
2. the event or pressure introduced;
3. actors and institutions allowed to respond;
4. valid outcome ranges and protected invariants;
5. persistent world, relationship, or memory changes;
6. player-visible signs before, during, and after the event;
7. how the player can influence, avoid, or reinterpret it;
8. how it resolves, closes a stage, and leaves an aftermath;
9. whether it may recur, escalate, expire, or become impossible.

Use generation to vary response, expression, tactics, and local consequences
inside this scaffold. Do not require the model to invent every major event,
its causality, and its authority in one step.

Treat a milestone as a world-state transition, not merely a dialogue topic.
Test whether later behavior remembers and reacts to it.

## Define scene-relative intelligence

Define intelligence as appropriate behavior for the current role, scene, and
player expectation. More knowledge, longer answers, or a larger model do not
automatically create a better game character.

Specify three layers:

1. **Authoritative context:** current world facts, permissions, relationships,
   goals, resources, and consequences.
2. **Design scaffold:** character invariants, role, tone, topic boundaries,
   valid strategies, narrative milestone, and output envelope.
3. **Generative behavior:** interpretation, planning, selection, adaptation, or
   expression produced inside those limits.

Build scene-specific evaluation cases before choosing a model or increasing
capability. Prefer the least open and most controllable system that meets the
experience target, latency, cost, safety, and variation requirements. Record
the evaluated model and behavior version without treating parameter count as
a design quality score.

## Layer memory by function and time horizon

Do not equate more stored text with better memory. Long context can dilute
attention, preserve irrelevant details, and make correction difficult.

Separate memory layers:

| Layer | Purpose | Example policy questions |
|---|---|---|
| Working context | Sustain the current scene or task | What must remain available until the scene ends? |
| Recent episodic memory | Preserve near-term events and promises | What is summarized after the session, and when does it decay? |
| Player-related memory | Support a relationship with the current player | Which preferences or shared events are relevant, visible, and correctable? |
| Major events | Preserve durable turning points | What qualifies as a milestone, and can the player contest the record? |
| Stable character state | Protect identity, goals, values, and long-term relationship state | Which fields are immutable, slowly mutable, or versioned? |
| NPC self-history and world memory | Give the character a life and context beyond the player | Which facts exist before contact, and which are authoritative? |

For each layer, define:

- source, provenance, and authority;
- salience rule;
- raw record, structured state, or summary form;
- consolidation or reflection cadence;
- retrieval trigger and ranking;
- type-specific decay or expiry;
- contradiction and replacement behavior;
- player inspection, correction, pinning, and deletion;
- privacy, consent, access, and retention requirements;
- behavior when retrieval fails or memory is unavailable.

Use consolidation or reflection to compress episodes into a smaller set of
useful relationship or character updates. Keep inferred player traits separate
from observed events. Mark them as uncertain, avoid converting sensitive
inferences into facts, retain their source and confidence where appropriate,
and let the player correct or reject them. Do not let reflection overwrite
authoritative world facts or explicit player corrections without validation.

Allow a player to mark an event as important only within explicit storage and
privacy boundaries. A promise such as "never forget" still needs expiry,
deletion, migration, and unavailable-memory behavior.

Apply time relevance by memory type. A recent illness, an old promise, a
one-time preference, and a world-changing event should not share one decay
rule.

## Design offline autonomy as player-relevant causality

An NPC may have goals, actions, relationships, and memories before meeting the
player and while the player is away. This avoids a blank-slate character, but
unseen activity is not automatically gameplay.

For every autonomous process, define:

- goal and valid action space;
- authoritative inputs and state owner;
- cadence and resource or authority budget;
- collision and conflict rules;
- persistent world delta;
- player-visible evidence on return;
- opportunities for the player to anticipate, influence, benefit from, or
  repair the consequence;
- catch-up, pause, and fallback behavior.

Prefer summarized or event-driven simulation when full continuous simulation
does not produce additional player value. Stop or narrow autonomous behavior
that consumes resources but creates only invisible NPC theatre.

When an NPC appears across a lobby, match, home space, or other contexts,
define each touchpoint's cadence, duration, scene role, carried state, and
opt-out behavior. Do not reduce an embodied or systemic character to a chat
window by default.

## Bound expression and out-of-character behavior

Treat factual fabrication, out-of-character behavior, continuity failure,
unsafe output, and excessive social realism as different failures.

Use multiple controls where the risk warrants them:

- authoritative environment and relationship state;
- valid action or strategy envelope;
- character invariants and knowledge boundaries;
- scene-specific topic pools and response goals;
- structured output or deterministic validators;
- post-generation review, bounded retry, and authored fallback;
- player reporting, correction, and recovery.

Do not promise that hallucination or out-of-character behavior is eliminated.
State the residual risk and the player-visible fallback.

Define the social boundary even when a response is entertaining and consistent
with the character. Specify permitted levels of intimacy, dependence,
sarcasm, hostility, disclosure, persuasion, and emotional escalation for the
audience and context. A character can become "too human" for the product's
contract without technically breaking persona.

## Scaffold participation for different players

Open conversation and creative input can disproportionately reward articulate,
confident, or highly inventive players. Test the experience with novice,
low-expression, accessibility-dependent, and time-constrained players as well
as expert users.

Provide scaffolds that preserve agency:

- suggested intents or topic starters;
- selectable goals, tones, or relationship moves;
- examples grounded in current context;
- constrained composition as an alternative to free text;
- short-input and non-verbal paths;
- visible interpretation and low-cost correction;
- graceful continuation when the player provides little input.

Do not judge the design only by demonstrations from expert prompt writers.

## Prototype and playtest NPC uncertainty

Start by exploring possible behaviors, then deliberately converge on a
controllable range supported by player evidence.

Test cases should cover:

- expected, ambiguous, adversarial, and out-of-scope interaction;
- the same intent across different roles, scenes, and relationship states;
- repeated, paraphrased, interrupted, and delayed interaction;
- long-session and cross-session continuity;
- retrieval of recent, old, corrected, pinned, expired, and unavailable memory;
- conflict between inferred player traits and explicit player correction;
- major world events and their later consequences;
- autonomous NPC activity during player absence;
- group-level emergence, resource conflict, and institution change;
- novice and low-expression participation;
- excessive intimacy, hostility, persuasion, or disclosure;
- review failure, retry exhaustion, and deterministic fallback;
- model or behavior-version change.

Record authoritative input state, retrieved memory, scaffold version,
generated proposal, validation or review result, final state transition,
player-visible response, latency, and behavior version. Minimize or synthesize
player text unless consent and a retention policy exist.

Measure experience outcomes such as comprehension, influence, surprise,
relationship continuity, social coherence, and recovery. Do not substitute
conversation length, token count, NPC activity volume, or model size.

## Produce an AI NPC design specification

For a substantial NPC, companion, society, or open-narrative design, include:

1. experience target and chosen topology;
2. player role and removal test;
3. deterministic social and world substrate;
4. scene-relative behavior and evaluation cases;
5. character invariants, mutable relationship state, and world truth;
6. memory layers, consolidation, decay, correction, and privacy;
7. authored milestones and causal consequences where applicable;
8. offline autonomy and player-visible world deltas;
9. expression, OOC, safety, and social-boundary controls;
10. accessibility and participation scaffolds;
11. failure, fallback, persistence, and version behavior;
12. prototype evidence, unknowns, and next falsifiable test;
13. sources applied and practitioner claims kept as hypotheses.

Omit inapplicable sections explicitly rather than pretending every character
needs population simulation, persistent memory, or open-ended dialogue.

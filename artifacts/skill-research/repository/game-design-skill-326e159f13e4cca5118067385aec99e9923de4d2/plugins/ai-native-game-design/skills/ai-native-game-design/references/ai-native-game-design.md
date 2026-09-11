# AI-native game design and review

Use this reference when generative AI runs during play, interprets player
expression, changes game content or rules, performs adjudication, or sustains a
character or relationship over time.

## Contents

1. [Source status](#source-status)
2. [Classify the role of AI](#classify-the-role-of-ai)
3. [Define the experience before the capability](#define-the-experience-before-the-capability)
4. [Specify the player-AI interface contract](#specify-the-player-ai-interface-contract)
5. [Specify the runtime play loop](#specify-the-runtime-play-loop)
6. [Design bounded freedom](#design-bounded-freedom)
7. [Protect legibility and continuity](#protect-legibility-and-continuity)
8. [Separate generation from game authority](#separate-generation-from-game-authority)
9. [Specify character continuity and memory](#specify-character-continuity-and-memory)
10. [Design failure, safety, and recovery](#design-failure-safety-and-recovery)
11. [Treat retention claims as hypotheses](#treat-retention-claims-as-hypotheses)
12. [Prototype and playtest the uncertainty](#prototype-and-playtest-the-uncertainty)
13. [Produce an AI-native design review](#produce-an-ai-native-design-review)

## Source status

This is a repository-authored synthesis, not a verbatim upstream record. Its
starting practitioner source is the Tencent Game Institute EP.01 panel recap
listed under **Practitioner evidence** in `authoritative-sources.md`. That
panel combines academic, laboratory, and shipped-project perspectives, but it
is not a peer-reviewed paper or an industry standard. Use
`ai-npc-design.md` for the distinct NPC, companion, society, memory, and open
narrative guidance synthesized from EP.02.

Use the panel for:

- practitioner taxonomies and design questions;
- reported prototype and playtest lessons;
- examples of input anchoring, rule generation, character continuity, and
  bounded generativity;
- hypotheses worth testing in a project.

Do not use it as proof of:

- market adoption percentages;
- universal genre suitability;
- a current model capability or defect rate;
- a guaranteed retention, emotional, therapeutic, or monetization effect;
- a fixed schedule, staffing estimate, or safety threshold.

The labels below are working design lenses. Preserve competing interpretations
when a project does not fit one label cleanly.

## Classify the role of AI

Classify both the whole product and each AI-dependent feature. A game can
remain conventional overall while containing one AI-native mechanic.

| Working category | Test | Design consequence |
|---|---|---|
| AI-assisted production | AI is used before release; removing it from the shipped runtime does not change play | Apply the normal design workflow; review the production pipeline separately |
| AI-enhanced game | Runtime AI improves or extends a conventional loop, but the main game remains playable without it | Specify the feature's value, failure mode, and fallback without relabelling the whole game |
| AI-native gameplay | Runtime generation or interpretation is necessary for a named core experience or mechanic | Treat model behavior, adjudication, latency, recovery, and evaluation as part of the game design |
| Boundary interactive work | AI is central, but goals, progression, failure, or game structure may be intentionally weak or absent | Judge it by its declared interactive-art, relationship, toy, or expressive goals instead of forcing competitive-game criteria |

Run two removal tests:

1. **Product removal test:** If runtime AI disappears, which core loops,
   fantasies, decisions, or relationships collapse?
2. **Feature removal test:** If one AI feature disappears, what distinct
   player value disappears even if the rest of the game still runs?

Do not use removal as the only definition. Record why the distinction matters
to scope, player expectation, validation, or fallback behavior.

## Define the experience before the capability

Write one experience target before listing AI features. Prefer a concrete
phrase that joins an emotional quality with player activity, then make it
testable through observable play.

Also define:

- the player fantasy;
- the decision or expression AI makes newly possible;
- the shortest loop that demonstrates that value;
- anti-goals describing what the experience must not become;
- why deterministic rules, authored branching, procedural generation, or
  multiplayer humans are insufficient for the intended value;
- the minimum AI-dependent slice that can prove or disprove the premise.

Reject capability-led requirements such as "add free chat," "make every NPC
intelligent," or "generate infinite content" unless they serve a named
experience and decision loop.

Distinguish:

- **possible:** the model can produce an output;
- **usable:** the player can understand and control the interaction;
- **playable:** the interaction creates meaningful decisions, feedback, risk,
  mastery, expression, or discovery.

## Specify the player-AI interface contract

Treat the player-AI interface as a game system, not as a generic chat box.
Define every row that applies:

| Contract element | Required design decision |
|---|---|
| Input mode | Selection, constrained composition, typed language, speech, drawing, action history, or a combination |
| Expressive promise | What the interface tells the player they may attempt |
| Interpretation | What intent, entities, targets, quantities, and context the game extracts |
| Authority | Which system decides whether an interpreted intent is legal and what effect it has |
| Anchors | Values, keywords, resources, cards, verbs, targets, or state constraints that bound the result |
| Cost and stakes | What the player spends or risks by submitting an intent |
| Out-of-scope handling | How the game declines, redirects, or converts an unsupported request |
| Correction | How the player sees and repairs a misunderstanding without restarting the experience |
| Feedback | How interpretation, validation, effect, and downstream consequences become visible |
| Accessibility | How players avoid mandatory long-form typing or speech and can use alternate input methods |

Do not assume unrestricted natural language is the most expressive interface.
Compare at least three control surfaces when input is a major design risk:

1. authored selection;
2. constrained composition from meaningful parts;
3. free-form expression with explicit anchors and repair.

Choose the least open surface that still proves the intended value.

## Specify the runtime play loop

Describe behavior independently from implementation architecture:

1. The game presents context, affordances, and constraints.
2. The player expresses an intent.
3. The system interprets the intent into inspectable game terms.
4. Deterministic rules validate permissions, costs, targets, and invariants.
5. An authority adjudicates the legal outcome.
6. The authoritative state changes once.
7. Player-facing feedback explains what happened.
8. Relevant consequences, memories, or content persist.

For every step, define:

- input and output;
- authoritative owner;
- maximum acceptable uncertainty or latency;
- rejection and retry behavior;
- player-visible feedback;
- data that persists;
- acceptance criteria.

If generation changes a rule, specify the **rules for creating rules**:

- which rule dimensions may change;
- valid ranges and combinations;
- duration and scope;
- conflict precedence;
- resource budget;
- preview and confirmation;
- rollback or expiry;
- validation before state mutation.

## Design bounded freedom

Treat freedom as designed possibility inside a legible contract. Avoid both
extremes:

- so little freedom that AI contributes no distinct value;
- so much freedom that players cannot form a useful mental model or predict
  consequences.

Use constraints to create mastery:

- expose stable verbs and resources;
- anchor generated effects to known quantities;
- limit targets, scope, duration, or consequence classes;
- make accepted and rejected intents explainable;
- preserve surprise inside a stable outcome envelope;
- allow the player to learn how to express better intents over time.

Do not silently reward incoherent or adversarial input merely because the model
can continue. If intentionally provoking the system becomes the most reliable
source of entertainment, decide whether to embrace that as the real design or
close the exploit.

## Protect legibility and continuity

Review two practitioner lenses separately:

### Interaction legibility

Can the player identify:

- what the system believed they meant;
- which rule accepted or rejected it;
- what changed immediately;
- why the outcome differed from expectation;
- what they can try next?

### Context continuity

Does the result remain coherent with:

- current world state;
- prior player actions;
- character commitments and relationships;
- active goals and unresolved consequences;
- the intended tone and role of the player?

Test the full chain:

`prompt or action → interpreted intent → rule adjudication → state change → feedback → later consequence`

An entertaining line of dialogue does not repair a broken state transition.
A mechanically legal result does not repair a character or world contradiction.

## Separate generation from game authority

Specify what AI may propose and what the game must validate. Do not let fluent
output silently become authoritative state.

For each generated artifact, define:

- schema or behavioral envelope;
- immutable invariants;
- deterministic validation;
- conflict resolution;
- maximum retry budget;
- safe fallback;
- whether the player sees a preview;
- whether the result can be reproduced or replayed;
- whether model, prompt, policy, or data changes can invalidate prior content.

Consider a hybrid strategy when real-time generation is too risky:

- pre-generate and review a bounded content pool;
- use runtime AI only to route, select, adapt, or parameterize;
- fall back to authored content when validation, latency, or safety fails.

Treat hybrid generation as a design option, not a guarantee of zero errors.

## Specify character continuity and memory

Separate at least four concerns:

| Concern | Design question |
|---|---|
| Character invariants | Which identity, knowledge, values, voice, and boundaries must not drift? |
| Mutable relationship state | Which attitudes may change, through what player actions, and at what rate? |
| Episodic memory | Which events should be remembered, summarized, forgotten, corrected, or contested? |
| World truth | Which facts remain authoritative even when a character lies, forgets, or hallucinates? |

Distinguish:

- **factual fabrication:** unsupported content stated as fact;
- **out-of-character behavior:** output conflicts with the established role;
- **continuity failure:** output ignores a salient past event or relationship;
- **intentional unreliability:** a designed trait the player can understand.

For long-lived relationships, define:

- memory salience and retention rules;
- contradiction handling;
- player correction or consent;
- persona-change boundaries;
- what happens when memory is unavailable;
- whether sensitive player disclosures are stored, summarized, or discarded.

Treat logging, privacy, retention, access, and deletion as project decisions
that require product, security, and legal review. Do not hide them inside a
character-design section.

## Design failure, safety, and recovery

Include player-facing behavior for:

- unsupported or ambiguous intent;
- invalid or balance-breaking output;
- unsafe or disallowed content;
- prompt injection or attempts to override the game contract;
- model timeout, rate limit, outage, or excessive latency;
- exhausted retry or validation budget;
- context loss, stale memory, or version drift;
- cost or abuse limits;
- a model or policy change that alters established behavior.

For each failure, specify:

1. whether play blocks, degrades, or continues;
2. the deterministic state preserved;
3. the feedback shown to the player;
4. available correction or fallback;
5. what evidence is recorded for diagnosis;
6. what player data must not be recorded.

Keep technical architecture in an engineering design or ADR. The GDD should
still state the observable behavior, authority, constraints, and acceptance
criteria.

## Treat retention claims as hypotheses

The EP.01 panel proposes two useful directions:

- relationship or emotional continuity;
- player creation enabled by lower-friction generative tools.

Use them as hypotheses, not default requirements. First decide whether the game
needs long-term retention at all. A short, complete experience can succeed
without service-game engagement.

For each retention hypothesis, define:

- intended player value;
- return trigger;
- content or relationship state that changes between sessions;
- risk of repetition, dependency, manipulation, or unwanted disclosure;
- comparison against a non-AI or lower-AI alternative;
- measurement period and success criteria;
- evidence that would falsify the hypothesis.

Do not equate conversation length, token use, content volume, or repeated
logins with fun, healthy attachment, or meaningful play.

## Prototype and playtest the uncertainty

Prototype the riskiest AI-dependent promise before building the surrounding
game. A useful prototype should expose the real interaction surface, not a
hand-authored happy path that bypasses generation.

Maintain a playtest evidence set containing:

- anonymized or synthetic input cases;
- interpreted intents;
- validation and adjudication results;
- player-visible responses;
- resulting state transitions;
- latency and failure outcomes;
- model and behavior version;
- whether the outcome can be replayed;
- observer notes separated from player statements;
- design decision: encourage, constrain, reject, or investigate.

Test at least:

- expected inputs;
- ambiguous inputs;
- unsupported inputs;
- adversarial or boundary-seeking inputs;
- repeated and paraphrased inputs;
- interrupted or delayed responses;
- long-session continuity;
- accessibility alternatives;
- attempts to exceed balance or narrative authority.

Do not store real player text by default merely because it would help tuning.
Define consent, minimization, redaction, access, retention, and deletion before
collecting it.

## Produce an AI-native design review

Lead with the design outcome, then report:

1. **Declared AI role:** product and feature classification, with removal-test
   evidence and uncertainty.
2. **Experience target:** intended value, core loop, anti-goals, and why AI is
   necessary.
3. **Player-AI contract:** input surface, interpretation, anchors, authority,
   correction, feedback, and accessibility.
4. **Runtime loop:** state transitions, generation envelope, validation,
   adjudication, persistence, and fallback.
5. **Legibility and continuity:** player mental model, feedback chain, world
   coherence, OOC, and memory.
6. **Failure and safety:** latency, outage, invalid output, unsafe input,
   recovery, privacy, and evidence policy.
7. **Prototype and playtest evidence:** observations, measurements, unknowns,
   and the next falsifiable test.
8. **Decision:** proceed, narrow, pivot, or stop, with blockers, concerns, and
   optional improvements separated.
9. **Sources applied:** project artifacts, this authored synthesis, applicable
   project workflows, and any primary or institutional sources actually used.

Do not award an "AI-native" label as a quality score. Judge whether the chosen
AI role produces a coherent, testable, and worthwhile player experience.

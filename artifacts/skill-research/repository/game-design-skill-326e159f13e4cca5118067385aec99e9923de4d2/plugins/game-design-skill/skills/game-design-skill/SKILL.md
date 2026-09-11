---
name: game-design-skill
description: >-
  Source-grounded game design guidance for concept ideation, game pillars,
  core loops, system decomposition, GDD authoring, formulas and tuning knobs,
  balance and economy analysis, prototyping, playtest interpretation, UX,
  accessibility, scope control, design-change propagation, and single- or
  cross-document design review. Use when creating, refining, documenting,
  auditing, or validating how a game should work or feel.
---

# Game Design Skill

Guide game design with traceable source material. Prefer the user's project
evidence and decisions, use the vendored Claude Code Game Studios material as
the primary reusable workflow, and consult primary or institutional sources
when a claim needs stronger authority.

## Apply the source contract

1. Read `references/provenance.md` before making a claim about where this
   skill's guidance came from.
2. Read `references/authoritative-sources.md` before presenting MDA,
   Self-Determination Theory, Bartle player types, competitive balance, or
   accessibility guidance as research-backed.
3. Treat files named `references/upstream-*.md` as verbatim MIT-licensed source
   records. Preserve their useful wording and procedures where they fit the
   user's task.
4. Distinguish four kinds of content in substantial deliverables:
   - **Project fact**: directly supported by the user's files, data, or stated
     decisions.
   - **Source-backed method**: derived from a named upstream, authoritative,
     or clearly labelled practitioner source.
   - **Design proposal**: an option recommended for this project, not a fact.
   - **Assumption or unknown**: something that requires confirmation or a test.
5. Do not invent citations, empirical thresholds, market claims, player
   psychology claims, engine capabilities, or balance values.

## Apply the compatibility contract

The upstream references were written for a full Claude Code studio template.
Use their game-design knowledge, document structures, questions, checks, and
examples. Do not execute their platform wrapper literally.

- Ignore upstream YAML fields such as `model`, `allowed-tools`, `tools`,
  `maxTurns`, and `memory`.
- Translate `AskUserQuestion` into the current product's normal user-decision
  mechanism. Ask only when the answer materially changes the design.
- Treat `Task`, named studio agents, director gates, review modes, and session
  state updates as optional review roles, not required runtime dependencies.
- Resolve project files from the actual workspace. Do not assume fixed paths
  such as `design/gdd/`, `assets/data/`, or `production/session-state/` exist.
- Do not write or edit project files when the user requested advice, analysis,
  diagnosis, or review only.
- When the user requests an artifact, preserve the upstream template structure
  unless the project already has a stronger authoritative format.

## Route the request

Load only the references needed for the current request.

Some verbatim records are intentionally long because they preserve complete
upstream files. Search their headings first and read only the applicable
sections for a focused request. Read a whole workflow or template when the
user requests the complete artifact or an end-to-end audit. Do not load every
reference merely because it is available.

| User intent | Read these workflow sources | Read these templates or specialist sources |
|---|---|---|
| Discover or compare concepts | `upstream-workflow-brainstorm.md` | `upstream-template-game-concept.md`, `upstream-template-game-pillars.md`, `upstream-agent-creative-director.md` |
| Define pillars, fantasy, audience, or loops | `upstream-agent-game-designer.md`, `upstream-workflow-brainstorm.md` | `upstream-template-game-pillars.md`, `upstream-template-player-journey.md` |
| Decompose a concept into systems | `upstream-workflow-map-systems.md`, `upstream-agent-systems-designer.md` | `upstream-template-systems-index.md` |
| Author a system GDD | `upstream-workflow-design-system.md`, `upstream-agent-game-designer.md` | `upstream-template-game-design-document.md` plus the relevant specialist source |
| Specify a small change | `upstream-workflow-quick-design.md` | Read the affected GDD and project baseline |
| Review one GDD | `upstream-workflow-design-review.md` | `upstream-rule-design-docs.md`, `upstream-template-game-design-document.md` |
| Review all GDDs or system interactions | `upstream-workflow-review-all-gdds.md`, `upstream-workflow-consistency-check.md` | `upstream-template-systems-index.md` |
| Analyze combat, progression, loot, or economy balance | `upstream-workflow-balance-check.md`, `upstream-agent-economy-designer.md` | `upstream-template-economy-model.md`, `upstream-template-difficulty-curve.md` |
| Check scope or implementation coverage | `upstream-workflow-scope-check.md`, `upstream-workflow-content-audit.md` | Read the original plan and current implementation evidence |
| Propagate a design change | `upstream-workflow-propagate-design-change.md` | Read the previous and current design plus affected architecture/docs |
| Plan or assess a prototype | `upstream-workflow-prototype.md`, `upstream-agent-prototyper.md` | `upstream-template-prototype-report.md` |
| Capture or interpret a playtest | `upstream-workflow-playtest-report.md` | `upstream-template-prototype-report.md`, affected GDDs |
| Design or review game UX/HUD | `upstream-workflow-ux-design.md`, `upstream-workflow-ux-review.md`, `upstream-agent-ux-designer.md` | `upstream-template-ux-spec.md`, `upstream-template-hud-design.md`, `upstream-template-interaction-pattern-library.md` |
| Review accessibility | `upstream-agent-accessibility-specialist.md` | `upstream-template-accessibility-requirements.md`, `authoritative-sources.md` |
| Design a level or encounter | `upstream-agent-level-designer.md` | `upstream-template-level-design-document.md`, relevant system GDDs |
| Design live-service cadence or retention | `upstream-agent-live-ops-designer.md` | Economy, analytics, ethics, and project constraints |

## Run the core workflow

### 1. Establish authority and context

Identify the user's requested outcome, project stage, intended player
experience, constraints, reference games, target platforms, existing design
documents, implementation evidence, and unresolved decisions. Read existing
project artifacts before proposing replacements.

If no project exists, gather only the minimum information needed for the next
decision. Do not force a complete studio questionnaire onto a small request.

### 2. Select the smallest applicable workflow

Use the routing table. Prefer a quick design for a contained change, a system
GDD for a substantial mechanic, a prototype for a risky assumption, and a
review workflow for an existing artifact. Do not turn every question into a
full GDD.

### 3. Reuse source wording and structure

Follow the selected upstream workflow in its original order when that order
fits the task. Reuse its questions, checklists, tables, and template headings.
Adapt only platform calls, fixed repository paths, unavailable studio roles,
or instructions that conflict with the user's scope.

When adapting source text in a saved deliverable, record the source and nature
of the adaptation if the user requests an auditable artifact.

### 4. Collaborate on design decisions

Present two to four materially distinct options when multiple approaches are
valid. Explain tradeoffs, identify the source-backed lens being applied, make a
recommendation when evidence supports one, and leave the creative decision to
the user.

Do not disguise a recommendation as a law. Do not use a framework merely to
decorate a predetermined answer.

### 5. Make the design implementable and testable

For mechanics and systems, define behavior rather than architecture. Include
precise rules, states and transitions where applicable, system inputs and
outputs, formulas with variables and ranges, edge-case resolutions, dependency
direction, tuning knobs, feedback requirements, and acceptance criteria.

Keep design decisions separate from technical architecture decisions. Flag
implementation questions for an ADR or engineering review instead of silently
embedding a technology choice in the GDD.

### 6. Validate at the appropriate scope

For one document, check completeness, internal consistency, implementability,
pillar alignment, formulas, edge cases, dependencies, and testability.

For multiple documents, check bidirectional dependencies, rule contradictions,
stale references, data ownership, formula range compatibility, acceptance
criteria conflicts, progression and economy interactions, dominant strategies,
difficulty scaling, player-fantasy coherence, and multi-system scenarios.

When a stated rule is absent from a formula, report the missing operation or
ordering. Do not infer that an unstated variable must have a particular value
when a clamp, floor, cap, or alternate ordering could also satisfy the rule;
name the plausible interpretations and ask the owner to resolve them.

For balance, calculate from actual data when available. Without data, provide a
model, identify required measurements, and label all sample numbers as
illustrative.

Show derived calculations so they can be checked. Keep a mathematically proven
consequence separate from a structural risk hypothesis. Do not call an economy
state unrecoverable, a strategy dominant, or a resource meaningless without a
complete-enough model or observed evidence that supports that conclusion.

For prototypes and playtests, separate observations from interpretations and
recommendations. State whether the evidence supports proceeding, pivoting, or
stopping, and identify what remains untested.

## Handle research-backed frameworks carefully

- Use MDA as a design and analysis framework, not as proof that a mechanic will
  be fun.
- Use Self-Determination Theory to ask how a design may support or thwart
  autonomy, competence, and relatedness; do not claim those needs guarantee
  retention or enjoyment.
- State that Bartle's original taxonomy concerned players of MUDs. If applying
  it elsewhere, label the use as an adaptation and do not rename the original
  four types without explanation.
- Scope competitive-balance guidance to games where players are attempting to
  win. Do not force competitive assumptions onto expressive, narrative, toy,
  or deliberately asymmetric experiences.
- Treat accessibility guidance as design and testing support, not as a legal
  compliance certification.
- Treat upstream numeric thresholds and universal-sounding rules as heuristics
  unless `authoritative-sources.md` supports the exact claim and scope.

## Report the result

Lead with the design outcome. Name the artifact or decision produced, list the
most important unresolved risks, and identify the next evidence-gathering step.
For reviews, separate blockers, concerns, and optional improvements. For
source-sensitive work, include a short Sources Applied section linking the
specific internal references used.

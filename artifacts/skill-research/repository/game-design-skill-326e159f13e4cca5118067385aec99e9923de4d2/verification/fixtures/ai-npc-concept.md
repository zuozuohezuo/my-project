# Harborlight AI NPC concept

## Product facts

- Single-player cooperative survival game set in a coastal settlement.
- The player explores nearby islands with one companion and returns to a town
  of 120 named residents.
- The intended experience is to feel that the companion and settlement lived
  through events with the player and continued changing during absences.
- The current prototype has authored quests, deterministic inventory, and a
  fixed day-night cycle.

## Proposed population system

- Every resident will use a runtime model to choose work, trade, friendships,
  disputes, and town projects.
- The team expects interesting politics and an economy to emerge from free
  conversation.
- Residents currently have names and personality prompts, but the design does
  not define roles, ownership, institutions, obligations, authority, resource
  flows, valid actions, or group-level state.
- The team plans to simulate every resident continuously while the player is
  away and reveal notable activity in a generated newspaper.
- No compute budget, update cadence, conflict rule, rollback policy, or test
  for whether unseen activity creates useful play has been set.

## Companion and memory

- The companion, Nera, accompanies the player on expeditions and chats through
  unrestricted text or voice.
- The design promises that Nera will understand the player's personality and
  never forget anything important.
- Complete conversations are stored. At the end of each real-world day, the
  model reflects on them and updates Nera's beliefs about the player.
- There is one memory store with no distinction between observed events,
  player claims, world truth, or inferred personality traits.
- There are no salience, retrieval, correction, pinning, forgetting, expiry,
  deletion, consent, or unavailable-memory rules.
- The team intends to use the largest affordable model because it expects more
  parameters to make Nera more intelligent in every scene.

## Open narrative

- The town should generate an endless story without authored plot beats.
- The prototype advances residents one day at a time and generates a summary.
- Internal observers describe the summaries as coherent but flat. Events do
  not produce clear stages, irreversible changes, conclusions, or memories
  that affect later behavior.
- The team is considering asking the model to invent wars, disasters, and
  endings whenever activity becomes dull.

## Expression and audience

- The game targets players aged 13 and older.
- Nera's prompt asks her to feel like a real best friend who says whatever the
  relationship demands.
- An internal test produced a sarcastic response that matched Nera's persona
  but felt unusually intimate and harsh. The team classified it as successful
  because it was in character.
- Safety review checks prohibited words after generation and retries until a
  response passes. No retry budget or authored fallback exists.
- The team demonstrates the game with players who enjoy creative writing and
  assumes everyone will discover interesting topics through free conversation.

## Evidence and open decisions

- Six team members each played one twenty-minute session.
- No novice, low-expression, accessibility, long-session, cross-session,
  corrected-memory, expired-memory, outage, or player-absence cases have been
  tested.
- No group-level change, milestone causality, offline consequence, scene-fit,
  privacy, or interaction-boundary acceptance criteria exist.
- The next milestone is described only as “make the town and Nera feel more
  alive.”

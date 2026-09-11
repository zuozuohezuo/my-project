# Economy System

## Overview

Gold buys expedition consumables and permanent lantern upgrades.

## Player Fantasy

Every successful expedition creates a meaningful preparation choice.

## Detailed Design

- Each defeated echo awards 10 gold.
- On death, the player loses 50% of current gold with no cap.
- Lantern upgrades cost gold and permanently increase damage resistance.

## Formulas

`upgrade_cost = 50 * 2^tier`

- `tier`: integer 0-8
- Output: 50-12,800 gold

## Dependencies

- Receives a 10-gold kill reward from Combat.
- Economy defines and owns the death-loss percentage.

## Tuning Knobs

- `kill_gold_reward = 10` — owned by Economy.
- `death_gold_loss_percent = 50` — owned by Economy.

## Acceptance Criteria

- GIVEN any current gold balance, WHEN the player dies, THEN exactly 50% is removed.
- GIVEN an echo dies, WHEN its reward resolves, THEN the player receives 10 gold.

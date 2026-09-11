# Combat System

## Overview

Combat is an optional defensive system used when storms create hostile echoes.

## Player Fantasy

The player survives through preparation and readable counterplay.

## Detailed Design

- Each defeated echo awards 20 gold.
- On death, the player loses 25% of current gold.
- A single hit cannot reduce a full-health player below 1 health.

## Formulas

`damage = base_damage * power_multiplier`

- `base_damage`: 10-40
- `power_multiplier`: 1-5
- Output: 10-200 damage

## Dependencies

- Outputs kill rewards to Economy.
- Reads the Economy-owned death-loss percentage.

## Tuning Knobs

- `kill_gold_reward = 20` — owned by Combat.
- `death_gold_loss_percent = 25` — owned by Combat.

## Acceptance Criteria

- GIVEN full health, WHEN one attack lands, THEN the player retains at least 1 health.
- GIVEN an echo dies, WHEN its reward resolves, THEN Economy receives 20 gold.

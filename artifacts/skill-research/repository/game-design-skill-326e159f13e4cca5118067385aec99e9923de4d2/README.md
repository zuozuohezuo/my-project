# Game Design Marketplace

A dual-compatible plugin Marketplace for Claude Code and Codex. It publishes
two independently installable plugins with one canonical skill each.

| Plugin | Purpose |
|---|---|
| `game-design-skill` | Source-grounded general game design methods distilled from Claude Code Game Studios |
| `ai-native-game-design` | Source-aware design and review methods for gameplay that uses generative AI at runtime |

Install either plugin or both. Neither plugin requires the other at runtime.

## Plugins

### Game Design Skill

[`game-design-skill`](plugins/game-design-skill) distills reusable game-design
methodology from
[`Donchitos/Claude-Code-Game-Studios`](https://github.com/Donchitos/Claude-Code-Game-Studios)
(CCGS) into a focused skill for Claude Code and Codex.

CCGS provides the primary game-design roles, workflows, review procedures, and
document templates. Selected upstream files are preserved verbatim under the
MIT license, pinned to a fixed commit, hashed, and mapped in
`provenance/upstream-lock.json`.

The plugin supports concept and pillar development, system decomposition,
system GDD authoring, balance and economy analysis, prototypes and playtests,
UX and accessibility work, scope control, design-change propagation, and
single- or cross-document design review. It is genre-agnostic; genre names
appear as project inputs and examples rather than packaged genre guides.

### AI-Native Game Design

[`ai-native-game-design`](plugins/ai-native-game-design) is a standalone
specialist plugin for games in which runtime AI interprets player expression,
generates content or rules, adjudicates outcomes, or sustains intelligent
characters and relationships.

It covers product and feature classification, removal tests, player-AI
interface contracts, bounded generation, deterministic game-state authority,
legibility, companion and multi-agent society topology, layered memory,
authored open-narrative milestones, offline NPC autonomy, character continuity,
failure recovery, safety and privacy requirements, prototypes, playtests, and
AI-native design reviews.

Its core method is a repository-authored synthesis of practitioner evidence
from Tencent Game Institute's *Chuguang* EP.01 and EP.02 recaps. The sources
are treated as practitioner evidence, not as peer-reviewed research, industry
standards, model benchmarks, or proof of player or market effects.

## Repository contract

- Publish exactly two independently installable plugins:
  `game-design-skill` and `ai-native-game-design`.
- Keep exactly one canonical skill body inside each plugin.
- Keep both plugins self-contained; neither may reference files inside the
  other plugin.
- Preserve exact CCGS upstream text only inside `game-design-skill` under
  `references/upstream-*.md`.
- Keep repository-authored synthesis separate from verbatim upstream records
  and label practitioner evidence independently from research authority.
- Put Claude Code and Codex compatibility behavior in each canonical
  `SKILL.md`, not in duplicated product-specific skill bodies.
- Cite authoritative supplements instead of inventing theory, thresholds, or
  platform behavior.

## Install

Add the Marketplace once, then install either plugin or both.

### Claude Code

```powershell
claude plugin marketplace add https://github.com/JupiterTheWarlock/game-design-skill
claude plugin install game-design-skill@game-design-skill --scope user
claude plugin install ai-native-game-design@game-design-skill --scope user
claude plugin list
```

### Codex

```powershell
codex plugin marketplace add https://github.com/JupiterTheWarlock/game-design-skill
codex plugin add game-design-skill@game-design-skill
codex plugin add ai-native-game-design@game-design-skill
codex plugin list --marketplace game-design-skill
```

## Install from a local clone

Replace `<repo>` with the absolute path to this checkout.

### Claude Code

```powershell
claude plugin marketplace add "<repo>" --scope local
claude plugin install game-design-skill@game-design-skill --scope local
claude plugin install ai-native-game-design@game-design-skill --scope local
claude plugin list
```

### Codex

```powershell
codex plugin marketplace add "<repo>"
codex plugin add game-design-skill@game-design-skill
codex plugin add ai-native-game-design@game-design-skill
codex plugin list --marketplace game-design-skill
```

## Validate

```powershell
python scripts/verify_repository.py
python scripts/check_links.py
python C:\Users\GJM258\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins/game-design-skill/skills/game-design-skill
python C:\Users\GJM258\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins/ai-native-game-design/skills/ai-native-game-design
python C:\Users\GJM258\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins/game-design-skill
python C:\Users\GJM258\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins/ai-native-game-design
claude plugin validate . --strict
```

Both skills use progressive disclosure. Their `SKILL.md` files contain the
routing and operational contracts; detailed sources load only when the current
task needs them.

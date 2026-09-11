# Verification

The fixtures and cases in this directory exercise the independently installed
Marketplace plugins rather than importing repository skill bodies directly.

## Static checks

```powershell
python scripts\verify_repository.py
python scripts\check_links.py
python C:\Users\GJM258\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\game-design-skill\skills\game-design-skill
python C:\Users\GJM258\.codex\skills\.system\skill-creator\scripts\quick_validate.py plugins\ai-native-game-design\skills\ai-native-game-design
python C:\Users\GJM258\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\game-design-skill
python C:\Users\GJM258\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\ai-native-game-design
claude plugin validate . --strict
claude plugin validate plugins\game-design-skill --strict
claude plugin validate plugins\ai-native-game-design --strict
```

## Optional real installed-skill cases

```powershell
python scripts\run_validation_case.py codex concept-and-pillars
python scripts\run_validation_case.py claude system-gdd
python scripts\run_validation_case.py codex cross-gdd-review --timeout-seconds 420
python scripts\run_validation_case.py codex ai-native-review --timeout-seconds 420
python scripts\capture_install_evidence.py
python scripts\restore_test_environment.py
python scripts\analyze_validation.py
```

The concept, system-GDD, and cross-GDD cases exercise
`game-design-skill`. The AI-native case exercises
`ai-native-game-design`. Installation evidence compares each canonical
`SKILL.md` with its Claude Code and Codex cache copy.

`fixtures/ai-npc-concept.md` is the raw concept used for the isolated EP.02
forward test. It exercises NPC topology, social substrate, narrative
milestones, memory lifecycle, offline autonomy, scene-relative intelligence,
participation scaffolds, and interaction boundaries without embedding an
expected answer.

The committed raw model transcripts predate the two-plugin split and are
retained as historical evidence. They are not counted by the current
`validation-summary.json`; rerun the cases after installing the relevant
plugin when a fresh behavioral release gate is required.

Raw stdout, stderr, CLI versions, elapsed times, and deterministic assertions
are stored under `verification/results/`. The final Codex cross-GDD response
emitted both `agent_message` and `turn.completed`; its process later hung while
shutting down an unrelated user MCP connection and was terminated by the
wrapper timeout. Both the completed protocol evidence and non-clean process
exit are retained rather than conflated.

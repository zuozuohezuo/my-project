# Provenance and source use

## Authority order

Use sources in this order:

1. The user's explicit decisions and current project artifacts.
2. Vendored files from `Donchitos/Claude-Code-Game-Studios` at commit
   `984023ddac0d5e27624f2baacde6105e45de375f`.
3. Primary papers, original authors, official institutions, and current
   platform documentation listed in `authoritative-sources.md`.
4. Clearly labelled practitioner evidence listed in
   `authoritative-sources.md`.
5. Clearly labelled design proposals or assumptions made for the current task.

Do not let a general reference override a project-specific rule unless the
user is explicitly revising that rule.

## Vendored files

Every `upstream-*.md` file in this directory is copied byte-for-byte from the
Git object named in `provenance/upstream-lock.json` at the repository root.
Each lock entry records:

- repository and fixed commit;
- upstream path and full-file line range;
- destination path;
- SHA-256 of the Git blob and vendored file;
- status (`verbatim`);
- the reason it is included.

The canonical `SKILL.md` is an adapted compatibility and routing layer. It is
not represented as verbatim upstream text. Its adaptations are limited to:

- removing dependency on Claude-specific tool calls, models, studio agents,
  fixed project paths, and session-state machinery;
- selecting which complete upstream files to read for a task;
- adding source-authority, licensing, and claim-safety rules;
- allowing both Claude Code and Codex to use one canonical skill body.

## Citation behavior

When a user requests provenance or a formal design artifact, cite the vendored
reference filename and, when useful, the original GitHub blob URL from the lock
file. For an external framework, cite the primary or institutional URL in
`authoritative-sources.md`.

Do not describe a passage as a verbatim quotation unless it is actually quoted
without changes. Do not describe upstream heuristics as independently proven
research merely because the upstream file names a theory.

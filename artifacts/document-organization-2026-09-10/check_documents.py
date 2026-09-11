"""Check authored local Markdown links and document migration coverage."""
from pathlib import Path
import json
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
paths = sorted(list(ROOT.glob('*.md')) + list((ROOT / 'docs').rglob('*.md')) + [ROOT / 'artifacts/README.md'])
link = re.compile(r'!?\[[^\]\n]*\]\(([^\)\n]+)\)')
missing = []
links_checked = 0
for path in paths:
    text = path.read_text(encoding='utf-8-sig')
    text = re.sub(r'^```[^\n]*\n.*?^```[^\n]*$', '', text, flags=re.M | re.S)
    for target in link.findall(text):
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
            continue
        raw = unquote(target.strip('<>').split('#', 1)[0])
        if not raw:
            continue
        resolved = (path.parent / raw).resolve()
        links_checked += 1
        if not resolved.exists():
            missing.append({'source': path.relative_to(ROOT).as_posix(), 'target': target})
manifest = json.loads((OUT / 'migration.json').read_text(encoding='utf-8'))
migration_errors = []
for record in manifest['moves']:
    if (ROOT / record['old']).exists() or not (ROOT / record['new']).exists():
        migration_errors.append(record['old'])
ui = (ROOT / 'src/dynasty/ui/main_window.py').read_text(encoding='utf-8')
runtime_path_ok = 'project_root() / "docs" / "00_项目总览" / "待确认事项.md"' in ui and (ROOT / 'docs/00_项目总览/待确认事项.md').is_file()
report = {'date':'2026-09-10', 'markdown_files':len(paths), 'local_links_checked':links_checked, 'missing_links':missing, 'moves_checked':len(manifest['moves']), 'migration_errors':migration_errors, 'runtime_document_path_ok':runtime_path_ok}
(OUT / 'document-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True,indent=2))
raise SystemExit(1 if missing or migration_errors or not runtime_path_ok else 0)

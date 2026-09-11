"""One-off document inventory, backup, and link migration. Moves use PowerShell."""
from pathlib import Path
import hashlib
import json
import os
import re
import sys
import zipfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
GROUPS = {
    "00_项目总览": ["待确认事项.md"],
    "01_系统设计/M01_人物能力与健康": ["皇帝属性与技能.md"],
    "01_系统设计/M02_性格与个人追求": ["人物性格状态与动机_建议.md"],
    "01_系统设计/M03_回合行动": ["M03_行动点与时间_建议.md", "M03_活动目录_候选.md", "M03_三阶段行动_试玩说明.md"],
    "01_系统设计/M04_朝廷官员": ["M04_朝廷官员与制度.md"],
    "01_系统设计/M05_M06_财政与地方经济": ["皇帝资源与财政权力.md", "M05_M06_财政与地方经济框架.md", "M06_县级属性.md", "M06_生产经营.md", "M06_钱粮物资与消费.md", "M06_人口职业与收入.md"],
    "02_开发实施": ["M05_M06_首版实现计划.md"],
    "03_试玩与验收": ["M06_县级经济_试玩说明.md", "M06_县级经济_验收记录.md", "M06_人口v2_验收记录.md", "验收记录.md"],
    "04_历史研究": ["史料_地图行政区.md", "史料_内帑与国库.md", "史料_人物官制法令.md", "M04_机构官职_明弘治参考.md", "地理抽检_种子1500.json"],
    "90_归档": ["框架草案_v0.16_归档.md", "技术方案_Godot候选_归档.md"],
    "90_归档/M03_旧版方案": ["M03_回合行动与事件.md", "M03_试玩说明.md"],
}
MOVES = {f"docs/{name}": f"docs/{group}/{name}" for group, names in GROUPS.items() for name in names}
for name in ["M03_验收记录.md", "M03_三阶段验收记录.md"]:
    MOVES[f"artifacts/{name}"] = f"docs/03_试玩与验收/{name}"
LINK = re.compile(r"(!?\[[^\]\n]*\]\()([^\)\n]+)(\))")


def local_target(raw, old):
    if raw.startswith(("#", "http:", "https:", "mailto:", "codex:", "data:")):
        return None
    raw = raw.strip("<>")
    path, sep, anchor = raw.partition("#")
    path = unquote(path)
    target = (ROOT / old).parent / path
    if not target.exists() and (ROOT / path).exists():
        target = ROOT / path
    try:
        rel = target.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None
    return rel, (sep + anchor)


def rewrite(text, old, new):
    def replace(match):
        found = local_target(match[2], old)
        if found is None:
            return match[0]
        rel, suffix = found
        target = MOVES.get(rel, rel)
        new_rel = os.path.relpath(ROOT / target, (ROOT / new).parent).replace("\\", "/")
        return match[1] + new_rel + suffix + match[3]
    text = LINK.sub(replace, text)
    for src, dst in MOVES.items():
        text = text.replace(f"`{src}`", f"`{dst}`")
    return text


def prepare():
    manifest = OUT / "migration.json"
    if manifest.exists():
        raise SystemExit("Migration was already prepared; refusing to replace the backup.")
    for src, dst in MOVES.items():
        if not (ROOT / src).is_file() or (ROOT / dst).exists():
            raise SystemExit(f"Invalid move: {src} -> {dst}")
    documents = list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md"))
    documents += [ROOT / "artifacts/M03_验收记录.md", ROOT / "artifacts/M03_三阶段验收记录.md", ROOT / "artifacts/M03_before/README.md"]
    changes = []
    for path in documents:
        old = path.relative_to(ROOT).as_posix()
        new = MOVES.get(old, old)
        original = path.read_text(encoding="utf-8-sig")
        revised = rewrite(original, old, new)
        if revised != original or old != new:
            changes.append({"old": old, "new": new, "content": revised})
    ui = ROOT / "src/dynasty/ui/main_window.py"
    ui_text = ui.read_text(encoding="utf-8")
    before = 'project_root() / "docs" / "待确认事项.md"'
    after = 'project_root() / "docs" / "00_项目总览" / "待确认事项.md"'
    assert ui_text.count(before) == 1
    changes.append({"old": ui.relative_to(ROOT).as_posix(), "new": ui.relative_to(ROOT).as_posix(), "content": ui_text.replace(before, after)})
    backup_paths = {item["old"] for item in changes} | set(MOVES)
    with zipfile.ZipFile(OUT / "before-organization.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for rel in sorted(backup_paths):
            archive.write(ROOT / rel, rel)
    records = [{"old": src, "new": dst, "sha256_before": hashlib.sha256((ROOT / src).read_bytes()).hexdigest()} for src, dst in MOVES.items()]
    manifest.write_text(json.dumps({"date": "2026-09-10", "moves": records, "rewrites": changes}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prepared {len(records)} moves; backup saved; {len(changes)} documents/code paths staged.")


def apply():
    payload = json.loads((OUT / "migration.json").read_text(encoding="utf-8"))
    for item in payload["moves"]:
        assert not (ROOT / item["old"]).exists()
        assert hashlib.sha256((ROOT / item["new"]).read_bytes()).hexdigest() == item["sha256_before"]
    for item in payload["rewrites"]:
        (ROOT / item["new"]).write_text(item["content"], encoding="utf-8")
    print("Moved file contents verified; links and runtime document path updated.")


if __name__ == "__main__":
    {"prepare": prepare, "rewrite": apply}[sys.argv[1]]()

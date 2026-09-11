"""Offline integrity audit for the research pack; does not certify historical truth.

Run: uv run python tools/verify_history_people_laws.py
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data/history"


def load(name):
    return json.loads((HISTORY / name).read_text(encoding="utf-8"))


def main():
    failures = []
    sources = load("sources_people_laws.json")["records"]
    source_by_id = {s["id"]: s for s in sources}
    if len(source_by_id) != len(sources):
        failures.append("Duplicate source IDs")
    texts = {}
    for source in sources:
        for field, checksum in (("local_path", "sha256"), ("text_path", "text_sha256")):
            if not source.get(field):
                failures.append(f"Missing source path: {source['id']}/{field}")
                continue
            path = ROOT / source[field]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source[checksum]:
                failures.append(f"Source checksum mismatch: {source['id']}/{field}")
        if source.get("text_path"):
            texts[source["id"]] = re.sub(r"\s+", "", (ROOT / source["text_path"]).read_text(encoding="utf-8"))
    counts, all_ids, evidence_count = {}, set(), 0
    for filename in ("people.json", "offices.json", "laws.json"):
        payload = load(filename)
        if payload["metadata"]["baseline_is_provisional"] is not True:
            failures.append(f"Baseline silently treated as user-approved: {filename}")
        if payload["metadata"]["simulation_effects_enabled"] is not False:
            failures.append(f"History accidentally enables simulation: {filename}")
        counts[filename] = len(payload["records"])
        for record in payload["records"]:
            if record["id"] in all_ids:
                failures.append(f"Duplicate catalogue ID: {record['id']}")
            all_ids.add(record["id"])
            for field in ("name", "source_ids", "verification_status", "period", "evidence"):
                if not record.get(field):
                    failures.append(f"Missing field {field}: {record['id']}")
            for source_id in record["source_ids"]:
                if source_id not in source_by_id:
                    failures.append(f"Unresolved source {source_id}: {record['id']}")
            for item in record["evidence"]:
                evidence_count += 1
                raw = texts.get(item["source_id"], "")
                if re.sub(r"\s+", "", item["anchor"]) not in raw or item["excerpt"] not in raw:
                    failures.append(f"Evidence no longer matches source: {record['id']}/{item['source_id']}")
    people = {record["id"]: record for record in load("people.json")["records"]}
    offices = {record["id"] for record in load("offices.json")["records"]}
    for record in people.values():
        if record["personality_scores"] is not None:
            failures.append(f"Invented personality scores: {record['id']}")
        for office_id in record["office_ids"]:
            if office_id not in offices:
                failures.append(f"Unresolved office reference: {record['id']}/{office_id}")
    # Known chronology hazards independently checked against the saved year table.
    expected = {"ma_wensheng": "ming_office_war_minister", "dai_shan": "ming_office_nanjing_justice_minister",
                "min_gui": "ming_office_censor_left", "si_zhong": "ming_office_censor_right"}
    for name, office in expected.items():
        if people["ming_person_" + name]["office_ids"] != [office]:
            failures.append(f"1500 first-month role shifted to a later office: {name}")
    law_records = {record["id"]: record for record in load("laws.json")["records"]}
    if law_records["ming_law_wenxing_1500"]["effective_at_baseline"] is not False:
        failures.append("February 1500 revision is incorrectly effective at first-month baseline")
    report = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "status": "passed" if not failures else "failed", "source_count": len(sources),
              "artifact_count": len(sources) * 2, "record_counts": counts,
              "evidence_anchor_count": evidence_count, "failures": failures,
              "scope": "本地文件校验和、来源引用、正文锚点、基础时间边界与缺省属性；不替代影印本校勘及史学审读。",
              "known_pending": ["1500精确开局旬与朝代基准由用户确认", "佀钟姓名异体的影印本复校",
                                "各地官员名册与编额", "洪武律与弘治问刑条例逐条版本校勘",
                                "官职名录中未逐项实现的制度差遣与实际权限"]}
    (HISTORY / "verification_people_laws.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

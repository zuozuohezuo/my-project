"""Audit the complete research pack offline without certifying historical truth.

Usage: uv run python tools/verify_history.py
Writes artifacts/history-audit.json; exits 1 for damaged files or broken data
contracts. Documented uncertainty is reported as limited, never as corruption.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = ("regions", "prefectures", "counties", "people", "offices", "laws")
EXPECTED_REGIONS = {
    "beizhili", "nanzhili", "shandong", "shanxi", "henan", "shaanxi",
    "sichuan", "jiangxi", "huguang", "zhejiang", "fujian", "guangdong",
    "guangxi", "yunnan", "guizhou",
}


def compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def clean_geography_text(value: str) -> str:
    value = re.sub(r"\{\{YL\|([^{}]+)\}\}", r"\1", value)
    value = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    return value.strip().replace("'''", "")


class Audit:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.failures: list[dict] = []
        self.check_counts: Counter = Counter()
        self.files: dict[str, dict] = {}
        self.source_texts: dict[str, str] = {}
        self.sources: dict[str, dict] = {}
        self.payloads: dict[str, dict] = {}
        self.record_counts: dict[str, int] = {}

    def check(self, condition: bool, group: str, target: str, requirement: str) -> bool:
        self.check_counts[group] += 1
        if not condition:
            self.failures.append({"group": group, "target": target, "requirement": requirement})
        return condition

    def load(self, relative: str):
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def verify_file(self, relative: str, expected_hash: str, source_id: str,
                    expected_bytes: int | None = None) -> Path | None:
        path = (self.root / relative).resolve()
        if not self.check(path.is_relative_to(self.root.resolve()), "source_paths", source_id,
                          "Download path must remain inside the project"):
            return None
        if not self.check(path.is_file(), "source_paths", source_id, f"Missing file: {relative}"):
            return None
        content = path.read_bytes()
        actual = hashlib.sha256(content).hexdigest()
        valid_hash = bool(re.fullmatch(r"[a-fA-F0-9]{64}", expected_hash or ""))
        self.check(valid_hash and actual == expected_hash.lower(), "source_hashes", source_id,
                   f"SHA-256 must match {relative}")
        if expected_bytes is not None:
            self.check(len(content) == expected_bytes, "source_sizes", source_id,
                       f"Byte count must match {relative}")
        self.files[relative] = {"path": relative, "sha256": actual, "bytes": len(content)}
        return path

    def verify_sources(self) -> None:
        manifests = sorted((self.root / "data/history").glob("sources_*.json"))
        self.check(bool(manifests), "source_manifests", "data/history", "At least one source manifest must exist")
        for manifest in manifests:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            for source in payload["records"]:
                source_id = source["id"]
                self.check(source_id not in self.sources, "unique_ids", source_id, "Source IDs must be globally unique")
                self.sources[source_id] = source
                self.check(bool(source.get("url")), "source_metadata", source_id, "Source URL is required")
                self.check(bool(source.get("license") or source.get("license_note")), "source_metadata", source_id, "License description is required")
                self.check(bool(source.get("downloaded_at") or source.get("accessed_at")), "source_metadata", source_id, "Retrieval date is required")
                self.check(bool(source.get("local_path")), "source_metadata", source_id, "Local download path is required")
                if source.get("local_path"):
                    self.verify_file(source["local_path"], source.get("sha256", ""), source_id, source.get("bytes"))
                if source.get("text_path"):
                    path = self.verify_file(source["text_path"], source.get("text_sha256", ""), source_id + "/text")
                    if path:
                        self.source_texts[source_id] = path.read_text(encoding="utf-8")
        fonts = self.load("assets/fonts/sources.json")
        for index, source in enumerate(fonts):
            label = "font_source_" + str(index + 1)
            self.check(bool(source.get("url") and source.get("license") and source.get("downloaded_at")),
                       "font_metadata", label, "Font URL, license and retrieval date are required")
            self.verify_file(source["local_path"], source.get("sha256", ""), label, source.get("bytes"))
        self.check(any(x.get("local_path", "").endswith(".ttf") for x in fonts), "font_metadata", "fonts", "A font binary must be recorded")
        self.check(any(x.get("local_path", "").endswith("OFL.txt") for x in fonts), "font_metadata", "fonts", "Font license must be recorded")
        self.font_source_count = len(fonts)

    def verify_catalogs(self) -> dict[str, dict]:
        records = {}
        for name in CATALOGS:
            payload = self.load(f"data/history/{name}.json")
            self.payloads[name] = payload
            self.record_counts[name] = len(payload["records"])
            self.check(bool(payload["records"]), "catalog_structure", name, "Catalogue must contain records")
            for record in payload["records"]:
                record_id = record["id"]
                self.check(record_id not in records, "unique_ids", record_id, "Record IDs must be globally unique")
                records[record_id] = record
                for field in ("name", "source_ids", "verification_status"):
                    self.check(bool(record.get(field)), "catalog_structure", record_id, f"Required field: {field}")
                for source_id in record.get("source_ids", []):
                    self.check(source_id in self.sources, "source_references", record_id, f"Source must resolve: {source_id}")
                if name in ("regions", "prefectures", "counties"):
                    excerpt = record.get("source_excerpt", "")
                    self.check(bool(excerpt), "geography_evidence", record_id, "Geography source excerpt is required")
                    texts = [clean_geography_text(self.source_texts[x]) for x in record.get("source_ids", []) if x in self.source_texts]
                    self.check(any(compact(excerpt) in compact(text) for text in texts), "geography_evidence", record_id,
                               "Excerpt must occur in one of its archived source transcriptions")
        geography = self.payloads["prefectures"]["records"] + self.payloads["counties"]["records"]
        for row in geography:
            label = row["id"]
            parent_id = row.get("parent_id")
            self.check(parent_id in records, "parent_references", label, "Parent ID must resolve")
            self.check(row.get("region_id") in EXPECTED_REGIONS, "parent_references", label, "Region ID must resolve to one of the 15 regions")
            if parent_id in records and parent_id not in EXPECTED_REGIONS:
                self.check(records[parent_id].get("region_id") == row["region_id"], "parent_references", label,
                           "Parent and child must belong to the same region")
            self.check(row.get("active_in_scenario") is False, "historical_scope", label,
                       "Unreconstructed cross-period records must remain reference-only")
            self.check(row.get("temporal_status") == "cross_period_reference_not_1500_verified", "historical_scope", label,
                       "Cross-period geography must not claim to be a verified 1500 snapshot")
            self.check(bool(row.get("parentage_status")), "historical_scope", label, "Parentage qualification is required")
            chain, cursor = set(), label
            while cursor in records and records[cursor].get("parent_id"):
                if cursor in chain:
                    self.check(False, "hierarchy_cycles", label, "Administrative hierarchy must be acyclic")
                    break
                chain.add(cursor)
                cursor = records[cursor]["parent_id"]
            else:
                self.check(True, "hierarchy_cycles", label, "Administrative hierarchy must be acyclic")
        return records

    def verify_geography(self) -> None:
        regions = {r["id"]: r for r in self.payloads["regions"]["records"]}
        self.check(set(regions) == EXPECTED_REGIONS, "map_regions", "regions", "Exactly two capitals and thirteen provincial regions are required")
        for name in ("regions", "prefectures", "counties"):
            meta = self.payloads[name]["metadata"]
            self.check(meta.get("historical_boundaries_available") is False, "historical_scope", name, "Unverified historical boundaries must remain marked unavailable")
            self.check(bool(meta.get("historical_scope") and meta.get("data_warning")), "historical_scope", name, "Geography must disclose cross-period scope and data warning")
        geo = self.load("data/history/ming_regions.geojson")
        self.check(geo.get("type") == "FeatureCollection" and len(geo.get("features", [])) == 15,
                   "map_geometry", "ming_regions.geojson", "Expected 15-feature GeoJSON FeatureCollection")
        feature_ids = set()
        city_source = self.sources.get("natural_earth_cities", {})
        cities = self.load(city_source["local_path"])
        city_lookup = {f["properties"]["name"]: f["geometry"]["coordinates"] for f in cities["features"]}
        for feature in geo.get("features", []):
            properties, geometry = feature["properties"], feature["geometry"]
            region_id = properties.get("region_id")
            self.check(region_id not in feature_ids, "map_regions", str(region_id), "Map feature region IDs must be unique")
            feature_ids.add(region_id)
            if not self.check(region_id in regions, "map_regions", str(region_id), "Map region must resolve"):
                continue
            region = regions[region_id]
            self.check(geometry.get("type") == "Point", "map_geometry", region_id, "Current map uses declared reference points")
            coordinates = geometry.get("coordinates", [])
            valid = len(coordinates) == 2 and all(isinstance(n, (int, float)) and math.isfinite(n) for n in coordinates)
            self.check(valid and -180 <= coordinates[0] <= 180 and -90 <= coordinates[1] <= 90,
                       "map_geometry", region_id, "Coordinates must be finite WGS84 longitude/latitude")
            self.check(coordinates == [region.get("longitude"), region.get("latitude")], "map_geometry", region_id, "Region catalogue and GeoJSON coordinates must agree")
            self.check(coordinates == city_lookup.get(region.get("modern_reference_city")), "map_evidence", region_id,
                       "Coordinate must exactly match the archived Natural Earth reference city")
            expected_status = "modern_city_reference_point_not_historical_seat_survey"
            self.check(properties.get("geometry_status") == region.get("geometry_status") == expected_status,
                       "historical_scope", region_id, "Reference points must not claim historical boundaries or surveyed seats")
            self.check(bool(region.get("coordinate_note")) and region.get("temporal_status") == "1500_provisional_region_framework",
                       "historical_scope", region_id, "Provisional regional framework and coordinate qualification are required")
            for source_id in properties.get("source_ids", []):
                self.check(source_id in self.sources, "source_references", region_id, "Map source must resolve: " + source_id)
        self.check(feature_ids == EXPECTED_REGIONS, "map_regions", "map_features", "Every region must appear exactly once")
        land = self.load("data/history/map_land.geojson")
        self.check(land.get("metadata", {}).get("geometry_status") == "modern_land_reference_not_ming_territory",
                   "historical_scope", "map_land.geojson", "Land background must not claim Ming sovereignty")
        self.check("1580" in self.sources.get("ming_map_1580", {}).get("historical_scope", ""),
                   "historical_scope", "ming_map_1580", "Later map must retain its actual period")

    def verify_people_laws(self) -> None:
        evidence_count = 0
        for name in ("people", "offices", "laws"):
            payload = self.payloads[name]
            self.check(payload["metadata"].get("baseline_is_provisional") is True,
                       "historical_scope", name, "Baseline must remain provisional")
            self.check(payload["metadata"].get("simulation_effects_enabled") is False,
                       "simulation_separation", name, "Reference catalogue must not enable simulation")
            for row in payload["records"]:
                self.check(bool(row.get("period") and row.get("evidence")), "text_evidence", row["id"], "Period and evidence are required")
                for evidence in row.get("evidence", []):
                    evidence_count += 1
                    source_id = evidence.get("source_id")
                    self.check(source_id in row["source_ids"], "source_references", row["id"], "Evidence source must be declared in record source_ids")
                    source = compact(self.source_texts.get(source_id, ""))
                    anchor, excerpt = compact(evidence.get("anchor", "")), compact(evidence.get("excerpt", ""))
                    self.check(bool(anchor and excerpt) and anchor in source and excerpt in source,
                               "text_evidence", row["id"], "Anchor and excerpt must occur in archived text: " + str(source_id))
        people = {r["id"]: r for r in self.payloads["people"]["records"]}
        offices = {r["id"] for r in self.payloads["offices"]["records"]}
        for row in people.values():
            self.check(row.get("personality_scores") is None, "simulation_separation", row["id"], "Historical people must not acquire invented personality scores")
            for office_id in row.get("office_ids", []):
                self.check(office_id in offices, "office_references", row["id"], "Office reference must resolve: " + office_id)
        expected = {"ma_wensheng": "ming_office_war_minister", "dai_shan": "ming_office_nanjing_justice_minister",
                    "min_gui": "ming_office_censor_left", "si_zhong": "ming_office_censor_right"}
        for person, office in expected.items():
            self.check(people.get("ming_person_" + person, {}).get("office_ids") == [office],
                       "chronology_regressions", person, "1500 first-month role must not shift to a later appointment")
        laws = {r["id"]: r for r in self.payloads["laws"]["records"]}
        self.check(laws.get("ming_law_wenxing_1500", {}).get("effective_at_baseline") is False,
                   "chronology_regressions", "ming_law_wenxing_1500", "Second-month revision must not be effective in the first-month baseline")
        self.evidence_count = evidence_count

    def run(self) -> dict:
        try:
            self.verify_sources()
            self.verify_catalogs()
            self.verify_geography()
            self.verify_people_laws()
        except Exception as exc:
            self.failures.append({"group": "audit_execution", "target": "research_pack",
                                  "requirement": f"Audit could not finish: {type(exc).__name__}: {exc}"})
        return {
            "schema_version": 1, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "failed" if self.failures else "passed_with_limitations",
            "integrity_status": "failed" if self.failures else "passed",
            "historical_accuracy_status": "limited",
            "scope": "离线核验文件、哈希、原文锚点、目录关系、地图坐标来源及已知时点边界；不把资料结构完整等同历史事实全部准确。",
            "source_count": len(self.sources), "font_source_count": getattr(self, "font_source_count", 0),
            "verified_local_file_count": len(self.files), "record_counts": self.record_counts,
            "text_evidence_count": getattr(self, "evidence_count", 0),
            "check_counts": dict(self.check_counts), "failures": self.failures,
            "limited": [
                {"area": "geography", "status": "limited", "detail": "15点图为历史治所所在现代城市参考位置；1500年省界未复原，县制为跨明代原典索引。"},
                {"area": "map_reference", "status": "limited", "detail": "下载SVG实际为约1580年，未地理配准，不作为1500精确疆界。"},
                {"area": "transcription", "status": "limited", "detail": "原典转录存在异体字、OCR及未分类段落；见geography_extraction_review.json。"},
                {"area": "chronology", "status": "limited", "detail": "1500农历正月为临时工作基准，具体开局待用户确认；未实现闰月换算。"},
                {"area": "people_and_law", "status": "limited", "detail": "人物、官职与法令是已注明范围的基础资料，不是全国地方官与法律条款全集；需后续影印本校勘。"},
            ],
            "verified_files": list(self.files.values()),
        }


def main() -> None:
    report = Audit(ROOT).run()
    output = ROOT / "artifacts/history-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {key: report[key] for key in ("status", "source_count", "font_source_count", "verified_local_file_count", "record_counts", "text_evidence_count")}
    summary["failure_count"] = len(report["failures"])
    summary["report"] = output.relative_to(ROOT).as_posix()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report["failures"]:
        print(json.dumps(report["failures"], ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()

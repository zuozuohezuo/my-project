"""Download public historical geography sources and rebuild the reference catalog.

Run with ``uv run python tools/download_geography.py``. Existing source snapshots
are reused; use --refresh to fetch newer revisions, or --offline to verify/rebuild.
The catalog is deliberately NOT a reconstructed 1500 county boundary dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/history"
RAW = DATA / "raw/geography"
SOURCES: list[dict] = []
REGION_SPECS = [
    ("beizhili", "北直隶", "京師", "顺天府", "Beijing", 40),
    ("nanzhili", "南直隶", "南京", "应天府", "Nanjing", 40),
    ("shandong", "山东", "山東", "济南府", "Jinan", 41),
    ("shanxi", "山西", "山西", "太原府", "Taiyuan", 41),
    ("henan", "河南", "河南", "开封府", "Kaifeng", 42),
    ("shaanxi", "陕西", "陝西", "西安府", "Xian", 42),
    ("sichuan", "四川", "四川", "成都府", "Chengdu", 43),
    ("jiangxi", "江西", "江西", "南昌府", "Nanchang", 43),
    ("huguang", "湖广", "湖廣", "武昌府", "Wuhan", 44),
    ("zhejiang", "浙江", "浙江", "杭州府", "Hangzhou", 44),
    ("fujian", "福建", "福建", "福州府", "Fuzhou", 45),
    ("guangdong", "广东", "廣東", "广州府", "Guangzhou", 45),
    ("guangxi", "广西", "廣西", "桂林府", "Guilin", 45),
    ("yunnan", "云南", "雲南", "云南府", "Kunming", 46),
    ("guizhou", "贵州", "貴州", "贵州宣慰司城（今贵阳）", "Guiyang", 46),
]
TERMS = "https://www.naturalearthdata.com/about/terms-of-use/"
NE_BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/"
COMMONS_PAGE = "https://commons.wikimedia.org/wiki/File:Ming_Empire_cca_1580_(en).svg"
COMMONS_API = "https://commons.wikimedia.org/w/api.php?" + urlencode({
    "action": "query", "format": "json", "prop": "imageinfo",
    "iiprop": "url|extmetadata|timestamp|sha1", "titles": "File:Ming Empire cca 1580 (en).svg",
})
SKCHAR_URL = "https://zh.wikisource.org/w/api.php?" + urlencode({
    "action": "parse", "format": "json", "contentmodel": "wikitext",
    "text": "{{SKchar|392}}", "prop": "text",
})


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(name: str, url: str, *, offline: bool, refresh: bool) -> Path:
    path = RAW / name
    if path.exists() and not refresh:
        return path
    if offline:
        raise FileNotFoundError(f"Offline source missing: {path}")
    RAW.mkdir(parents=True, exist_ok=True)
    error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "DynastyFrameworkResearch/0.1 (public historical source archive)"})
            with urlopen(request, timeout=90) as response:
                body = response.read()
            path.write_bytes(body)
            return path
        except Exception as exc:
            error = exc
            time.sleep(attempt + 1)
    raise RuntimeError(f"Unable to fetch {url}") from error


def register(source_id: str, title: str, url: str, path: Path, license_name: str,
             license_url: str, **details: object) -> dict:
    record = {
        "id": source_id, "title": title, "url": url,
        "local_path": path.relative_to(ROOT).as_posix(),
        "downloaded_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size, "license": license_name,
        "license_url": license_url, "verification_status": "downloaded_hash_verified",
        **details,
    }
    SOURCES.append(record)
    return record


def load_wikisource(volume: int, siku: bool, flags: dict) -> str:
    prefix = "mingshi_siku" if siku else "mingshi"
    title = f"明史 (四庫全書本)/卷{volume:03}" if siku else f"明史/卷{volume}"
    url = "https://zh.wikisource.org/w/api.php?" + urlencode({
        "action": "query", "prop": "revisions", "rvprop": "content|ids|timestamp",
        "rvslots": "main", "format": "json", "titles": title,
    })
    path = fetch(f"{prefix}_{volume}_api.json", url, **flags)
    page = next(iter(json.loads(path.read_bytes())["query"]["pages"].values()))
    revision = page["revisions"][0]
    text = revision["slots"]["main"]["*"]
    text_path = RAW / f"{prefix}_{volume}.wikitext"
    text_path.write_text(text, encoding="utf-8")
    register(
        f"{prefix}_{volume}", title, f"https://zh.wikisource.org/w/index.php?oldid={revision['revid']}",
        path, "Public-domain ancient work; Wikisource editorial/transcription contributions CC BY-SA 4.0",
        "https://creativecommons.org/licenses/by-sa/4.0/", download_url=url,
        page_revision_id=revision["revid"], source_revision_at=revision["timestamp"],
        text_path=text_path.relative_to(ROOT).as_posix(),
        text_sha256=hashlib.sha256(text_path.read_bytes()).hexdigest(),
        historical_scope="Retrospective Ming dynasty geography; multiple dates, NOT a 1500 snapshot",
        attribution=f"《{title}》张廷玉等；维基文库贡献者，原文与校录署名通过固定版本页面及页面历史提供。",
    )
    return text


try:
    from opencc import OpenCC
    CONVERTER = OpenCC("t2s")
except ImportError:
    CONVERTER = None


def simplify(text: str) -> str:
    return CONVERTER.convert(text) if CONVERTER else text


def clean(text: str) -> str:
    text = re.sub(r"\{\{YL\|([^{}]+)\}\}", r"\1", text)
    text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip().replace("'''", "")


def comparable(text: str) -> str:
    # Only variant characters; do not normalize unrelated names or dates.
    text = text.replace("{{SKchar|392}}", "𥔲")
    return simplify(text).translate(str.maketrans("寜寳懐徳陜甯澂邱厯夀呉鳯隂髙㝎", "宁宝怀德陕宁澄丘历寿吴凤阴高定"))


def extract(texts: dict[int, str], siku: dict[int, str]) -> tuple[list, list, list]:
    units: list[dict] = []
    counties: list[dict] = []
    leftovers: list[dict] = []
    unique: dict[tuple, dict] = {}
    regions = {spec[2]: spec[0] for spec in REGION_SPECS}
    admin_suffix = r"(?:軍民指揮使司|都指揮使司|宣慰使司|宣慰司|宣撫司|安撫司|招討司|長官司|軍民府|御夷府|御夷州|府|州|衛)"

    for volume, text in texts.items():
        comparable_siku = comparable(siku[volume])
        region_id = None
        prefecture = None
        substate = None
        section_unit = None
        just_heading = False

        def add(name: str, kind: str, parent: str | None, evidence: str, line_no: int, method: str) -> dict:
            key = (region_id, parent, name, kind)
            if key in unique:
                row = unique[key]
                if evidence:
                    row["source_excerpt"] = evidence
                return row
            keytext = "|".join(str(x) for x in key)
            prefix = "county" if kind == "county" else "unit"
            row = {
                "id": f"{region_id}_{prefix}_{hashlib.sha256(keytext.encode()).hexdigest()[:10]}",
                "name": simplify(name if kind != "county" or name.endswith("縣") else name + "縣"),
                "name_original": name,
                "type": kind, "region_id": region_id, "parent_id": parent or region_id,
                "source_ids": [f"mingshi_{volume}", f"mingshi_siku_{volume}"],
                "source_location": f"明史/卷{volume}，原始转录第 {line_no} 行",
                "source_line": line_no,
                "source_excerpt": evidence,
                "extraction_method": method,
                "verification_status": "transcribed_reference_temporal_review_required",
                "second_transcription_name_match": comparable(name) in comparable_siku,
                "temporal_status": "cross_period_reference_not_1500_verified",
                "scenario_year": 1500,
                "active_in_scenario": False,
                "parentage_status": "source_sequence_and_direction_marker; temporal_review_required",
                "longitude": None, "latitude": None,
            }
            row["later_era_mentions"] = sorted(set(re.findall(r"(?:正德|嘉靖|隆慶|萬曆|泰昌|天啓|崇禎)", evidence)))
            unique[key] = row
            (counties if kind == "county" else units).append(row)
            return row

        for line_no, rawline in enumerate(text.splitlines(), 1):
            line = clean(rawline)
            heading = re.match(r"^(={2,4})([^=]+)\1$", line)
            if heading:
                level, name = len(heading[1]), heading[2].strip()
                if level == 2:
                    region_id = regions.get(name[:2])
                    prefecture = substate = section_unit = None
                    just_heading = False
                    continue
                if not region_id:
                    continue
                name = name.split("元六番")[0]
                original_heading = name
                heading_corrections = {(41, "苛嵐州"): "岢嵐州", (46, "鄧州"): "鄧川州"}
                name = heading_corrections.get((volume, name), name)
                kind = "prefecture" if name.endswith("府") else "subprefecture" if name.endswith("州") else "military_or_native_office"
                parent = (prefecture or {}).get("id") if level == 4 else region_id
                section_unit = add(name, kind, parent, "", line_no, "wikisource_section_heading")
                if original_heading != name:
                    section_unit["source_heading_original"] = original_heading
                    section_unit["name_correction"] = "章节标题与正文不一致，名称据紧随正文及四库本对应州名校正。"
                if level == 3:
                    prefecture = section_unit
                    substate = section_unit if kind == "subprefecture" else None
                else:
                    substate = section_unit
                just_heading = True
                continue
            if not region_id or not line or line.startswith(("{{", "|", "__")):
                continue
            if just_heading and section_unit and line.startswith(section_unit["name_original"]):
                section_unit["source_excerpt"] = line
                section_unit["later_era_mentions"] = sorted(set(re.findall(r"(?:正德|嘉靖|隆慶|萬曆|泰昌|天啓|崇禎)", line)))
                just_heading = False
                continue
            if any(line.startswith(spec[2]) and "禹貢" in line[:12] for spec in REGION_SPECS):
                continue

            # Unheaded prefectures (notably Jiangxi) and inline subordinate states.
            inline = re.match(rf"^([\u3400-\u9fff]{{1,12}}?{admin_suffix})(?=\s|元|洪武|永樂|宣德|正統|景泰|天順|成化|弘治|正德|嘉靖|萬曆|崇禎|府[東西南北]|本|倚|[東西南北]+有|[東西南北]+臨|自|，有)", line)
            if inline:
                name = inline[1]
                # A county's location starts NAME + 府東/州東: the marker is
                # outside the name and must never turn e.g. 建昌縣 into 建昌府.
                tail = line[len(name):]
                if name.endswith(("府", "州")) and re.match(r"^[東西南北]+[。，]", tail):
                    inline = None
                else:
                    kind = "prefecture" if name.endswith("府") else "subprefecture" if name.endswith("州") else "military_or_native_office"
                    parent = region_id if kind == "prefecture" else (prefecture or {}).get("id", region_id)
                    row = add(name, kind, parent, line, line_no, "paragraph_administrative_suffix")
                    if kind == "prefecture":
                        prefecture, substate = row, None
                    elif kind == "subprefecture":
                        substate = row
                    continue

            county = re.match(r"^([\u3400-\u9fff]{1,5}?)[，\s]*(倚|[府州廳][，\s]*少?[東西南北]|[府州]治|元|本|嘉靖|成化|明玉珍)", line)
            if county:
                name, marker = county[1], county[2]
                if name.endswith(("司", "衛", "所", "州", "府")):
                    leftovers.append({"volume": volume, "region_id": region_id, "source_line": line_no, "text": line})
                    continue
                if marker.startswith("州"):
                    parent = (substate or prefecture or {}).get("id", region_id)
                else:
                    parent = (prefecture or {}).get("id", region_id)
                add(name, "county", parent, line, line_no, "paragraph_name_before_seat_or_relative_direction")
                continue
            leftovers.append({"volume": volume, "region_id": region_id, "source_line": line_no, "text": line})

    # The ordinary transcription has 南唐府; the same paragraph says 改曰南康府,
    # and the Siku anchor explicitly reads 南康府. Record, never silently conceal.
    for row in units:
        if row["region_id"] == "jiangxi" and row["name_original"] == "南唐府":
            row["name"] = "南康府"
            row["name_correction"] = "常规转录作南唐府，同段改曰南康府；四库本锚点南康府，显示名据此校正。"
            row["verification_status"] = "cross_transcription_name_corrected_temporal_review_required"
    corrections = {
        (40, "井徑"): "井陘", (40, "成安安"): "成安", (40, "徑"): "涇",
        (41, "教義"): "孝義", (42, "扶鳳"): "扶風",
        (44, "蒲江"): "浦江", (46, "柷嘉"): "𥔲嘉",
    }
    for row in counties:
        volume = int(row["source_ids"][0].split("_")[-1])
        corrected = corrections.get((volume, row["name_original"]))
        if corrected:
            row["name"] = simplify(corrected + "縣")
            row["name_corrected_original"] = corrected
            row["name_correction"] = "显示县名据同卷四库本县名及相邻说明校正；原转录与原文仍完整保留。"
            row["second_transcription_name_match"] = comparable(corrected) in comparable(siku[volume])
            row["verification_status"] = "cross_transcription_name_corrected_temporal_review_required"
            if corrected == "𥔲嘉":
                row["source_ids"].append("siku_character_392")
    # Explicit direct subordination outranks where a paragraph happened to be
    # placed by the Wikisource editor. This is the source's reference period,
    # not a claim about the 1500 arrangement. Do not blanket-rewrite mentions:
    # 奉议州、新化州等在后文又改属府，腾越州段的直隶记述指另一机构。
    direct_states = {
        ("guangdong", "羅定州"),
        *(('guangxi', name) for name in ["田州", "歸順州", "泗城州", "向武州", "都康州", "龍州", "江州", "思陵州", "憑祥州"]),
    }
    for row in units:
        if (row["region_id"], row["name_original"]) in direct_states:
            if "直隸布政司" not in row["source_excerpt"]:
                raise ValueError(f"Direct-state correction lost its source evidence: {row['name']}")
            row["source_layout_parent_id"] = row["parent_id"]
            row["parent_id"] = row["region_id"]
            row["parentage_status"] = "explicit_direct_subordination_in_source; temporal_review_required"
            row["parentage_correction"] = "原文明示直隶布政司，修正由章节排版顺序造成的误挂府级；未回溯1500年。"
    return units, counties, leftovers


def build(flags: dict) -> None:
    SOURCES.clear()
    texts = {n: load_wikisource(n, False, flags) for n in range(40, 47)}
    siku = {n: load_wikisource(n, True, flags) for n in range(40, 47)}
    skchar = fetch("siku_character_392_api.json", SKCHAR_URL, **flags)
    register("siku_character_392", "四库本 SKchar 392 字形模板展开：𥔲", SKCHAR_URL, skchar,
             "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/",
             verification_status="template_expansion_checked; corroborates_𥔲嘉_name")
    cities_path = fetch("ne_10m_populated_places_simple.geojson", NE_BASE + "ne_10m_populated_places_simple.geojson", **flags)
    land_path = fetch("ne_110m_land.geojson", NE_BASE + "ne_110m_land.geojson", **flags)
    terms_path = fetch("natural_earth_terms.html", TERMS, **flags)
    for name, title, path in [
        ("natural_earth_cities", "Natural Earth v5.1.2 10m populated places simple", cities_path),
        ("natural_earth_land", "Natural Earth v5.1.2 110m land", land_path),
    ]:
        register(name, title, NE_BASE + path.name, path, "Public domain", TERMS,
                 historical_scope="Modern geographic reference only; no historical boundaries", attribution="Made with Natural Earth.")
    register("natural_earth_license", "Natural Earth Terms of Use", TERMS, terms_path, "Terms of use evidence", TERMS)

    commons = fetch("commons_ming_map_api.json", COMMONS_API, **flags)
    info = next(iter(json.loads(commons.read_bytes())["query"]["pages"].values()))["imageinfo"][0]
    svg_url = info["url"].split("?")[0]
    svg = fetch("ming_empire_1580_reference.svg", svg_url, **flags)
    register("ming_map_1580_metadata", "Commons historical map licensing metadata", COMMONS_PAGE, commons,
             "CC0 structured metadata; CC BY-SA description", "https://creativecommons.org/publicdomain/zero/1.0/", download_url=COMMONS_API)
    register("ming_map_1580", "Ming Empire cca 1580 (en)", COMMONS_PAGE, svg,
             info["extmetadata"]["LicenseShortName"]["value"], "https://creativecommons.org/licenses/by-sa/3.0/cz/deed.en",
             download_url=svg_url, attribution="Michal Klajban / Podzemnik; derivative SVG by Jann; later translators listed in Commons file history.",
             modifications="None. Original SVG downloaded unchanged; used only as a separately identified historical reference.",
             historical_scope="circa 1580, about 80 years after scenario start; not georeferenced and NOT 1500 GIS boundaries",
             source_references=["Cambridge History of China, volume 7, map 1, p. xxiv (as cited by map authors)",
                                "Timothy Brook, The Troubled Empire (2010), map 6, p. 41 (as cited by map authors)"],
             verification_status="file_and_license_verified; historical_boundary_accuracy_not_independently_verified")

    # CHGIS is a valuable future reference, but is intentionally not bundled.
    chgis_url = "https://chgis.fas.harvard.edu/data/chgis/v6/"
    chgis = fetch("chgis_v6_license.html", chgis_url, **flags)
    register("chgis_license_review", "CHGIS v6 official license review", chgis_url, chgis,
             "Free academic research only; no commercial use/resale/redistribution",
             chgis_url, decision="No CHGIS vector/data files downloaded or included in the game.")

    city_features = json.loads(cities_path.read_bytes())["features"]
    cities = {f["properties"]["name"]: f for f in city_features}
    regions = []
    for region_id, name, original, capital, city, volume in REGION_SPECS:
        lon, lat = cities[city]["geometry"]["coordinates"]
        description_match = re.search(rf"^=={re.escape(original)}[^=]*==\s*\n(.+)", texts[volume], re.M)
        regions.append({
            "id": region_id, "name": name,
            "official_name": ("京师直隶" if region_id == "beizhili" else "南京直隶" if region_id == "nanzhili" else name + "等处承宣布政使司"),
            "name_original": original, "capital": capital,
            "longitude": lon, "latitude": lat,
            "modern_reference_city": city,
            "source_ids": [f"mingshi_{volume}", f"mingshi_siku_{volume}", "natural_earth_cities"],
            "source_excerpt": clean(description_match[1]) if description_match else "",
            "verification_status": "15_region_framework_and_seat_reference_checked; exact_1500_geometry_pending",
            "geometry_status": "modern_city_reference_point_not_historical_seat_survey",
            "coordinate_note": "Natural Earth现代城市参考坐标；仅用于治所所在地区示意，不代表历史府衙位置或明代边界。",
            "temporal_status": "1500_provisional_region_framework",
            "scenario_year": 1500,
        })
    units, counties, leftovers = extract(texts, siku)
    meta = {
        "schema_version": 1, "scenario_year": 1500, "scenario_era": "弘治十三年（临时开局基准）",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "historical_scope": "《明史》地理志跨明代沿革名录；下级行政记录尚未全部回溯到1500年",
        "coordinate_reference_system": "WGS84 longitude, latitude",
        "historical_boundaries_available": False,
        "data_warning": "府州县为史料参考库；禁止把其数量、隶属与万历人口直接用作1500开局实值。",
        "display_name_conversion": "OpenCC t2s" if CONVERTER else "Original traditional Chinese retained",
    }
    dump(DATA / "regions.json", {"metadata": {**meta, "record_count": len(regions)}, "records": regions})
    dump(DATA / "prefectures.json", {"metadata": {**meta, "record_count": len(units), "type_counts": dict(Counter(r['type'] for r in units))}, "records": units})
    dump(DATA / "counties.json", {"metadata": {**meta, "record_count": len(counties)}, "records": counties})
    dump(DATA / "ming_regions.geojson", {
        "type": "FeatureCollection", "metadata": meta,
        "features": [{"type": "Feature", "properties": {
            "region_id": r["id"], "name": r["name"], "capital": r["capital"],
            "source_ids": r["source_ids"], "geometry_status": r["geometry_status"],
        }, "geometry": {"type": "Point", "coordinates": [r["longitude"], r["latitude"]]}} for r in regions],
    })
    # Land is geographic background only, with no national/provincial borders.
    land = json.loads(land_path.read_bytes())
    land["metadata"] = {"source_ids": ["natural_earth_land"], "geometry_status": "modern_land_reference_not_ming_territory"}
    dump(DATA / "map_land.geojson", land)
    dump(DATA / "sources_geography.json", {"metadata": {"schema_version": 1, "generated_at": meta["generated_at"]}, "records": SOURCES})
    dump(DATA / "geography_extraction_review.json", {"metadata": {
        **meta, "parsed_units": len(units), "parsed_counties": len(counties),
        "unclassified_paragraph_count": len(leftovers),
        "county_counts_by_region": dict(Counter(r["region_id"] for r in counties)),
        "county_name_corrections": [{"id": r["id"], "original": r["name_original"], "corrected": r["name"]}
                                    for r in counties if "name_correction" in r],
        "county_names_without_second_transcription_substring_match": [
            {"id": r["id"], "name": r["name"], "source_ids": r["source_ids"]}
            for r in counties if not r["second_transcription_name_match"]],
    }, "records": leftovers})
    print(json.dumps({"regions": len(regions), "units": len(units), "counties": len(counties),
                      "unclassified_paragraphs": len(leftovers), "source_files": len(SOURCES)}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.refresh and args.offline:
        parser.error("--refresh and --offline cannot be combined")
    build({"refresh": args.refresh, "offline": args.offline})


if __name__ == "__main__":
    main()

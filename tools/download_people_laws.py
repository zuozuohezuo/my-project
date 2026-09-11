"""Fetch the public-domain source chapters used by the Ming history starter pack.

Run: uv run python tools/download_people_laws.py
No authentication, bulk scraping, database export or synthetic source text is used.
Existing source files are retained unless --refresh is requested.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/history/raw"
CATALOG = ROOT / "data/history/sources_people_laws.json"

MING_VOLUMES = {
    15: "孝宗本纪", 72: "职官一", 73: "职官二", 74: "职官三", 75: "职官四", 76: "职官五",
    93: "刑法一", 109: "宰辅年表一", 111: "七卿年表一",
    181: "刘健谢迁李东阳等列传", 182: "王恕马文升刘大夏列传", 183: "周经倪岳闵珪戴珊等列传",
    184: "傅瀚张升等列传", 185: "李敏佀钟曾鉴等列传",
}
LAW_VOLUMES = {2: "职制", 3: "公式", 4: "户役", 5: "田宅", 7: "仓库", 23: "受赃", 30: "河防"}
DISCOVERY_NOTES = [
    {"id": "cbdb_license", "url": "https://cbdb.hsites.harvard.edu/download-cbdb-standalone-database",
     "additional_url": "https://cbdb.hsites.harvard.edu/exclusive-commercial-license",
     "status": "official_metadata_checked_not_imported", "checked_on": "2026-09-07",
     "note": "经哈佛CBDB官网核对，学术数据采用CC BY-NC-SA，另有商业授权说明。此游戏原型未导入CBDB整库或记录；采用公有领域原典人工整理。商业数据库不是当前运行依赖。"},
    {"id": "wikisource_parser_failure", "status": "resolved", "checked_on": "2026-09-07",
     "note": "初次下载卷181/182/183/185时，页面有空的首个mw-parser-output而导致正文校验失败；已改为选择正文最长的相应元素，重新下载及锚点校验通过。失败页未冒充原典保存。"},
    {"id": "urllib_without_project_agent", "status": "resolved_with_declared_project_user_agent", "checked_on": "2026-09-07",
     "url": "https://zh.wikisource.org/wiki/明史/卷181",
     "note": "一次不带项目标识的标准库诊断请求返回403；带公开项目User-Agent的正常页面请求返回200，未使用账号、验证码绕过或私有接口。"},
    {"id": "law_edition_limit", "status": "pending_edition_collation", "checked_on": "2026-09-07",
     "note": "在线大明律载体含后世集解、会典及附例。只将基础律文主题作为参考，尚未逐条比对洪武刊本和1500年问刑条例原刊。"},
    {"id": "huidian_chronology", "status": "edition_dates_checked", "checked_on": "2026-09-07",
     "url": "https://zh.wikisource.org/wiki/大明會典/御製大明會典序",
     "note": "御序分别署弘治十五年、正德四年、万历十五年。保留序文本以证明版本层次，未称会典全文已下载或1500年已颁行。"},
]


def specifications():
    specs = []
    for volume, title in MING_VOLUMES.items():
        specs.append({"id": f"mingshi_{volume:03d}", "title": f"明史·卷{volume}·{title}",
                      "url": f"https://zh.wikisource.org/wiki/明史/卷{volume}",
                      "work": "明史", "source_kind": "public_domain_primary_historiography"})
    for volume, title in LAW_VOLUMES.items():
        specs.append({"id": f"daminglv_{volume:02d}", "title": f"大明律集解附例·卷{volume}·{title}",
                      "url": f"https://zh.wikisource.org/wiki/大明律/{volume:02d}",
                      "work": "大明律集解附例", "source_kind": "public_domain_law_with_later_commentary"})
    specs.append({"id": "mingtongjian_043", "title": "明通鉴·卷43·弘治十二至十五年",
                  "url": "https://zh.wikisource.org/wiki/明通鑑/卷043", "work": "明通鉴",
                  "source_kind": "public_domain_primary_historiography"})
    specs.append({"id": "daminghuidian_prefaces", "title": "大明会典·御制大明会典序（含1502、1509、1587序）",
                  "url": "https://zh.wikisource.org/wiki/大明會典/御製大明會典序", "work": "大明会典",
                  "source_kind": "public_domain_edition_history"})
    return specs


def download(spec, refresh=False):
    result = dict(spec)
    path = RAW / f"{spec['id']}.html"
    text_path = RAW / f"{spec['id']}.txt"
    result["accessed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["license_note"] = (
        "原典作者均已逝世逾百年，维基文库标为公有领域；现代校录、标点、页面与贡献遵守站点所示 "
        "CC BY-SA 等适用条款。保留来源、原始 HTML 与修订链接；正式发行前复核版本和署名要求。"
    )
    result["period_note"] = (
        "清代修撰的明代史书，须按条目纪年筛选，不能将全书制度总述视为1500年同步快照。"
        if spec["work"] in {"明史", "明通鉴"} else
        "此载体含后世集解与附例，不能将所有附例当作1500年已生效法。结构化条目只摘出律文主题，数值规则未启用。"
    )
    if spec["work"] == "大明会典":
        result["period_note"] = "只用御序核对版本年代：弘治十五年、正德四年、万历十五年。后出会典不可整本当作1500年已颁行制度；未下载或声称全书完成校勘。"
    try:
        if refresh or not path.exists():
            url = urllib.parse.quote(spec["url"], safe=":/?=&")
            request = urllib.request.Request(url, headers={"User-Agent": "MingDynastyPrototype/0.1 (educational local history research)"})
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
                result["http_status"] = response.status
                result["resolved_url"] = response.url
            soup = BeautifulSoup(payload, "html.parser")
            body = max(soup.select(".mw-parser-output"), key=lambda node: len(node.get_text()), default=None)
            if body is None or len(body.get_text(strip=True)) < 300:
                raise ValueError("No substantial Wikisource source body found")
            path.write_bytes(payload)
        else:
            result["http_status"] = "cached"
        payload = path.read_bytes()
        soup = BeautifulSoup(payload, "html.parser")
        body = max(soup.select(".mw-parser-output"), key=lambda node: len(node.get_text()), default=None)
        if body is None:
            raise ValueError("Missing source body")
        # Original HTML remains untouched; reading copy removes scripts and edit controls.
        for node in body.select("script,style,.mw-editsection,.noprint,#toc"):
            node.decompose()
        body_text = body.get_text("\n", strip=True)
        text_path.write_text(body_text, encoding="utf-8")
        result.update({"local_path": path.relative_to(ROOT).as_posix(),
                       "text_path": text_path.relative_to(ROOT).as_posix(),
                       "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
                       "text_sha256": hashlib.sha256(text_path.read_bytes()).hexdigest(),
                       "verification_status": "downloaded_body_checked"})
        match = re.search(r"(?:oldid=|oldid%3D)(\d+)", payload.decode("utf-8", errors="replace"))
        if match:
            result["revision_url"] = f"https://zh.wikisource.org/w/index.php?oldid={match.group(1)}"
    except (OSError, ValueError, urllib.error.URLError) as exc:
        result.update({"verification_status": "download_failed", "error": str(exc), "local_path": None})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    previous = {}
    if CATALOG.exists():
        previous = json.loads(CATALOG.read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(lambda spec: download(spec, args.refresh), specifications()))
    # Preserve original access time when re-reading cached artifacts.
    old_records = {r["id"]: r for r in previous.get("records", [])}
    for record in records:
        if record.get("http_status") == "cached" and record["id"] in old_records:
            record["accessed_at"] = old_records[record["id"]]["accessed_at"]
    result = {"metadata": {"schema_version": 1, "baseline_year": 1500,
              "baseline_note": "弘治十三年为工作基准，待用户确认；纪年按明代农历，不映射公历月日。",
              "retrieval_method": "公开原典章节 HTML 下载及正文提取，逐条来源核对见条目 evidence"},
              "records": records,
              "discovery_notes": list({note["id"]: note for note in
                  [*previous.get("discovery_notes", []), *DISCOVERY_NOTES]}.values())}
    CATALOG.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for record in records:
        print(record["id"], record["verification_status"], record.get("bytes", record.get("error")))
    if any(record["verification_status"] == "download_failed" for record in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

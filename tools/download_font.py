"""Download an OFL-licensed CJK font, preserving its license and provenance."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/"


def main():
    target = ROOT / "assets" / "fonts"
    target.mkdir(parents=True, exist_ok=True)
    records = []
    for remote, local in [("NotoSansSC%5Bwght%5D.ttf", "NotoSansSC.ttf"), ("OFL.txt", "OFL.txt")]:
        url = BASE + remote
        with urlopen(url, timeout=90) as response:
            data = response.read()
        (target / local).write_bytes(data)
        records.append({"url": url, "local_path": f"assets/fonts/{local}", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "downloaded_at": datetime.now(timezone.utc).isoformat(), "license": "SIL Open Font License 1.1"})
    (target / "sources.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"font_files": len(records), "bytes": sum(item["bytes"] for item in records)}))


if __name__ == "__main__":
    main()

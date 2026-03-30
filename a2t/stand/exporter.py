from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def _flatten_row(row: Dict[str, Any]) -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"{key}.{sub_key}"] = sub_value
        else:
            flat[key] = value
    return flat


class Exporter:
    def export_csv(self, path: str | Path, rows: List[Dict[str, Any]]) -> None:
        path = Path(path)
        if not rows:
            path.write_text("", encoding="utf-8")
            return

        flat_rows = [_flatten_row(r) for r in rows]
        fieldnames = sorted({k for row in flat_rows for k in row.keys()})

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_rows)

    def export_txt(self, path: str | Path, rows: List[Dict[str, Any]]) -> None:
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False))
                f.write("\n")
from __future__ import annotations
import csv
import json
from pathlib import Path


def _flatten_row(row):
    flat = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat["%s.%s" % (key, sub_key)] = sub_value
        else:
            flat[key] = value
    return flat


class Exporter:
    def export_csv(self, path, rows):
        path = Path(path)
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        flat_rows = [_flatten_row(r) for r in rows]
        fieldnames = sorted(set(k for row in flat_rows for k in row.keys()))
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_rows)

    def export_txt(self, path, rows):
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False))
                f.write("\n")

    def export_json(self, path, rows):
        path = Path(path)
        with path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

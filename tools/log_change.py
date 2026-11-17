#!/usr/bin/env python3
"""Insert a WITA timestamped, append-only change entry into the project SRS."""

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WITA = timezone(timedelta(hours=8), "WITA")
MARKER = "<!-- CHANGELOG:START -->"
TYPES = (
    "ADDED",
    "CHANGED",
    "FIXED",
    "REMOVED",
    "DECISION",
    "MODEL",
    "DATA",
    "CONFIG",
    "DOCS",
    "REQUIREMENT",
)


def build_entry(args: argparse.Namespace, stamp: str) -> str:
    lines = [
        f"### `[{stamp} WITA]` - {args.title}",
        f"- **Tipe**: {args.type}",
        f"- **Author**: {args.author}",
        f"- **Fase**: {args.phase}",
    ]
    if args.req:
        lines.append(f"- **Requirement terkait**: {', '.join(args.req)}")
    if args.files:
        lines.append("- **File**: " + ", ".join(f"`{path}`" for path in args.files))
    if args.details:
        lines.append("- **Detail**:")
        lines.extend(f"  - {detail}" for detail in args.details)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Catat perubahan proyek ke srs.md")
    parser.add_argument("--title", required=True, help="Ringkasan perubahan")
    parser.add_argument("--type", default="CHANGED", choices=TYPES)
    parser.add_argument("--author", default="change-logger")
    parser.add_argument("--phase", default="-", help="Fase workflow 0-7 atau '-'")
    parser.add_argument("--req", nargs="*", default=[], help="ID requirement terkait")
    parser.add_argument("--files", nargs="*", default=[], help="File yang berubah")
    parser.add_argument("--details", nargs="*", default=[], help="Detail faktual perubahan")
    parser.add_argument("--srs", default="srs.md", help="Path file SRS")
    args = parser.parse_args()

    srs_path = Path(args.srs)
    if not srs_path.is_file():
        print(f"ERROR: {srs_path} tidak ditemukan", file=sys.stderr)
        return 1
    content = srs_path.read_text(encoding="utf-8")
    if MARKER not in content:
        print(f"ERROR: penanda {MARKER} tidak ada di {srs_path}", file=sys.stderr)
        return 1

    stamp = datetime.now(WITA).strftime("%Y-%m-%d %H:%M:%S")
    entry = build_entry(args, stamp)
    content = content.replace(MARKER, f"{MARKER}\n\n{entry}", 1)
    content = re.sub(
        r"(\*\*Terakhir diperbarui\*\*:).*",
        rf"\1 {stamp} WITA",
        content,
        count=1,
    )
    srs_path.write_text(content, encoding="utf-8")
    print(f"OK [{stamp} WITA] {args.title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

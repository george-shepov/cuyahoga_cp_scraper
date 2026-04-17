#!/usr/bin/env python3
"""Export approved knowledge-base content to JSON for external publishing."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from database.session import SessionLocal, init_db
from services.knowledge_base import KnowledgeBaseService


def export_content(output_path: Path, limit: int) -> int:
    init_db()
    session = SessionLocal()
    try:
        service = KnowledgeBaseService(session)
        items = service.export_approved_content(limit=limit)
    finally:
        session.close()

    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_items": len(items),
        "items": items,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export approved KB content as JSON feed")
    parser.add_argument(
        "--output",
        default="analysis_output/approved_content_feed.json",
        help="Output JSON file path",
    )
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of approved items")
    args = parser.parse_args()

    output_path = Path(args.output)
    exported = export_content(output_path, args.limit)
    print(f"exported={exported}")
    print(f"file={output_path}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Gold set tool: `validate` a gold JSONL, `stats` writes learning/metrics/gold_stats.json.

Default gold path: $PI_ROUTER_HOME/gold/v1.jsonl (outside the repo). This tool never creates
gold rows; labelling is a user review step after G3.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engines" / "hybrid_router"))
from hierarchical_routing.hierarchical_engine import HeuristicFallbackEngine  # noqa: E402
from ztc import gold  # noqa: E402
from ztc.paths import METRICS_DIR, router_home  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("validate", "stats"))
    ap.add_argument("--gold", type=Path, default=None)
    args = ap.parse_args()
    path = args.gold or router_home() / "gold" / "v1.jsonl"
    rows = gold.load(path) if path.exists() else []
    errors = gold.validate(rows)
    if args.command == "validate":
        for e in errors:
            print(e)
        print(f"{len(rows)} rows, {len(errors)} errors ({'missing file' if not path.exists() else 'ok' if not errors else 'invalid'})")
        return 1 if errors else 0
    if errors:
        print(f"refusing stats: {len(errors)} validation errors", file=sys.stderr)
        return 1
    engine = HeuristicFallbackEngine()
    stats = gold.aggregate(rows, heuristic=lambda text: engine.predict({"log": text})["decision"])
    stats["gold_file_present"] = path.exists()
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    out = METRICS_DIR / "gold_stats.json"
    out.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

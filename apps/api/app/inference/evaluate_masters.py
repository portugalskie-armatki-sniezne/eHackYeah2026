import argparse
import hashlib
import json
import os
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from app.inference.masters import MIN_SCORE_RATIO, QUESTION, UNMATCHED_CRITERION, MasterMatcher
from app.inference.runtime import configured_classifier, configured_translator
from app.matching import MIN_TITLE_SIMILARITY, title_similarity

ROOT = Path(__file__).resolve().parents[4]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate matching of new reports to nearby masters")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-recall", type=float, default=0.7)
    parser.add_argument("--max-false-merges", type=float, default=0.15)
    args = parser.parse_args()
    for name in ("min_recall", "max_false_merges"):
        if not 0 <= getattr(args, name) <= 1:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1")
    matcher = MasterMatcher(configured_translator(), configured_classifier())
    fixture = ROOT / "tests/fixtures/master_matching.json"
    results = []
    for case in json.loads(fixture.read_text()):
        started = perf_counter()
        # the same order as publication: similar titles first, then the model.
        similarities = [title_similarity(case["title"], candidate) for candidate in case["candidates"]]
        if max(similarities) >= MIN_TITLE_SIMILARITY:
            predicted, source = similarities.index(max(similarities)), "title"
        else:
            choice = matcher.choose(case["title"], {str(index): text for index, text in enumerate(case["candidates"])})
            predicted, source = (None if choice is None else int(choice)), "model"
        row = {
            "id": case["id"],
            "expected": case["expected"],
            "predicted": predicted,
            "source": source,
            "seconds": round(perf_counter() - started, 3),
        }
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    same = [row for row in results if row["expected"] is not None]
    different = [row for row in results if row["expected"] is None]
    joined = sum(row["predicted"] == row["expected"] for row in same)
    merged = sum(row["predicted"] is not None for row in different)
    recall = joined / len(same) if same else None
    false_merges = merged / len(different) if different else None
    report = {
        "joined": joined,
        "same": len(same),
        "recall": recall,
        "false_merges": merged,
        "different": len(different),
        "false_merge_rate": false_merges,
        "results": results,
    }
    report["configuration"] = {
        "question_sha256": hashlib.sha256(f"{QUESTION}\n{UNMATCHED_CRITERION}".encode()).hexdigest(),
        "fixtures_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "min_score_ratio": MIN_SCORE_RATIO,
        "min_title_similarity": MIN_TITLE_SIMILARITY,
        "calibration_strength": os.getenv("LAYA_CALIBRATION_STRENGTH", "1"),
        "permutations": os.getenv("LAYA_PERMUTATIONS", "3"),
        "device": os.getenv("LAYA_DEVICE", "cpu"),
        "packages": {name: version(name) for name in ("laya", "transformers", "torch")},
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Joined: {joined}/{len(same)} ({recall}), false merges: {merged}/{len(different)} ({false_merges})")
    if (recall is not None and recall < args.min_recall) or (
        false_merges is not None and false_merges > args.max_false_merges
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

import argparse
import hashlib
import json
import os
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from app.inference.contracts import ImageInput
from app.inference.entities import EntityClassificationRequest, EntityClassificationService, load_entity_question
from app.inference.runtime import configured_classifier, configured_translator
from app.inference.service import InferenceService

ROOT = Path(__file__).resolve().parents[4]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the configured models on civic report fixtures")
    parser.add_argument("--split", choices=["development", "holdout", "contract", "all"], default="all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-accuracy", type=float, default=0.8)
    args = parser.parse_args()
    if not 0 <= args.min_accuracy <= 1:
        parser.error("--min-accuracy must be between 0 and 1")
    question = load_entity_question()
    service = EntityClassificationService(InferenceService(configured_translator(), configured_classifier()), question)
    fixture = ROOT / "tests/fixtures/entity_classification.json"
    cases = json.loads(fixture.read_text())
    results = []
    for case in cases:
        if args.split != "all" and case["split"] != args.split:
            continue
        image = (
            ImageInput(data=(ROOT / case["image"]).read_bytes(), media_type="image/jpeg") if case.get("image") else None
        )
        started = perf_counter()
        result = service.classify(
            EntityClassificationRequest.model_validate(
                {key: case[key] for key in ("title", "description", "source_language")}
            ),
            image,
        )
        row = {
            "id": case["id"],
            "split": case["split"],
            "expected": case["expected"],
            "predicted": result.entity_type,
            "translated_text": result.translation.text,
            "seconds": round(perf_counter() - started, 3),
        }
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    labelled = [row for row in results if row["expected"] is not None]
    correct = sum(row["predicted"] == row["expected"] for row in labelled)
    accuracy = correct / len(labelled) if labelled else None
    report = {"correct": correct, "labelled": len(labelled), "accuracy": accuracy, "results": results}
    report["configuration"] = {
        "criteria_sha256": hashlib.sha256(question.model_dump_json().encode()).hexdigest(),
        "fixtures_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "calibration_strength": os.getenv("LAYA_CALIBRATION_STRENGTH", "1"),
        "permutations": os.getenv("LAYA_PERMUTATIONS", "3"),
        "device": os.getenv("LAYA_DEVICE", "cpu"),
        "packages": {name: version(name) for name in ("laya", "transformers", "torch")},
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Accuracy: {correct}/{len(labelled)} ({accuracy})", flush=True)
    if accuracy is not None and accuracy < args.min_accuracy:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

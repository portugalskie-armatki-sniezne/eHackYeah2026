import json
from pathlib import Path

from fastapi import HTTPException

from app.gemini import IMAGE_TYPES, generate_visualizations

MOCK_DIR = Path(__file__).resolve().parent / "mock"
DESCRIPTION = (MOCK_DIR / "opis.txt").read_text(encoding="utf-8")
PHOTO = MOCK_DIR / "laka-po-deszczu-czyli-polana.jpg"
VARIANTS = 3


def main() -> None:
    try:
        images = generate_visualizations(DESCRIPTION, [("image/jpeg", PHOTO.read_bytes())], VARIANTS)
    except HTTPException as error:
        raise SystemExit(error.detail) from None

    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    proposals = []
    for number, (prompt, media_type, data) in enumerate(images, start=1):
        path = output_dir / f"variant-{number}{IMAGE_TYPES[media_type]}"
        path.write_bytes(data)
        proposals.append({"prompt": prompt, "media_type": media_type, "file": path.name})
        print(path, flush=True)
    (output_dir / "prompts.json").write_text(
        json.dumps(proposals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

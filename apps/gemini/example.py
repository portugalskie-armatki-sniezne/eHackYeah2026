from pathlib import Path

from fastapi import HTTPException

from app.gemini import IMAGE_TYPES, generate_visualization

MOCK_DIR = Path(__file__).resolve().parent / "mock"
DESCRIPTION = (MOCK_DIR / "opis.txt").read_text(encoding="utf-8")
PHOTO = MOCK_DIR / "laka-po-deszczu-czyli-polana.jpg"


def main() -> None:
    try:
        photos = [("image/jpeg", PHOTO.read_bytes())]
        prompt, media_type, data = generate_visualization("improvement", DESCRIPTION, photos)
    except HTTPException as error:
        raise SystemExit(error.detail) from None

    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    path = output_dir / f"visualization{IMAGE_TYPES[media_type]}"
    path.write_bytes(data)
    (output_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()

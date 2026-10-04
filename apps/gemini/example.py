from pathlib import Path

from fastapi import HTTPException

from app.gemini import IMAGE_TYPES, generate_image

PROMPT = (
    "Wygeneruj realistyczne zdjęcie małego parku miejskiego w Krakowie po rewitalizacji. "
    "Drzewa, ławki, zadbane alejki i ciepłe popołudniowe światło. Bez napisów."
)


def main() -> None:
    try:
        media_type, data = generate_image(PROMPT)
    except HTTPException as error:
        raise SystemExit(error.detail) from None

    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(exist_ok=True)
    path = output_dir / f"example{IMAGE_TYPES[media_type]}"
    path.write_bytes(data)
    print(path)


if __name__ == "__main__":
    main()

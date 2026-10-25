"""Writes the GET /instruments body to web/mock/catalog.json, the catalog of
the frontend's dev mock: `python3 -m src.scripts.export_catalog`."""
import json
from pathlib import Path

from src.contract import jobs

TARGET = Path("web/mock/catalog.json")


def main() -> None:
    TARGET.write_text(
        json.dumps(jobs.catalog_response(), indent=2, ensure_ascii=False) +
        "\n",
        encoding="utf-8")
    print(TARGET)


if __name__ == "__main__":
    main()

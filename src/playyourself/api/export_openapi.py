"""Write the OpenAPI spec to docs/openapi.json."""

import json
from pathlib import Path

from playyourself.api.app import app

OUT = Path(__file__).resolve().parents[3] / "docs" / "openapi.json"


def main() -> None:
    OUT.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

"""Write the API's OpenAPI schema where the frontend generates its types from.

    uv run python scripts/export_openapi.py [output.json]   # from backend/

Usually run through `npm run gen:api` in the frontend, which also regenerates the TypeScript types.
"""

import json
import sys
from pathlib import Path

from backend.main import app

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "review-burden" / "lib" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.write_text(render(), encoding="utf-8")
    print(f"Wrote {output}")

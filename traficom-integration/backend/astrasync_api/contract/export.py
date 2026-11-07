"""Write the OpenAPI contract file, or with ``--check`` fail if it has drifted from the code."""

import argparse
import json
import sys
from pathlib import Path

from ..app import build_openapi, create_app

OPENAPI_PATH = Path(__file__).resolve().parents[3] / "contract" / "openapi.json"


def render_openapi() -> str:
    return json.dumps(build_openapi(create_app()), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = parser.parse_args()

    rendered = render_openapi()
    if args.check:
        if not OPENAPI_PATH.exists() or OPENAPI_PATH.read_text("utf-8") != rendered:
            print(f"{OPENAPI_PATH} is out of date; run this module without --check.")
            return 1
        return 0
    OPENAPI_PATH.write_text(rendered, "utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

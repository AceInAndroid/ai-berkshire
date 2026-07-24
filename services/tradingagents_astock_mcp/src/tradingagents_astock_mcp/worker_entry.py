"""Private entry point executed by the isolated TradingAgents Python runtime."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Direct script execution puts the package directory, not its parent, on sys.path.
# This path is derived only from the installed adapter file and is never user input.
_PACKAGE_PARENT = Path(__file__).resolve().parent.parent
if str(_PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PARENT))

from tradingagents_astock_mcp.worker import execute_request_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(prog="tradingagents-astock-worker")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    execute_request_file(args.request, args.result)


if __name__ == "__main__":
    main()

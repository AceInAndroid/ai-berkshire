from __future__ import annotations

import argparse


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tradingagents-astock-mcp")
    subparsers = parser.add_subparsers(dest="command", required=True)
    serve = subparsers.add_parser("serve", help="Run the MCP server")
    serve.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    from .mcp_server import create_mcp

    server = create_mcp()
    transport = "stdio" if args.transport == "stdio" else "streamable-http"
    server.run(transport=transport)


if __name__ == "__main__":
    main()

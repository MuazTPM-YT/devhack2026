# uv run --locked --env-file .env python -m akira_mcp          stdio MCP server (Claude Code / Claude Desktop)
# uv run --locked --env-file .env python -m akira_mcp watch    live event lines (for a terminal or Monitor)
import argparse
import logging
import sys

from akira_mcp import settings as config


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m akira_mcp", description="Akira MCP server and live watch.")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server on stdio (default)")
    w = sub.add_parser("watch", help="print one line per Akira event; reconnects on its own")
    w.add_argument("--after", type=int, default=None, help="start after this seq (default: from now)")
    w.add_argument("--incident", default=None, help="only this incident id")
    args = p.parse_args(argv)
    # stdout is the MCP protocol channel: every log line goes to stderr
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        s = config.load()
    except config.SettingsError as e:
        print(f"akira_mcp: {e}", file=sys.stderr)
        return 2
    if args.command == "watch":
        from akira_mcp import watch
        return watch.run(s.gateway_url, args.after, args.incident)
    from akira_mcp.server import build_server
    build_server(s).run("stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())

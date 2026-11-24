# Flipper Zero MCP Server Guidelines

- Local Model Context Protocol (MCP) server driving a Flipper Zero over USB serial.
- 32 tools covering display capture, button presses, CLI commands, SD storage, BadUSB, Sub-GHz, and knowledge base.
- Offline test suite:
  - Run tests with `pytest -v` or `python -m unittest discover -s tests -v`.
  - All 81 tests must pass cleanly.
- Tool annotations: Every tool must maintain complete FastMCP tool hints (read_only, destructive, etc.).

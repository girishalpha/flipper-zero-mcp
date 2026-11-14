# flipper-zero-mcp

A small MCP server that lets an AI agent (Claude Code, Claude Desktop, or any
MCP client) drive a Flipper Zero over USB: press buttons, see the screen, run
CLI commands, manage files, and capture radio/IR/RFID input.

It is one Python file with two dependencies. No custom firmware, no companion
app on the Flipper, no extra hardware.

![Screenshot returned by flipper_screenshot](docs/screenshot.png)

## What it can do

- **See and control the screen** — `flipper_screenshot` returns the display as a
  PNG; `flipper_navigate` and `flipper_press` send button presses and can
  return the resulting screen in the same call.
- **Run anything on the CLI** — `flipper_run_cli` for normal commands,
  `flipper_listen` for commands that run until interrupted (`subghz rx`,
  `ir rx`, `rfid read`, ...).
- **Manage files** — list, read, download, upload (MD5-verified), mkdir, delete.
- **Launch and close apps**, run JavaScript on the device, write and run BadUSB
  scripts, transmit saved Sub-GHz files, set the LED and vibration motor.
- **Diagnose itself** — `flipper_status` reports whether the Flipper is
  connected, the port is free, the CLI answers and the screen can be captured.

Full list: [docs/TOOLS.md](docs/TOOLS.md).

## Requirements

- Flipper Zero connected by USB
- Python 3.10+
- `pip install -r requirements.txt` (`mcp`, `pyserial`)

Tested on Windows 11 with Momentum firmware (mntm-012). It uses only the
standard Flipper CLI and RPC, so other firmware and operating systems should
work, but they have not been tested.

## Install

```bash
git clone https://github.com/girishalpha/flipper-zero-mcp.git
cd flipper-zero-mcp
pip install -r requirements.txt
python flipper_mcp_server.py --selftest
```

The self-test prints the device info and SD card status, then `self-test OK`.

### Claude Code

```bash
claude mcp add flipper -- python /full/path/to/flipper_mcp_server.py
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "flipper": {
      "command": "python",
      "args": ["/full/path/to/flipper_mcp_server.py"]
    }
  }
}
```

### Configuration

The serial port is found automatically by USB ID (`0483:5740`). To override it,
set the `FLIPPER_PORT` environment variable (for example `COM10` or
`/dev/ttyACM0`).

## Example

Ask the agent something like:

> Open the Infrared app on my Flipper and show me the screen.

It will typically call `flipper_status`, then `flipper_loader_open`, then
`flipper_screenshot`, and use `flipper_navigate(..., screenshot=True)` to move
through menus while watching the result.

## How it works

- The server opens the serial port for each tool call and closes it again, so
  it never blocks qFlipper or other tools between calls.
- Commands go through the Flipper's text CLI at 230400 baud.
- Screenshots use the Flipper's protobuf RPC: the server starts an RPC session,
  requests the screen stream, takes one 128x64 frame, stops the session and
  encodes the frame as a PNG. The few protobuf messages involved are
  encoded by hand, so no generated protobuf code is needed.

## Things to know

- **A locked Flipper refuses screenshots.** On Momentum, RPC is blocked while
  the device is keypad- or PIN-locked. `flipper_unlock` clears a keypad lock.
- **Only one program can hold the serial port.** Close qFlipper and any
  lab.flipper.net browser tab before using this server.
- More in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Responsible use

This server gives an AI agent real control of a radio and HID device. Transmit
only on frequencies that are legal where you are, and only at devices you own.
Run BadUSB scripts only on computers you own or are authorised to test.

## License

MIT — see [LICENSE](LICENSE).

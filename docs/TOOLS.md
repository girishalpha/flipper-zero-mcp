# Tools

All tools open the serial port, do their work and close it again.

## Status and device

| Tool | Arguments | What it does |
|---|---|---|
| `flipper_status` | — | Health check: USB present, port free, CLI answering, running app, uptime, screen capture working. Run this first when something fails. |
| `flipper_info` | — | Full `device_info` output (firmware, hardware, radio, region). |
| `flipper_reboot` | `mode` = `normal` \| `dfu` | Reboot the Flipper, optionally into the DFU bootloader. |
| `flipper_led` | `r`, `g`, `b` (0-255) | Set the RGB status LED. |
| `flipper_vibro` | `on` | Turn the vibration motor on or off. |

## Screen and buttons

| Tool | Arguments | What it does |
|---|---|---|
| `flipper_screenshot` | `save_path` (optional) | Return the current screen as a PNG (128x64, upscaled 4x). Optionally save it on the PC. |
| `flipper_press` | `button`, `kind` = `short` \| `long` \| `press` \| `release`, `screenshot` | Send one button press. With `screenshot=true`, also return the screen afterwards. |
| `flipper_navigate` | `keys`, `delay_ms`, `screenshot` | Send a sequence such as `down,down,ok` or `back ok:long`. With `screenshot=true`, also return the screen after the last press. |
| `flipper_unlock` | — | Clear a keypad lock (Back x3) and return the screen. Does not clear a PIN lock. |

Buttons are `up`, `down`, `left`, `right`, `ok`, `back`.

## CLI

| Tool | Arguments | What it does |
|---|---|---|
| `flipper_run_cli` | `command`, `timeout` | Run any CLI command that finishes on its own and return its output. `help` lists commands. |
| `flipper_listen` | `command`, `seconds` | Run a command that listens until interrupted, stop it with Ctrl+C after `seconds`, and return what it captured. |

Useful `flipper_listen` commands:

| Command | Captures |
|---|---|
| `subghz rx 433920000 0` | Decoded Sub-GHz packets on a frequency (last argument: 0 internal radio, 1 external) |
| `ir rx` / `ir rx raw` | Infrared signals, decoded or raw |
| `rfid read` | 125 kHz RFID cards |
| `ikey read` | iButton keys |
| `log` | Live system log |

## Apps

| Tool | Arguments | What it does |
|---|---|---|
| `flipper_apps_running` | — | Show the running app, if any. |
| `flipper_loader_open` | `app`, `args` (optional) | Launch an app by name, optionally with a file path. |
| `flipper_loader_close` | — | Close the running app. |
| `flipper_js_run` | `script`, `timeout` | Upload a JavaScript program to `/ext/.tmp/mcp_run.js`, run it on the device and return its output. |

## Storage

Paths are Flipper paths: `/ext` is the SD card, `/int` is internal storage.

| Tool | Arguments | What it does |
|---|---|---|
| `flipper_storage_info` | — | SD card label, filesystem and free space. |
| `flipper_storage_list` | `path` | List a directory. |
| `flipper_storage_read` | `path`, `max_bytes` | Return a file as text, or as `base64:...` if it is binary. |
| `flipper_storage_download` | `remote_path`, `local_path` | Copy a file from the Flipper to the PC (binary-safe). |
| `flipper_storage_write` | `remote_path`, `local_path` | Upload a PC file to the Flipper and verify it by MD5. |
| `flipper_storage_mkdir` | `path` | Create a directory. |
| `flipper_storage_delete` | `path` | Delete a file or empty directory. |

## Transmit and HID

| Tool | Arguments | What it does |
|---|---|---|
| `flipper_subghz_tx` | `path`, `frequency` | Transmit a saved `.sub` file. |
| `flipper_badusb_create` | `filename`, `ducky_script` | Write a DuckyScript to `/ext/badusb/`. Does not run it. |
| `flipper_badusb_run` | `filename` | Launch the Bad USB app with a saved script. It runs against whatever computer the Flipper is plugged into. |

Transmit only on legal frequencies at devices you own, and run BadUSB scripts
only on computers you own or are authorised to test.

## Orientation and search

| Tool | Arguments | What it does |
|---|---|---|
| `flipper_index` | `depth`, `max_calls` | One-call survey: firmware/hardware/region, running app, SD free, and an `/ext` tree with per-folder file/subdir counts down to `depth`. Huge folders are counted but not expanded; a call budget keeps it fast. Run first to get oriented. |
| `flipper_find` | `name`, `path`, `max_calls` | Recursively search the SD for files/folders whose name contains `name`. Budgeted. |
| `flipper_launch_fap` | `fap_path` | Launch an external `.fap` by its SD path without blocking (external apps are not in `loader list`, and a blocking launch wedges the port). Follow with `flipper_screenshot` / `flipper_navigate`. |
| `flipper_js_run` | `script`, `timeout` | Run a JavaScript program on the device (mJS engine) and return its output. |

## Task knowledge base

A local `knowledge/` folder is the agent's growing memory of past tasks, so a
similar future task reuses learnings instead of starting from scratch. The notes
are **per-user and git-ignored**; only the folder's `README.md` is committed.

| Tool | Arguments | What it does |
|---|---|---|
| `flipper_kb_list` | — | List saved topics. |
| `flipper_kb_search` | `query` | Search all notes for a term. Run at the **start** of a task. |
| `flipper_kb_read` | `topic` | Read one note. |
| `flipper_kb_save` | `topic`, `content`, `append` | Record a learning (timestamped). Run at the **end** of a task. |

Suggested pattern for any task: `flipper_index` + `flipper_kb_search` to orient →
do the work → `flipper_kb_save` the non-obvious bits.

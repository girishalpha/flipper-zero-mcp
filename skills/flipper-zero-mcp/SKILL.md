---
name: flipper-zero-mcp
description: Operational guide and workflows for AI coding assistants using the Flipper Zero MCP Server to interact with a physical Flipper Zero device over USB serial.
---

# Flipper Zero MCP Assistant Skill

This skill guides AI assistants (Claude, Cursor, Windsurf, Cline) on driving a physical **Flipper Zero** over USB serial without companion apps or custom firmware.

## Architecture & Communication

- **Direct Serial Protocol**: Communicates directly over USB serial (`0483:5740`) via both Flipper CLI text protocol and Protobuf RPC.
- **Hardware Isolation**: Only standard Flipper CLI and RPC are used; no device flashing or firmware modification required.
- **Safe State Tracking**: Screens are returned as base64 PNGs directly inline or rendered for visual validation.

---

## Tool Reference (32 Available Tools)

### 1. Vision & Screen Navigation
- `flipper_screenshot`: Capture the current 128x64 LCD display as a base64 PNG.
- `flipper_press`: Send button clicks (`up`, `down`, `left`, `right`, `ok`, `back`) with optional short/long hold.
- `flipper_navigate`: Sequence multiple button presses and optionally return the resulting screen in a single turn.
- `flipper_unlock`: Dismiss lockscreen or unlock PIN.

### 2. CLI Execution & Diagnostics
- `flipper_status`: Check USB connectivity, port accessibility, CLI readiness, and screen capture status.
- `flipper_run_cli`: Execute standard one-shot commands (`device_info`, `power info`, `date`, `uptime`).
- `flipper_listen`: Run streaming commands with a timeout (`subghz rx`, `ir rx`, `rfid read`, `nfc rx`).
- `flipper_reboot`: Reboot the device (normal, OS update, or DFU mode).

### 3. File System & Storage
- `flipper_storage_list`: List files and directories on `/ext` (microSD) or `/int` (internal flash).
- `flipper_storage_info`: Query total and available filesystem bytes.
- `flipper_storage_read`: Read text or binary files from the device.
- `flipper_storage_upload`: Upload local files to Flipper with automated MD5 hash verification.
- `flipper_storage_download`: Download files from Flipper to the local host.
- `flipper_storage_mkdir`: Create directories on the device.
- `flipper_storage_delete`: Delete files or directories.
- `flipper_find`: Recursively locate files matching wildcard patterns.
- `flipper_index`: Produce a high-level survey of device firmware, SD card tree, and radio capabilities.

### 4. Applications & Automation
- `flipper_loader_open`: Launch a built-in application (e.g. `Infrared`, `Sub-GHz`, `NFC`, `Bad USB`).
- `flipper_loader_close`: Close the currently running application.
- `flipper_apps_running`: Check active application and loader state.
- `flipper_js_run`: Run a JavaScript script directly on the Flipper.
- `flipper_badusb_create`: Create and upload a BadUSB DuckyScript file.
- `flipper_badusb_run`: Open BadUSB app with the target payload ready to execute.
- `flipper_subghz_tx`: Transmit a saved Sub-GHz file.
- `flipper_led`: Set RGB notification LED color and brightness.
- `flipper_vibro`: Trigger vibration motor.

### 5. Persistent Knowledge Base
- `flipper_kb_save`: Save task notes, captured frequencies, or device mappings to persistent local knowledge base (`knowledge/`).
- `flipper_kb_list`: List saved knowledge base documents.
- `flipper_kb_read`: Read knowledge base note.
- `flipper_kb_search`: Search notes across previous sessions.

---

## Standard Agent Workflow

1. **Pre-flight Check**:
   Always run `flipper_status` first to confirm USB connection and port availability.
2. **Interactive Navigation**:
   Use `flipper_navigate(keys=[...], screenshot=True)` to traverse menus and inspect the screen after presses in a single tool call to conserve turns.
3. **File Management**:
   Always use MD5-verified uploads via `flipper_storage_upload` when staging BadUSB or Sub-GHz assets.
4. **Knowledge Sharing**:
   Save important findings (e.g., detected frequencies, device profiles) using `flipper_kb_save` so future sessions have context.

# Troubleshooting

Start with `flipper_status`. Its first line that is not OK usually names the
problem.

## `NOT CONNECTED: Flipper not found on USB`

- Check the cable (some USB-C cables are charge-only) and that the Flipper is on.
- The Flipper disappears from USB for a few seconds while it reboots; retry.
- If the port is not detected automatically, set `FLIPPER_PORT` (for example
  `COM10` or `/dev/ttyACM0`).

## `PORT BUSY` / "Access is denied" / "Permission denied"

Another program has the serial port open. Only one can hold it at a time.

- Close qFlipper.
- Close or disconnect any browser tab using Web Serial, such as
  lab.flipper.net. The browser keeps the port even when the tab is in the
  background.
- On Linux, add your user to the `dialout` group and log in again.

## Screenshot fails: "Flipper refused the RPC session"

The Flipper is locked. On Momentum firmware, RPC sessions are refused while the
device is keypad- or PIN-locked, even if the screen does not obviously show it.

- Keypad lock: run `flipper_unlock` (it sends Back three times).
- PIN lock: enter the PIN on the device.
- To allow screenshots while locked, enable the "Allow RPC While Locked"
  option in the Momentum settings. This lets any USB-connected computer view
  and control a locked Flipper, so leave it off unless you need it.

## `NO CLI` / "Flipper CLI not responding"

The port opened but no prompt came back.

- An app on the Flipper may be using the USB link (for example a USB-UART
  bridge or a HID app such as Bad USB). Close the app on the device.
- Unplug and replug the cable.

## A command returns nothing or times out

- Commands that listen until interrupted (`subghz rx`, `ir rx`, `rfid read`,
  `ikey read`, `log`) never return on their own. Use `flipper_listen` instead
  of `flipper_run_cli`.
- Some commands refuse to run while an app is open and say so. Close the app
  with `flipper_loader_close`.

## The screenshot is sideways

Apps that use the screen in portrait orientation are returned in the display's
native landscape layout. Only the 180-degree flip is corrected.

## Button presses do nothing

- If the Flipper is locked, presses are ignored until it is unlocked.
- Add a larger `delay_ms` to `flipper_navigate` if an app is slow to redraw
  and presses are being missed.

import asyncio
import hashlib
import os
import tempfile
import unittest
from unittest import mock

import flipper_mcp
from flipper_mcp.tools import badusb, device, gui, storage, survey

HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


class FakeFlipper:
    """Stands in for transport.Flipper: records CLI lines, replays canned output."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.commands = []
        self.written = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def cli(self, line, timeout=15):
        self.commands.append(line)
        return self.responses.get(line, "")

    def write_file(self, path, data, chunk=4096):
        self.written[path] = data


def listed_tools():
    return {t.name: t for t in asyncio.run(flipper_mcp.mcp.list_tools())}


class Registration(unittest.TestCase):
    def test_all_tools_registered(self):
        tools = listed_tools()
        self.assertEqual(len(tools), 32)
        self.assertTrue(all(name.startswith("flipper_") for name in tools))

    def test_every_tool_declares_all_four_hints(self):
        for name, tool in listed_tools().items():
            self.assertIsNotNone(tool.annotations, f"{name} has no annotations")
            for hint in HINTS:
                self.assertIsInstance(getattr(tool.annotations, hint), bool, f"{name}.{hint}")

    def test_every_tool_has_a_description(self):
        for name, tool in listed_tools().items():
            self.assertTrue((tool.description or "").strip(), name)

    def test_risky_tools_are_flagged(self):
        tools = listed_tools()
        for name in ("flipper_storage_delete", "flipper_storage_write", "flipper_reboot",
                     "flipper_run_cli", "flipper_js_run", "flipper_badusb_run"):
            self.assertTrue(tools[name].annotations.destructiveHint, name)
        for name in ("flipper_subghz_tx", "flipper_listen", "flipper_badusb_run", "flipper_run_cli"):
            self.assertTrue(tools[name].annotations.openWorldHint, name)

    def test_read_only_tools_do_not_claim_to_change_things(self):
        tools = listed_tools()
        for name in ("flipper_info", "flipper_status", "flipper_storage_list", "flipper_storage_read",
                     "flipper_index", "flipper_find", "flipper_kb_list", "flipper_kb_read", "flipper_kb_search"):
            ann = tools[name].annotations
            self.assertTrue(ann.readOnlyHint, name)
            self.assertFalse(ann.destructiveHint, name)


class Storage(unittest.TestCase):
    def upload(self, remote_md5):
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, "a.bin")
            with open(local, "wb") as fh:
                fh.write(b"payload")
            fake = FakeFlipper({'storage md5 "/ext/a.bin"': remote_md5})
            with mock.patch.object(storage, "Flipper", return_value=fake):
                return storage.flipper_storage_write("/ext/a.bin", local), fake

    def test_upload_verified_by_md5(self):
        result, fake = self.upload(hashlib.md5(b"payload").hexdigest())
        self.assertEqual(result, "OK: 7 bytes -> /ext/a.bin")
        self.assertEqual(fake.written["/ext/a.bin"], b"payload")

    def test_upload_reports_md5_mismatch(self):
        result, _ = self.upload("0" * 32)
        self.assertTrue(result.startswith("MISMATCH"))


class BadUsb(unittest.TestCase):
    def test_adds_txt_extension_only_when_missing(self):
        self.assertEqual(badusb._normalise_name("hello"), "hello.txt")
        self.assertEqual(badusb._normalise_name("hello.TXT"), "hello.TXT")

    def test_create_normalises_line_endings_and_path(self):
        script = "STRING hi\r\nENTER"
        data = b"STRING hi\nENTER"
        fake = FakeFlipper({'storage md5 "/ext/badusb/demo.txt"': hashlib.md5(data).hexdigest()})
        with mock.patch.object(badusb, "Flipper", return_value=fake):
            result = badusb.flipper_badusb_create("demo", script)
        self.assertEqual(fake.written, {"/ext/badusb/demo.txt": data})
        self.assertEqual(result, "OK: wrote 15 bytes -> /ext/badusb/demo.txt")

    def test_run_opens_the_bad_usb_app_with_the_script(self):
        fake = FakeFlipper()
        with mock.patch.object(badusb, "Flipper", return_value=fake):
            badusb.flipper_badusb_run("demo")
        self.assertEqual(fake.commands, ['loader open "Bad USB" "/ext/badusb/demo.txt"'])


class Gui(unittest.TestCase):
    def test_navigate_rejects_bad_keys_without_touching_the_device(self):
        with mock.patch.object(gui, "Flipper", side_effect=AssertionError("device opened")):
            self.assertEqual(gui.flipper_navigate("up,sideways"), "invalid keys: ['sideways']")
            self.assertEqual(gui.flipper_navigate("ok:medium"), "invalid keys: ['ok:medium']")

    def test_navigate_sends_each_press(self):
        fake = FakeFlipper()
        with mock.patch.object(gui, "Flipper", return_value=fake):
            result = gui.flipper_navigate("down, ok:long", delay_ms=0)
        self.assertEqual(fake.commands, ["input send down short", "input send ok long"])
        self.assertEqual(result, "sent 2 presses: down ok:long")


class Survey(unittest.TestCase):
    TREE = {
        'storage list "/ext"': "[D] subghz\n[F] notes.txt 12b",
        'storage list "/ext/subghz"': "[F] garage.sub 100b",
    }

    def test_find_walks_subdirectories(self):
        with mock.patch.object(survey, "Flipper", return_value=FakeFlipper(self.TREE)):
            self.assertEqual(survey.flipper_find("GARAGE"), "/ext/subghz/garage.sub")

    def test_find_reports_no_match(self):
        with mock.patch.object(survey, "Flipper", return_value=FakeFlipper(self.TREE)):
            self.assertIn("no match for 'zzz'", survey.flipper_find("zzz"))

    def test_find_respects_call_budget(self):
        fake = FakeFlipper(self.TREE)
        with mock.patch.object(survey, "Flipper", return_value=fake):
            survey.flipper_find("garage", max_calls=1)
        self.assertEqual(fake.commands, ['storage list "/ext"'])


class Device(unittest.TestCase):
    def test_status_when_flipper_missing(self):
        with mock.patch.object(device, "find_port", side_effect=RuntimeError("Flipper not found")):
            self.assertEqual(device.flipper_status(), "NOT CONNECTED: Flipper not found")

    def test_led_clamps_channels(self):
        fake = FakeFlipper()
        with mock.patch.object(device, "Flipper", return_value=fake):
            device.flipper_led(300, -5, 128)
        self.assertEqual(fake.commands, ["led r 255", "led g 0", "led b 128"])


if __name__ == "__main__":
    unittest.main()

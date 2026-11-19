import asyncio
import hashlib
import os
import tempfile
import unittest
from unittest import mock

import flipper_mcp
from flipper_mcp.tools import apps, badusb, device, gui, knowledge, storage, subghz, survey

HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


class FakeFlipper:
    """Stands in for transport.Flipper: records CLI lines, replays canned output."""

    def __init__(self, responses=None, files=None):
        self.responses = responses or {}
        self.files = files or {}
        self.commands = []
        self.written = {}
        self.s = mock.Mock()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def cli(self, line, timeout=15):
        self.commands.append(line)
        return self.responses.get(line, "")

    def cli_timed(self, line, seconds):
        self.commands.append(line)
        return self.responses.get(line, "")

    def read_file(self, path, limit=1 << 20):
        data = self.files.get(path, b"")
        return data[:limit]

    def write_file(self, path, data, chunk=4096):
        self.written[path] = data

    def screen_frame(self, timeout=5):
        return bytes(1024), 0


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

    def test_storage_list(self):
        fake = FakeFlipper({'storage list "/ext"': "[D] subghz\n[F] a.txt 5b"})
        with mock.patch.object(storage, "Flipper", return_value=fake):
            res = storage.flipper_storage_list("/ext")
        self.assertIn("a.txt", res)

    def test_storage_info(self):
        fake = FakeFlipper({'storage info /ext': "Label: SD\nType: FAT32"})
        with mock.patch.object(storage, "Flipper", return_value=fake):
            res = storage.flipper_storage_info()
        self.assertIn("FAT32", res)

    def test_storage_read_text_and_binary(self):
        fake = FakeFlipper(files={"/ext/a.txt": b"hello text", "/ext/b.bin": b"\x00\xff\xfe"})
        with mock.patch.object(storage, "Flipper", return_value=fake):
            self.assertEqual(storage.flipper_storage_read("/ext/a.txt"), "hello text")
            b64 = storage.flipper_storage_read("/ext/b.bin")
            self.assertTrue(b64.startswith("base64:"))

    def test_storage_download(self):
        fake = FakeFlipper(files={"/ext/a.txt": b"download content"})
        with tempfile.TemporaryDirectory() as tmp:
            local = os.path.join(tmp, "out.txt")
            with mock.patch.object(storage, "Flipper", return_value=fake):
                res = storage.flipper_storage_download("/ext/a.txt", local)
            self.assertTrue(res.startswith("OK: 16 bytes"))
            with open(local, "rb") as fh:
                self.assertEqual(fh.read(), b"download content")

    def test_storage_mkdir_and_delete(self):
        fake = FakeFlipper()
        with mock.patch.object(storage, "Flipper", return_value=fake):
            storage.flipper_storage_mkdir("/ext/newdir")
            storage.flipper_storage_delete("/ext/old.txt")
        self.assertEqual(fake.commands, ['storage mkdir "/ext/newdir"', 'storage remove "/ext/old.txt"'])


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

    def test_press_sends_key(self):
        fake = FakeFlipper()
        with mock.patch.object(gui, "Flipper", return_value=fake):
            res = gui.flipper_press("ok", "short")
        self.assertEqual(fake.commands, ["input send ok short"])
        self.assertEqual(res, "sent ok short")

    def test_unlock(self):
        fake = FakeFlipper()
        with mock.patch.object(gui, "Flipper", return_value=fake), \
                mock.patch.object(gui.time, "sleep"):
            res = gui.flipper_unlock()
        self.assertEqual(fake.commands, ["input send back short"] * 3)
        self.assertEqual(res[0], "sent Back x3")

    def test_screenshot(self):
        fake = FakeFlipper()
        with tempfile.TemporaryDirectory() as tmp:
            save_path = os.path.join(tmp, "screen.png")
            with mock.patch.object(gui, "Flipper", return_value=fake):
                img = gui.flipper_screenshot(save_path=save_path)
            self.assertTrue(os.path.isfile(save_path))
            self.assertIsInstance(img, gui.Image)
            self.assertTrue(len(img.data) > 0)


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

    def test_index_surveys_device(self):
        responses = {
            "device_info": "hardware_name: F7\nfirmware_version: 0.12\n",
            "loader info": "Desktop",
            "storage info /ext": "Total: 32GB\nFree: 16GB\n",
            'storage list "/ext"': "[D] subghz\n[F] notes.txt 12b",
        }
        with mock.patch.object(survey, "Flipper", return_value=FakeFlipper(responses)):
            res = survey.flipper_index(depth=1)
        self.assertIn("# FLIPPER INDEX", res)
        self.assertIn("F7", res)
        self.assertIn("Desktop", res)


class Device(unittest.TestCase):
    def test_status_when_flipper_missing(self):
        with mock.patch.object(device, "find_port", side_effect=RuntimeError("Flipper not found")):
            self.assertEqual(device.flipper_status(), "NOT CONNECTED: Flipper not found")

    def test_status_when_connected(self):
        responses = {
            "device_info": "hardware_name: F7\nfirmware_version: 0.12\n",
            "loader info": "Desktop",
            "uptime": "uptime: 1h",
        }
        fake = FakeFlipper(responses)
        with mock.patch.object(device, "find_port", return_value="COM3"), \
                mock.patch.object(device, "Flipper", return_value=fake):
            res = device.flipper_status()
        self.assertIn("port: COM3", res)
        self.assertIn("cli: OK", res)
        self.assertIn("screen: OK (unlocked)", res)

    def test_info(self):
        fake = FakeFlipper({"device_info": "hw: F7"})
        with mock.patch.object(device, "Flipper", return_value=fake):
            self.assertEqual(device.flipper_info(), "hw: F7")

    def test_run_cli(self):
        fake = FakeFlipper({"help": "commands: ps, free"})
        with mock.patch.object(device, "Flipper", return_value=fake):
            self.assertEqual(device.flipper_run_cli("help"), "commands: ps, free")

    def test_listen(self):
        fake = FakeFlipper({"subghz rx 433920000 0": "received 433.92 packet"})
        with mock.patch.object(device, "Flipper", return_value=fake):
            res = device.flipper_listen("subghz rx 433920000 0", seconds=1)
        self.assertEqual(res, "received 433.92 packet")

    def test_led_clamps_channels(self):
        fake = FakeFlipper()
        with mock.patch.object(device, "Flipper", return_value=fake):
            device.flipper_led(300, -5, 128)
        self.assertEqual(fake.commands, ["led r 255", "led g 0", "led b 128"])

    def test_vibro(self):
        fake = FakeFlipper({"vibro 1": ""})
        with mock.patch.object(device, "Flipper", return_value=fake):
            self.assertEqual(device.flipper_vibro(True), "vibro on")

    def test_reboot(self):
        fake = FakeFlipper()
        with mock.patch.object(device, "Flipper", return_value=fake), \
                mock.patch.object(device.time, "sleep"):
            device.flipper_reboot("normal")
            device.flipper_reboot("dfu")
        fake.s.write.assert_has_calls([mock.call(b"power reboot\r"), mock.call(b"power reboot2dfu\r")])


class Apps(unittest.TestCase):
    def test_apps_running(self):
        fake = FakeFlipper({"loader info": "Sub-GHz"})
        with mock.patch.object(apps, "Flipper", return_value=fake):
            self.assertEqual(apps.flipper_apps_running(), "Sub-GHz")

    def test_loader_open_and_close(self):
        fake = FakeFlipper()
        with mock.patch.object(apps, "Flipper", return_value=fake):
            apps.flipper_loader_open("Sub-GHz", "/ext/subghz/test.sub")
            apps.flipper_loader_close()
        self.assertEqual(fake.commands, [
            'loader open "Sub-GHz" "/ext/subghz/test.sub"',
            'loader close',
        ])

    def test_launch_fap(self):
        fake = FakeFlipper()
        with mock.patch.object(apps, "Flipper", return_value=fake), \
                mock.patch.object(apps.time, "sleep"):
            res = apps.flipper_launch_fap("/ext/apps/GPIO/test.fap")
        self.assertIn("launch sent: /ext/apps/GPIO/test.fap", res)
        fake.s.write.assert_called_with(b'loader open "/ext/apps/GPIO/test.fap"\r')

    def test_js_run(self):
        fake = FakeFlipper({'js /ext/.tmp/mcp_run.js': "js result: 42"})
        with mock.patch.object(apps, "Flipper", return_value=fake):
            res = apps.flipper_js_run("let x = 42; print(x);")
        self.assertEqual(res, "js result: 42")
        self.assertEqual(fake.written["/ext/.tmp/mcp_run.js"], b"let x = 42; print(x);")


class SubGhz(unittest.TestCase):
    def test_subghz_tx(self):
        fake = FakeFlipper({'subghz tx_from_file "/ext/subghz/test.sub" 433920000': "Transmitting..."})
        with mock.patch.object(subghz, "Flipper", return_value=fake):
            res = subghz.flipper_subghz_tx("/ext/subghz/test.sub", 433920000)
        self.assertEqual(res, "Transmitting...")


class Knowledge(unittest.TestCase):
    def test_kb_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb_dir = os.path.join(tmp, "knowledge")
            with mock.patch.object(knowledge.kb, "KB_DIR", kb_dir):
                save_res = knowledge.flipper_kb_save("SubGhz Notes", "Found 433.92 gate remote", append=False)
                self.assertIn("saved -> knowledge/subghz-notes.md", save_res)

                list_res = knowledge.flipper_kb_list()
                self.assertIn("subghz-notes : SubGhz Notes", list_res)

                read_res = knowledge.flipper_kb_read("subghz-notes")
                self.assertIn("Found 433.92 gate remote", read_res)

                search_res = knowledge.flipper_kb_search("gate")
                self.assertIn("Found 433.92 gate remote", search_res)


if __name__ == "__main__":
    unittest.main()

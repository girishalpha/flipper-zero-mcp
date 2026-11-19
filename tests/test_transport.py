import unittest
from unittest import mock

from fakes import FakeSerial, screen_frame_message

from flipper_mcp import transport

FRAMEBUFFER = bytes(range(256)) * 4  # 1024 bytes, like a real 128x64 1-bpp frame


def open_flipper(fake: FakeSerial) -> transport.Flipper:
    """Build a Flipper session on top of a fake serial port."""
    with mock.patch.object(transport, "find_port", return_value="FAKE"), \
            mock.patch.object(transport.serial, "Serial", return_value=fake), \
            mock.patch.object(transport.time, "sleep"):
        return transport.Flipper()


class FindPort(unittest.TestCase):
    def test_env_var_wins(self):
        with mock.patch.dict("os.environ", {"FLIPPER_PORT": "COM99"}):
            self.assertEqual(transport.find_port(), "COM99")

    def test_detects_by_usb_id(self):
        port = mock.Mock(vid=0x0483, pid=0x5740, device="COM7")
        other = mock.Mock(vid=0x1234, pid=0x5678, device="COM1")
        with mock.patch.dict("os.environ", clear=True), \
                mock.patch.object(transport.serial.tools.list_ports, "comports", return_value=[other, port]):
            self.assertEqual(transport.find_port(), "COM7")

    def test_not_found_raises(self):
        with mock.patch.dict("os.environ", clear=True), \
                mock.patch.object(transport.serial.tools.list_ports, "comports", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "Flipper not found"):
                transport.find_port()


class Clean(unittest.TestCase):
    def test_strips_echo_ansi_and_prompt(self):
        raw = b"device_info\r\nhw: f7\r\n\x1b[32mgreen\x1b[0m\r\n>: "
        self.assertEqual(transport.Flipper._clean(raw, "device_info"), "hw: f7\ngreen")

    def test_keeps_output_when_no_echo(self):
        self.assertEqual(transport.Flipper._clean(b"hello\r\n>: ", "other"), "hello")


class Session(unittest.TestCase):
    def test_breaks_rpc_on_open_and_closes_on_exit(self):
        fake = FakeSerial()
        with open_flipper(fake):
            self.assertEqual(fake.writes[0], b"\x03\r")
            self.assertTrue(fake.dtr and fake.rts)
        self.assertTrue(fake.closed)

    def test_unresponsive_cli_raises(self):
        with mock.patch.object(transport.Flipper, "_read_prompt", side_effect=TimeoutError):
            with self.assertRaisesRegex(RuntimeError, "CLI not responding"):
                open_flipper(FakeSerial())


class Cli(unittest.TestCase):
    def test_returns_cleaned_output(self):
        f = open_flipper(FakeSerial({"device_info": b"hardware_name: f7\r\n"}))
        self.assertEqual(f.cli("device_info"), "hardware_name: f7")

    def test_command_with_no_output_is_empty(self):
        self.assertEqual(open_flipper(FakeSerial()).cli("vibro 0"), "")

    def test_timed_command_that_finishes_by_itself(self):
        f = open_flipper(FakeSerial({"ir rx": b"done\r\n"}))
        self.assertEqual(f.cli_timed("ir rx", 1), "done")

    def test_timed_command_is_stopped_with_ctrl_c(self):
        fake = FakeSerial(silent={"subghz rx 433920000 0"})
        f = open_flipper(fake)
        f.cli_timed("subghz rx 433920000 0", 0.2)
        self.assertIn(b"\x03", fake.writes)


class Files(unittest.TestCase):
    def test_read_file(self):
        f = open_flipper(FakeSerial({'storage read "/ext/a.txt"': b"Size: 5\r\nhello\r\n"}))
        self.assertEqual(f.read_file("/ext/a.txt"), b"hello")

    def test_read_file_honours_limit(self):
        f = open_flipper(FakeSerial({'storage read "/ext/a.txt"': b"Size: 5\r\nhello\r\n"}))
        self.assertEqual(f.read_file("/ext/a.txt", limit=3), b"hel")

    def test_read_missing_file_raises(self):
        f = open_flipper(FakeSerial({'storage read "/ext/x"': b"Storage error: file not found\r\n"}))
        with self.assertRaisesRegex(IOError, "file not found"):
            f.read_file("/ext/x")

    def test_write_file_is_chunked_and_lossless(self):
        fake = FakeSerial()
        f = open_flipper(fake)
        f.write_file("/ext/a.txt", b"0123456789", chunk=4)
        self.assertEqual(fake.chunks, [b"0123", b"4567", b"89"])
        self.assertIn(b'storage remove "/ext/a.txt"\r', fake.writes)  # replaces any old file first


class ScreenFrame(unittest.TestCase):
    def test_returns_framebuffer_and_orientation(self):
        fake = FakeSerial(rpc_frame=screen_frame_message(FRAMEBUFFER, orientation=1))
        data, orientation = open_flipper(fake).screen_frame()
        self.assertEqual(data, FRAMEBUFFER)
        self.assertEqual(orientation, 1)

    def test_stops_the_rpc_session_afterwards(self):
        fake = FakeSerial(rpc_frame=screen_frame_message(FRAMEBUFFER))
        open_flipper(fake).screen_frame()
        self.assertEqual(fake.writes[-1], b"\x05\x08\x02\x9a\x01\x00")  # stop_session

    def test_locked_device_gives_actionable_error(self):
        fake = FakeSerial(rpc_frame=b"Session start error: locked\r\n")
        with self.assertRaisesRegex(RuntimeError, "locked"):
            open_flipper(fake).screen_frame()

    def test_no_frame_times_out(self):
        with self.assertRaises(TimeoutError):
            open_flipper(FakeSerial()).screen_frame(timeout=0.2)


if __name__ == "__main__":
    unittest.main()

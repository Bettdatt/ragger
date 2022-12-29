from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

from ragger.backend import SpeculosBackend
from ragger.firmware import Firmware
from ragger.navigator import Navigator, NavIns


class TestNavigator(TestCase):

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.backend = MagicMock()
        self.firmware = Firmware("nanos", "2.1")
        self.callbacks = dict()
        self.navigator = Navigator(self.backend, self.firmware, self.callbacks)

    def tearDown(self):
        self.directory.cleanup()

    @property
    def pathdir(self) -> Path:
        return Path(self.directory.name)

    def test__get_snaps_dir_path(self):
        name = "some_name"
        expected = self.pathdir / "snapshots-tmp" / self.firmware.device / name
        result = self.navigator._get_snaps_dir_path(self.pathdir, name, False)
        self.assertEqual(result, expected)

        expected = self.pathdir / "snapshots" / self.firmware.device / name
        result = self.navigator._get_snaps_dir_path(self.pathdir, name, True)
        self.assertEqual(result, expected)

    def test__checks_snaps_dir_path_ok_creates_dir(self):
        name = "some_name"
        expected = self.pathdir / "snapshots" / self.firmware.device / name
        navigator = Navigator(self.backend, self.firmware, self.callbacks, golden_run=True)
        self.assertFalse(expected.exists())
        result = navigator._check_snaps_dir_path(self.pathdir, name, True)
        self.assertEqual(result, expected)
        self.assertTrue(expected.exists())

    def test__checks_snaps_dir_path_ok_dir_exists(self):
        name = "some_name"
        expected = self.pathdir / "snapshots" / self.firmware.device / name
        navigator = Navigator(self.backend, self.firmware, self.callbacks, golden_run=True)
        expected.mkdir(parents=True)
        self.assertTrue(expected.exists())
        result = navigator._check_snaps_dir_path(self.pathdir, name, True)
        self.assertEqual(result, expected)
        self.assertTrue(expected.exists())

    def test__checks_snaps_dir_path_nok_raises(self):
        name = "some_name"
        expected = self.pathdir / "snapshots" / self.firmware.device / name
        self.assertFalse(expected.exists())
        with self.assertRaises(ValueError):
            self.navigator._check_snaps_dir_path(self.pathdir, name, True)
        self.assertFalse(expected.exists())

    def test___init_snaps_temp_dir_ok_creates_dir(self):
        name = "some_name"
        expected = self.pathdir / "snapshots-tmp" / self.firmware.device / name
        self.assertFalse(expected.exists())
        result = self.navigator._init_snaps_temp_dir(self.pathdir, name)
        self.assertEqual(result, expected)
        self.assertTrue(expected.exists())

    def test___init_snaps_temp_dir_ok_unlink_files(self):
        existing_files = ["first", "second"]
        name = "some_name"
        expected = self.pathdir / "snapshots-tmp" / self.firmware.device / name
        expected.mkdir(parents=True)
        for filename in existing_files:
            (expected / filename).touch()
            self.assertTrue((expected / filename).exists())
        result = self.navigator._init_snaps_temp_dir(self.pathdir, name)
        self.assertEqual(result, expected)
        self.assertTrue(expected.exists())
        for filename in existing_files:
            self.assertFalse((expected / filename).exists())

    def test__get_snap_path(self):
        path = Path("not important")
        testset = {1: "00001", 11: "00011", 111: "00111", 1111: "01111", 11111: "11111"}
        for (index, name) in testset.items():
            name += ".png"
            self.assertEqual(self.navigator._get_snap_path(path, index), path / name)

    def test__compare_snap_with_timeout_ok(self):
        self.navigator._backend.compare_screen_with_snapshot.side_effect = [False, True]
        self.assertTrue(self.navigator._compare_snap_with_timeout("not important", 1))
        self.assertEqual(self.navigator._backend.compare_screen_with_snapshot.call_count, 2)

    def test__compare_snap_with_timeout_ok_no_timeout(self):
        self.navigator._backend.compare_screen_with_snapshot.return_value = True
        self.assertTrue(self.navigator._compare_snap_with_timeout("not important", 0))
        self.assertEqual(self.navigator._backend.compare_screen_with_snapshot.call_count, 1)

    def test__compare_snap_with_timeout_nok(self):
        self.navigator._backend.compare_screen_with_snapshot.return_value = False
        self.assertFalse(self.navigator._compare_snap_with_timeout("not important", 0))
        self.assertEqual(self.navigator._backend.compare_screen_with_snapshot.call_count, 1)

    def test_compare_snap_ok(self):
        self.navigator._backend.compare_screen_with_snapshot.return_value = True
        self.assertIsNone(self.navigator._compare_snap(self.pathdir, self.pathdir, 1))

    def test_compare_snap_nok_raises(self):
        self.navigator._backend.compare_screen_with_snapshot.return_value = False
        with self.assertRaises(AssertionError):
            self.navigator._compare_snap(self.pathdir, self.pathdir, 1)

    def test_navigate_nok_raises(self):
        with self.assertRaises(NotImplementedError):
            self.navigator.navigate([NavIns(2)])

    def test_navigate_ok_raises(self):
        cb1, cb2 = MagicMock(), MagicMock()
        ni1, ni2 = NavIns(1, (1, ), {'1': 1}), NavIns(2, (2, ), {'2': 2})
        self.navigator._callbacks = {ni1.id: cb1, ni2.id: cb2}
        self.navigator.navigate([ni1, ni2])
        for cb, ni in [(cb1, ni1), (cb2, ni2)]:
            self.assertEqual(cb.call_count, 1)
            self.assertEqual(cb.call_args, (ni.args, ni.kwargs))

    def test_navigate_and_compare_ok(self):
        cb1, cb2 = MagicMock(), MagicMock()
        ni1, ni2 = NavIns(1, (1, ), {'1': 1}), NavIns(2, (2, ), {'2': 2})
        s1, s2, s3 = 1, 2, 3
        self.navigator._callbacks = {ni1.id: cb1, ni2.id: cb2}
        with patch("ragger.navigator.navigator.sleep") as patched_sleep:
            self.navigator.navigate_and_compare(self.pathdir, self.pathdir, [ni1, ni2], s1, s2, s3)
        self.assertEqual(patched_sleep.call_count, 1 + 1 + 2)  # first + last + 2 instructions
        self.assertEqual(
            patched_sleep.call_args_list,
            [
                ((s1, ), ),  # first sleep
                ((s2, ), ),  # first instruction sleep
                ((s2, ), ),  # second instruction sleep
                ((s3, ), ),  # last sleep
            ])

    def test_navigate_and_compare_ok_golden(self):
        self.navigator._golden_run = True
        cb1, cb2 = MagicMock(), MagicMock()
        ni1, ni2 = NavIns(1, (1, ), {'1': 1}), NavIns(2, (2, ), {'2': 2})
        s1, s2, s3 = 1, 2, 3
        self.navigator._callbacks = {ni1.id: cb1, ni2.id: cb2}
        with patch("ragger.navigator.navigator.sleep") as patched_sleep:
            self.navigator.navigate_and_compare(self.pathdir, self.pathdir, [ni1, ni2], s1, s2, s3)
        self.assertEqual(patched_sleep.call_count, 1 + 1 + 2)  # first + last + 2 instructions
        self.assertEqual(patched_sleep.call_args_list, [
            ((s1 * self.navigator.GOLDEN_INSTRUCTION_SLEEP_MULTIPLIER_FIRST, ), ),
            ((s2 * self.navigator.GOLDEN_INSTRUCTION_SLEEP_MULTIPLIER_MIDDLE, ), ),
            ((s2 * self.navigator.GOLDEN_INSTRUCTION_SLEEP_MULTIPLIER_MIDDLE, ), ),
            ((s3 * self.navigator.GOLDEN_INSTRUCTION_SLEEP_MULTIPLIER_LAST, ), ),
        ])

    def test_navigate_until_text_and_compare_is_not_Speculos(self):
        self.assertIsNone(self.navigator.navigate_until_text_and_compare(None, None, None))

    def test_navigate_until_text_and_compare_ok_no_snapshots(self):
        self.navigator._backend = MagicMock(spec=SpeculosBackend)
        self.navigator._backend.compare_screen_with_text.side_effect = [False, False, True]
        self.navigator.navigate = MagicMock()
        text = "some triggering text"
        cb1, cb2 = MagicMock(), MagicMock()
        ni1, ni2 = NavIns(1, (1, ), {'1': 1}), NavIns(2, (2, ), {'2': 2})
        self.navigator._callbacks = {ni1.id: cb1, ni2.id: cb2}
        self.navigator._compare_snap = MagicMock()

        self.assertIsNone(self.navigator.navigate_until_text_and_compare(ni1, ni2, text))
        # no snapshot to check, so no call
        self.assertFalse(self.navigator._compare_snap.called)
        # backend compare function called 3 times with the text
        self.assertEqual(self.navigator._backend.compare_screen_with_text.call_count, 3)
        self.assertEqual(self.navigator._backend.compare_screen_with_text.call_args_list,
                         [((text, ), )] * 3)
        # backend compare function return 2 time False, then True
        # so 2 calls with the navigate instruction, and the final one with the validation instruction
        self.assertEqual(self.navigator.navigate.call_count, 3)
        self.assertEqual(self.navigator.navigate.call_args_list, [(([ni1], ), ), (([ni1], ), ),
                                                                  (([ni2], ), )])

    def test_navigate_until_text_and_compare_ok_with_snapshots(self):
        self.navigator._backend = MagicMock(spec=SpeculosBackend)
        self.navigator._backend.compare_screen_with_text.side_effect = [False, False, True]
        self.navigator.navigate = MagicMock()
        text = "some triggering text"
        cb1, cb2 = MagicMock(), MagicMock()
        ni1, ni2 = NavIns(1, (1, ), {'1': 1}), NavIns(2, (2, ), {'2': 2})
        self.navigator._callbacks = {ni1.id: cb1, ni2.id: cb2}
        self.navigator._compare_snap = MagicMock()

        self.assertIsNone(
            self.navigator.navigate_until_text_and_compare(ni1, ni2, text, self.pathdir,
                                                           self.pathdir))
        # snapshots checked, so 3 calls
        self.assertEqual(self.navigator._compare_snap.call_count, 3)
        # backend compare function called 3 times with the text
        self.assertEqual(self.navigator._backend.compare_screen_with_text.call_count, 3)
        self.assertEqual(self.navigator._backend.compare_screen_with_text.call_args_list,
                         [((text, ), )] * 3)
        # backend compare function return 2 time False, then True
        # so 2 calls with the navigate instruction, and the final one with the validation instruction
        self.assertEqual(self.navigator.navigate.call_count, 3)
        self.assertEqual(self.navigator.navigate.call_args_list, [(([ni1], ), ), (([ni1], ), ),
                                                                  (([ni2], ), )])

    def test_navigate_until_text_and_compare_nok_timeout(self):
        self.navigator._backend = MagicMock(spec=SpeculosBackend)
        self.navigator._backend.compare_screen_with_text.return_value = False
        self.navigator.navigate = MagicMock()
        cb = MagicMock()
        ni = NavIns(1, (1, ), {'1': 1})
        self.navigator._callbacks = {ni.id: cb}
        self.navigator._compare_snap = MagicMock()

        with self.assertRaises(TimeoutError):
            self.navigator.navigate_until_text_and_compare(ni, None, "not important", timeout=0)

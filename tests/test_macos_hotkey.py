import unittest
from unittest.mock import patch

from bonaventure.macos_hotkey import GlobalHotKey


class Function:
    def __init__(self, fn):
        self.fn = fn

    def __call__(self, *args):
        return self.fn(*args)


class Carbon:
    def __init__(self, failure=0):
        self.removed = self.unregistered = 0
        self.signature = int.from_bytes(b"BVNT", "big")
        self.GetApplicationEventTarget = Function(lambda: 1)
        def install(target, callback, count, spec, data, out):
            self.spec = (spec._obj.event_class, spec._obj.event_kind)
            out._obj.value = 100
            return 0
        def register(code, modifiers, identifier, target, options, out):
            self.registered = (code, modifiers)
            if not failure:
                out._obj.value = 101
            return failure
        def parameter(event, name, type_, actual_type, size, actual_size, out):
            out._obj.signature, out._obj.id = self.signature, 1
            return 0
        self.InstallEventHandler = Function(install)
        self.RegisterEventHotKey = Function(register)
        self.GetEventParameter = Function(parameter)
        self.UnregisterEventHotKey = Function(self.unregister)
        self.RemoveEventHandler = Function(self.remove)

    def unregister(self, ref):
        self.unregistered += 1

    def remove(self, ref):
        self.removed += 1


class HotKeyTests(unittest.TestCase):
    def test_binds_command_option_b_and_dispatches_only_its_own_events(self):
        carbon, actions = Carbon(), []
        with patch("bonaventure.macos_hotkey.C.CDLL", return_value=carbon):
            key = GlobalHotKey(lambda: actions.append("toggle"))
        self.assertEqual(carbon.registered, (11, 0x900))
        self.assertEqual(carbon.spec, (int.from_bytes(b"keyb", "big"), 6))
        self.assertEqual(key.callback(None, None, None), 0)
        carbon.signature = int.from_bytes(b"OTHR", "big")
        self.assertEqual(key.callback(None, None, None), -9874)
        self.assertEqual(actions, ["toggle"])
        key.close()
        key.close()
        self.assertEqual((carbon.unregistered, carbon.removed), (1, 1))

    def test_registration_conflict_removes_event_handler(self):
        carbon = Carbon(failure=-9878)
        with patch("bonaventure.macos_hotkey.C.CDLL", return_value=carbon):
            with self.assertRaisesRegex(RuntimeError, "another app"):
                GlobalHotKey(lambda: None)
        self.assertEqual((carbon.unregistered, carbon.removed), (0, 1))


if __name__ == "__main__":
    unittest.main()

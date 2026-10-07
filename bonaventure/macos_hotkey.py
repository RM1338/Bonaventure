"""Register Option-Command-B system-wide without a keyboard event monitor."""
import ctypes as C
from ctypes.util import find_library


class EventType(C.Structure):
    _fields_ = [("event_class", C.c_uint32), ("event_kind", C.c_uint32)]


class HotKeyID(C.Structure):
    _fields_ = [("signature", C.c_uint32), ("id", C.c_uint32)]


class GlobalHotKey:
    def __init__(self, action):
        self.action = action
        self.library = C.CDLL(find_library("Carbon") or "/System/Library/Frameworks/Carbon.framework/Carbon")
        lib = self.library
        callback_type = C.CFUNCTYPE(C.c_int32, C.c_void_p, C.c_void_p, C.c_void_p)
        lib.GetApplicationEventTarget.restype = C.c_void_p
        lib.InstallEventHandler.argtypes = [C.c_void_p, callback_type, C.c_uint32, C.POINTER(EventType), C.c_void_p, C.POINTER(C.c_void_p)]
        lib.InstallEventHandler.restype = C.c_int32
        lib.RegisterEventHotKey.argtypes = [C.c_uint32, C.c_uint32, HotKeyID, C.c_void_p, C.c_uint32, C.POINTER(C.c_void_p)]
        lib.RegisterEventHotKey.restype = C.c_int32
        lib.GetEventParameter.argtypes = [C.c_void_p, C.c_uint32, C.c_uint32, C.c_void_p, C.c_uint32, C.c_void_p, C.c_void_p]
        lib.GetEventParameter.restype = C.c_int32
        lib.UnregisterEventHotKey.argtypes = [C.c_void_p]
        lib.RemoveEventHandler.argtypes = [C.c_void_p]
        self.handler, self.hotkey = C.c_void_p(), C.c_void_p()
        self.identifier = HotKeyID(int.from_bytes(b"BVNT", "big"), 1)

        def callback(next_handler, event, data):
            identifier = HotKeyID()
            status = lib.GetEventParameter(event, int.from_bytes(b"----", "big"), int.from_bytes(b"hkid", "big"),
                                           None, C.sizeof(identifier), None, C.byref(identifier))
            if status or identifier.signature != self.identifier.signature or identifier.id != self.identifier.id:
                return -9874  # eventNotHandledErr
            try:
                self.action()
            except Exception as error:
                print(f"[launcher] Shortcut callback failed: {error}")
            return 0

        self.callback = callback_type(callback)  # Retain the C callback for registration's lifetime.
        spec = EventType(int.from_bytes(b"keyb", "big"), 6)  # kEventHotKeyPressed
        target = lib.GetApplicationEventTarget()
        status = lib.InstallEventHandler(target, self.callback, 1, C.byref(spec), None, C.byref(self.handler))
        if status:
            raise RuntimeError(f"Cannot install global shortcut handler ({status})")
        status = lib.RegisterEventHotKey(11, 0x100 | 0x800, self.identifier, target, 0, C.byref(self.hotkey))
        if status:
            self.close()
            raise RuntimeError(f"Option-Command-B could not be registered ({status}); another app may use it")

    def close(self):
        if self.hotkey.value:
            self.library.UnregisterEventHotKey(self.hotkey)
            self.hotkey = C.c_void_p()
        if self.handler.value:
            self.library.RemoveEventHandler(self.handler)
            self.handler = C.c_void_p()

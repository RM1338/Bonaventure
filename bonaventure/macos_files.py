"""Open file panels above the notch without blocking AppKit's event loop."""
from threading import Event


def choose_files(api, multiple, extensions):
    import AppKit
    from PyObjCTools import AppHelper

    done, result, errors = Event(), [], []

    def present():
        controls = api._mac_controls
        if controls.file_dialog_open:
            done.set()
            return
        native = api._launcher.native
        controls.file_dialog_open = True
        panel = None
        original_level = None

        def finish(response=None, error=None):
            try:
                if error is not None:
                    errors.append(error)
                elif response == AppKit.NSModalResponseOK:
                    result.extend(str(url.path()) for url in panel.URLs())
            except Exception as failure:
                errors.append(failure)
            finally:
                try:
                    if panel is not None:
                        panel.orderOut_(None)
                    if original_level is not None:
                        native.setLevel_(original_level)
                    if controls.expanded and not controls.stopped:
                        native.makeKeyAndOrderFront_(None)
                except Exception as failure:
                    errors.append(failure)
                finally:
                    controls.file_dialog_open = False
                    controls.file_picker = None
                    done.set()

        try:
            original_level = native.level()
            native.setLevel_(AppKit.NSNormalWindowLevel)
            panel = AppKit.NSOpenPanel.openPanel()
            controls.file_picker = panel  # Retain until the completion callback.
            panel.setTitle_("Select patient history" if multiple else "Select chest X-ray")
            panel.setCanChooseFiles_(True)
            panel.setCanChooseDirectories_(False)
            panel.setAllowsMultipleSelection_(multiple)
            panel.setAllowedFileTypes_(extensions)
            panel.setAllowsOtherFileTypes_(True)
            panel.setLevel_(original_level + 1)
            panel.center()
            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            panel.beginWithCompletionHandler_(finish)
        except Exception as error:
            finish(error=error)

    AppHelper.callAfter(present)
    done.wait()  # Only the bridge worker waits; AppKit stays responsive.
    if errors:
        raise errors[0]
    return tuple(result) or None

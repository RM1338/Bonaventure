"""Entry point: pick the native desktop shell for this OS before importing any GUI code.
Linux -> linux_app, macOS -> macos_app, Windows -> windows_app. All share desktop.Api and the pipeline."""
import sys


def main():
    if sys.platform == "darwin":
        from .macos_app import main as launch
    elif sys.platform == "win32":
        from .windows_app import main as launch
    else:
        from .linux_app import main as launch
    launch()


if __name__ == "__main__":
    main()

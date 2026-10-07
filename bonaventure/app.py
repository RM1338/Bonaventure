"""Entry point: pick the native desktop shell for this OS before importing any GUI code.
Linux -> linux_app (Hyprland/GTK), macOS -> macos_app (notch + menu bar). Both share desktop.Api and the whole pipeline."""
import sys


def main():
    if sys.platform == "darwin":
        from .macos_app import main as launch
    else:
        from .linux_app import main as launch
    launch()


if __name__ == "__main__":
    main()

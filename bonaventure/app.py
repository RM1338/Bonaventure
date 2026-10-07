"""Entry point: pick the native desktop shell for this OS before importing any GUI code.
Linux -> linux_app (Hyprland/GTK). The window code is kept apart from desktop.Api and the pipeline, so another OS only
needs its own shell module."""
import sys


def main():
    if sys.platform == "darwin":
        sys.exit("The macOS shell is still in review and not on this branch yet.")
    from .linux_app import main as launch
    launch()


if __name__ == "__main__":
    main()

"""Select the native desktop implementation before importing GUI code."""
import sys


def main():
    if sys.platform == "darwin":
        from .macos_app import main as launch
    else:
        from .linux_app import main as launch
    launch()


if __name__ == "__main__":
    main()

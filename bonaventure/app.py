"""macOS branch entry point; reject other platforms before native imports."""
import sys


def main():
    if sys.platform != "darwin":
        sys.exit("This is the macOS branch. For Omarchy/Linux, use the main branch; for Windows, use the windows branch.")
    from .macos_app import main as launch
    launch()


if __name__ == "__main__":
    main()

"""Install a local .app and optional login agent, using the existing checkout and venv."""
import argparse
import os
import plistlib
import shlex
import subprocess
import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABEL = "org.bonaventure.desktop"


def launcher_script(root, logs):
    return "\n".join((
        "#!/bin/bash", "set -e",
        'export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"',
        f"mkdir -p {shlex.quote(str(logs))}",
        f"cd {shlex.quote(str(logs))}",
        'export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1',
        'if command -v brew >/dev/null 2>&1; then',
        '  export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"',
        'fi',
        f"export PYTHONPATH={shlex.quote(str(root))}${{PYTHONPATH:+:$PYTHONPATH}}",
        f"exec {shlex.quote(str(root / '.venv/bin/python'))} -u -m bonaventure.app "
        f">> {shlex.quote(str(logs / 'bonaventure.log'))} 2>&1", "",
    ))


def install_files(root, home, login=True):
    app = home / "Applications/Bonaventure.app"
    contents = app / "Contents"
    executable = contents / "MacOS/Bonaventure"
    logs = home / "Library/Logs/Bonaventure"
    if app.exists():
        info_path = contents / "Info.plist"
        if not info_path.is_file() or plistlib.loads(info_path.read_bytes()).get("CFBundleIdentifier") != LABEL:
            raise RuntimeError(f"Another app already exists at {app}; no changes made")
    executable.parent.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    executable.write_text(launcher_script(root, logs))
    executable.chmod(0o755)
    info = dict(CFBundleIdentifier=LABEL, CFBundleName="Bonaventure", CFBundleDisplayName="Bonaventure",
                CFBundleExecutable="Bonaventure", CFBundlePackageType="APPL", CFBundleVersion="1",
                CFBundleShortVersionString="0.1", LSUIElement=True, NSHighResolutionCapable=True,
                NSMicrophoneUsageDescription="Bonaventure uses the microphone to dictate the current presentation locally.")
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(info, stream)
    agent = home / "Library/LaunchAgents" / f"{LABEL}.plist"
    if login:
        agent.parent.mkdir(parents=True, exist_ok=True)
        config = dict(Label=LABEL, ProgramArguments=[str(executable)], WorkingDirectory=str(home),
                      RunAtLoad=True, KeepAlive=dict(SuccessfulExit=False), ThrottleInterval=10,
                      LimitLoadToSessionType="Aqua", ProcessType="Interactive",
                      StandardOutPath=str(logs / "service.log"), StandardErrorPath=str(logs / "service.log"))
        with agent.open("wb") as stream:
            plistlib.dump(config, stream)
    return app, agent


def launcher_message(command):
    """Ask the app, not just launchctl, whether its native launcher is ready."""
    import socket
    path = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "bonaventure.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.5)
        connection.connect(str(path))
        connection.sendall(command.encode())
        response = connection.recv(1024)
    return json.loads(response).get("ready") is True


def wait_for_launcher(timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if launcher_message("status"):
                return launcher_message("show")
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-login", action="store_true", help="install the app without enabling login startup")
    parser.add_argument("--uninstall", action="store_true", help="remove this app wrapper and login agent; keep project/model files")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Run this installer on your Mac, using .venv/bin/python")
    home = Path.home()
    agent = home / "Library/LaunchAgents" / f"{LABEL}.plist"
    service = f"gui/{os.getuid()}/{LABEL}"
    domain = f"gui/{os.getuid()}"
    if args.uninstall:
        import shutil
        app = home / "Applications/Bonaventure.app"
        if app.exists():
            with (app / "Contents/Info.plist").open("rb") as stream:
                if plistlib.load(stream).get("CFBundleIdentifier") != LABEL:
                    raise RuntimeError("App identifier differs; no app files removed")
        subprocess.run(["launchctl", "bootout", service], capture_output=True)
        agent.unlink(missing_ok=True)
        if app.exists():
            shutil.rmtree(app)
        print("Removed Bonaventure app wrapper and login startup. Project and models remain in place.")
        return
    # Detect the old instance rather than launching a service that immediately
    # exits after toggling an existing Terminal-owned process.
    import socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.5)
            connection.connect(str(Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "bonaventure.sock"))
    except OSError:
        pass
    else:
        parser.error("Quit the running Bonaventure instance from its menu bar menu, then run this command again")
    python = ROOT / ".venv/bin/python"
    if not python.exists():
        parser.error("The project's .venv/bin/python is missing")
    if not (ROOT / "run.sh").is_file():
        parser.error("The project's run.sh is missing")
    subprocess.run(["/bin/bash", str(ROOT / "run.sh"), "--check-runtime"], check=True)
    app, agent = install_files(ROOT, home, login=not args.no_login)
    subprocess.run(["launchctl", "bootout", service], capture_output=True)
    if args.no_login:
        agent.unlink(missing_ok=True)
        subprocess.run(["open", str(app)], check=True)
    else:
        subprocess.run(["launchctl", "bootstrap", domain, str(agent)], check=True)
    print("Waiting for the launcher to start…", flush=True)
    if not wait_for_launcher():
        logs = home / "Library/Logs/Bonaventure"
        excerpts = []
        for name in ("bonaventure.log", "service.log"):
            path = logs / name
            if path.is_file():
                excerpts.append(f"\n{name}:\n" + "\n".join(path.read_text(errors="replace").splitlines()[-20:]))
        parser.error("App installed, but its launcher did not become ready. "
                     "Inspect the startup logs below (models may still be loading separately). "
                     + "".join(excerpts) + f"\nLogs: {logs}")
    print(f"Installed and launcher opened: {app}")
    print("Runs without Terminal. Login startup: " + ("off" if args.no_login else "on"))
    print(f"Logs: {home / 'Library/Logs/Bonaventure/bonaventure.log'}")
    print("This development app uses the current project folder and .venv; keep both in place.")


if __name__ == "__main__":
    main()

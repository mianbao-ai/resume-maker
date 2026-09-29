import re
import socket
import subprocess
import os
import signal


def _list_listening_ports_pids() -> dict[int, list[int]]:
    """Return port -> [pids] for all TCP listeners. One system call (ss or lsof)."""
    port_pids: dict[int, list[int]] = {}
    if os.name != "posix":
        return port_pids
    # Prefer ss on Linux (fast); fallback to lsof
    try:
        out = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout:
            # LINE: LISTEN 0 128 0.0.0.0:5100 0.0.0.0:* users:(("python",pid=12345,fd=3))
            for line in out.stdout.splitlines():
                if "pid=" not in line:
                    continue
                m = re.search(r":(\d+)\s+.*pid=(\d+)", line)
                if m:
                    port, pid = int(m.group(1)), int(m.group(2))
                    port_pids.setdefault(port, []).append(pid)
            return port_pids
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fallback: lsof one shot
    try:
        out = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n", "-F", "pn"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0 or not out.stdout:
            return port_pids
        pid = None
        for line in out.stdout.strip().splitlines():
            if line.startswith("p"):
                pid = int(line[1:]) if line[1:].isdigit() else None
            elif line.startswith("n") and pid is not None:
                # n*:5100 or n127.0.0.1:5100
                m = re.search(r":(\d+)$", line)
                if m:
                    port = int(m.group(1))
                    port_pids.setdefault(port, []).append(pid)
                pid = None
        return port_pids
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return port_pids


def find_available_port(start_port: int = 5000, end_port: int = 5500) -> int:
    """Find an available port in the specified range"""
    for port in range(start_port, end_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("localhost", port))
                return port
        except OSError:
            # Port is already in use, try next one
            continue

    # If no port is available in the range, raise an exception
    raise RuntimeError(f"No available port found in range {start_port}-{end_port}")

def get_pids_on_port(port: int) -> list[int]:
    """Return list of PIDs listening on the given port (Linux/macOS: lsof)."""
    try:
        out = subprocess.run(
            ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        raise RuntimeError("lsof not found, cannot resolve process by port")
    if out.returncode != 0 or not out.stdout.strip():
        return []
    return [int(x) for x in out.stdout.strip().split() if x.strip().isdigit()]


def _get_cmdline(pid: int) -> str:
    """Return process command line (Linux: /proc; macOS: ps)."""
    if os.name != "posix":
        return ""
    # Linux
    try:
        with open(f"/proc/{pid}/cmdline") as f:
            return f.read().replace("\x00", " ")
    except (OSError, FileNotFoundError):
        pass
    # macOS
    out = subprocess.run(
        ["ps", "-p", str(pid), "-o", "args="],
        capture_output=True,
        text=True,
        timeout=2,
    )
    return out.stdout.strip() if out.returncode == 0 else ""


def _get_cwd(pid: int) -> str:
    """Return process cwd (Linux only; macOS returns '')."""
    if os.name != "posix":
        return ""
    try:
        return os.path.realpath(f"/proc/{pid}/cwd")
    except (OSError, FileNotFoundError):
        return ""


def is_server_process(pid: int) -> bool:
    """True if this PID looks like our FastAPI server (python main.py in server)."""
    cmd = _get_cmdline(pid)
    if "main.py" not in cmd or "python" not in cmd.lower():
        return False
    # cwd = _get_cwd(pid)
    # # Must be running from our server tree (cwd contains 'fastapi' on Linux)
    # if cwd and "fastapi" not in cwd:
    #     return False
    return True


def get_server_pids_on_port(port: int) -> list[int]:
    """Return PIDs listening on port that are our server process only."""
    return [p for p in get_pids_on_port(port) if is_server_process(p)]


def get_server_ports_pids(start_port: int, end_port: int) -> list[tuple[int, list[int]]]:
    """Return [(port, [pids])] for our server in port range. One system call, no 401x lsof."""
    all_ = _list_listening_ports_pids()
    out: list[tuple[int, list[int]]] = []
    for port in range(start_port, end_port + 1):
        pids = all_.get(port, [])
        ours = [p for p in pids if is_server_process(p)]
        if ours:
            out.append((port, ours))
    return out


def kill_pids(pids: list[int], sig: int = signal.SIGTERM) -> None:
    for pid in pids:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            raise RuntimeError(f"Cannot kill process {pid} (permission denied)")

"""Misbehaving child entries for the sandbox tests. Loaded only inside the sandbox child."""
import subprocess
import sys
import time


def echo(header, payload):
    return {"ok": True, "n": len(payload), "header": header}


def env_keys(header, payload):
    import os
    return {"ok": True, "keys": sorted(os.environ)}


def hog_memory(header, payload):
    """Commits 1 GB, then returns normally: only a memory cap can make this fail."""
    chunks = [bytearray(64 * 1024 * 1024) for _ in range(16)]
    return {"ok": True, "allocated": len(chunks)}


def spin_cpu(header, payload):
    """Burns 20 s of CPU, then returns normally: only a CPU cap below that can make this fail."""
    end = time.process_time() + 20
    while time.process_time() < end:
        pass
    return {"ok": True}


def sleep_forever(header, payload):
    time.sleep(3600)


def spawn_process(header, payload):
    try:
        subprocess.run([sys.executable, "-c", "pass"], timeout=20)
        return {"ok": True, "spawned": True}
    except OSError as exc:
        return {"ok": True, "spawned": False, "winerror": getattr(exc, "winerror", None)}


def fork_process(header, payload):
    import os
    try:
        pid = os.fork()
    except OSError as exc:
        return {"ok": True, "forked": False, "errno": exc.errno}
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)
    return {"ok": True, "forked": True}


def start_thread(header, payload):
    import threading
    try:
        threading.Thread(target=lambda: None).start()
    except RuntimeError:
        return {"ok": True, "started": False}
    return {"ok": True, "started": True}


def read_parent(header, payload):
    """Tries to open the parent's environment, memory and open files through /proc (Linux)."""
    import os
    opened = []
    for name in ("environ", "mem", "fd"):
        path = "/proc/%d/%s" % (os.getppid(), name)
        try:
            os.listdir(path) if name == "fd" else open(path, "rb").read(1)
            opened.append(name)
        except OSError:
            pass
    return {"ok": True, "opened": opened}


def crash(header, payload):
    import os
    os._exit(7)

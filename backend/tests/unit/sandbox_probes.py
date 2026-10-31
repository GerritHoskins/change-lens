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


def crash(header, payload):
    import os
    os._exit(7)

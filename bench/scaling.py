"""Does the spell-check loop scale to 2 CPUs? 1 thread vs 2 threads vs 2
processes on the same total work (prints one JSON line per mode)."""

import json
import random
import string
import sys
import sysconfig
import threading
import time
from multiprocessing import Process

rng = random.Random(9)
letters = string.ascii_lowercase
VOCAB = {"".join(rng.choice(letters) for _ in range(rng.randrange(4, 11))) for _ in range(200_000)}
WORDS = list(VOCAB)
TEXT = " ".join(rng.choice(WORDS) for _ in range(2_000_000))


def check(words):
    bad = 0
    for w in words:
        if w not in VOCAB:
            bad += 1
    return bad


def run(mode):
    # A fresh split every time: str objects cache their hash, so reused words
    # would skip the hashing a real spell-check pays once per word.
    words = TEXT.split()
    half = len(words) // 2
    parts = [words[:half], words[half:]]
    t = time.perf_counter()
    if mode == "1 thread":
        check(words)
    else:
        make = threading.Thread if mode == "2 threads" else Process
        workers = [make(target=check, args=(p,)) for p in parts]
        for w in workers:
            w.start()
        for w in workers:
            w.join()
    return time.perf_counter() - t


def main():
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    for mode in ("1 thread", "2 threads", "2 processes"):
        dt = min(run(mode) for _ in range(2))
        print(json.dumps({"mode": mode, "seconds": round(dt, 3), "gil": gil,
                          "free_threading_build": bool(sysconfig.get_config_var("Py_GIL_DISABLED"))}), flush=True)


if __name__ == "__main__":
    main()

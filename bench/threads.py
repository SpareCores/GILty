"""Could GILty scale with threads if Python had no GIL?

Each thread babbles its own chain (independent walks over the model), so the
algorithm itself needs no coordination at all. Two layouts:
  shared    all threads read one model
  private   every thread builds its own model (its own objects: no
            reference counts shared between threads, but N copies in cache)
Aggregate words/s for 1, 2, 4, 8 threads; JSON lines.
"""

import json
import sys
import sysconfig
import threading
import time

sys.path.insert(0, ".")
from gilty.markov import Babbler, load_book, tokenize, train  # noqa: E402

WORDS = 2_000_000
ORDER = 1


def bench(threads, layout, tokens, shared_model):
    def work(i, out):
        model = train(tokens, ORDER) if layout == "private" else shared_model
        b = Babbler(model, ORDER, tokens, seed=i)
        ready.wait()
        t = time.perf_counter()
        for _ in range(WORDS // 100_000):
            b.babble(100_000)
        out[i] = time.perf_counter() - t

    ready = threading.Event()
    out = [0.0] * threads
    ts = [threading.Thread(target=work, args=(i, out)) for i in range(threads)]
    for t in ts:
        t.start()
    time.sleep(0.5 + (2.0 if layout == "private" else 0))  # let private models build
    t0 = time.perf_counter()
    ready.set()
    for t in ts:
        t.join()
    wall = time.perf_counter() - t0
    return threads * WORDS / wall


def main():
    tokens = tokenize(load_book())
    model = train(tokens, ORDER)
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()
    for layout in ("shared", "private"):
        for n in (1, 2, 4, 8):
            rate = max(bench(n, layout, tokens, model) for _ in range(2))
            print(json.dumps({"python": sys.version.split()[0], "free_threading": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
                              "gil": gil, "layout": layout, "threads": n, "words_per_second": round(rate)}), flush=True)


if __name__ == "__main__":
    main()

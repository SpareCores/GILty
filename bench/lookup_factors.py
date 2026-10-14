"""Which property of 'random dict lookups' opens the gap between machines?

Variants of `for k in keys: s += d[k]` over n entries:
  base         probe keys are equal-but-distinct int objects, shuffled
  identical    probe keys are the dict's own key objects, shuffled
  sequential   distinct probe keys in insertion order
  smallvals    values are small ints (cached objects), probe keys distinct
  nosum        distinct probe keys, the value is fetched but not added
"""

import gc
import json
import random
import sys
import time


def best_of(fn, repeat=3):
    best = None
    for _ in range(repeat):
        gc.collect()
        t = time.perf_counter()
        fn()
        dt = time.perf_counter() - t
        best = dt if best is None or dt < best else best
    return best


def make(n, variant):
    rng = random.Random(1)
    stored = [i * 7919 + 100_000 for i in range(n)]
    order = list(range(n))
    rng.shuffle(order)
    vals = [i % 200 for i in range(n)] if variant == "smallvals" else [i + 1000 for i in range(n)]
    d = dict(zip((stored[i] for i in order), (vals[i] for i in order)))  # inserted in random order
    if variant == "identical":
        keys = [stored[i] for i in order]
    elif variant == "sequential":
        keys = [int(str(stored[i])) for i in order]  # dict order = insertion order
    else:
        keys = [int(str(k)) for k in stored]
        rng.shuffle(keys)
    if variant == "nosum":
        def run():
            for k in keys:
                d[k]
    else:
        def run():
            s = 0
            for k in keys:
                s += d[k]
    return run


def main():
    sizes = [int(a) for a in sys.argv[1:]] or [50_000, 100_000, 150_000, 250_000]
    for variant in ("base", "identical", "sequential", "smallvals", "nosum"):
        for n in sizes:
            dt = best_of(make(n, variant))
            print(json.dumps({"variant": variant, "size": n, "seconds": dt, "ns": dt / n * 1e9}), flush=True)


if __name__ == "__main__":
    main()

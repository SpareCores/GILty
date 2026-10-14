"""Where between cache and RAM does the hash-table gap peak?

Random dict lookups, set membership and a sparse Game of Life step (Counter
over packed cell ids) at many working-set sizes, best of three, JSON lines.
"""

import gc
import json
import random
import time
from collections import Counter


def best_of(fn, repeat=3):
    best = None
    for _ in range(repeat):
        gc.collect()
        t = time.perf_counter()
        fn()
        dt = time.perf_counter() - t
        best = dt if best is None or dt < best else best
    return best


def dict_lookup(n):
    d = {i * 7919: i for i in range(n)}
    keys = [i * 7919 for i in range(n)]
    random.shuffle(keys)

    def run():
        s = 0
        for k in keys:
            s += d[k]

    return run


def set_member(n):
    s = {i * 7919 for i in range(n)}
    probe = [random.randrange(n * 7919) for _ in range(n)]

    def run():
        c = 0
        for p in probe:
            if p in s:
                c += 1

    return run


W = 1 << 16
OFFS = [dx * W + dy for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


def life_step(n):
    """One generation of a random soup with n live cells (packed x*W+y ids)."""
    side = int((n / 0.3) ** 0.5)
    live = {random.randrange(side) * W + random.randrange(side) for _ in range(n)}

    def run():
        counts = Counter()
        for c in live:
            for o in OFFS:
                counts[c + o] += 1
        return {c for c, k in counts.items() if k == 3 or (k == 2 and c in live)}

    return run


SIZES = [10_000, 30_000, 60_000, 100_000, 150_000, 250_000, 400_000, 700_000, 1_000_000]


def main():
    for name, make in (("dict_lookup", dict_lookup), ("set_member", set_member), ("life_step", life_step)):
        for n in SIZES:
            fn = make(n)
            dt = best_of(fn)
            print(json.dumps({"kernel": name, "size": n, "seconds": dt, "ns_per_item": dt / n * 1e9}), flush=True)
            del fn


if __name__ == "__main__":
    main()

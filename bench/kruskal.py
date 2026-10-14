"""Prototype: Kruskal maze generation with a dict-based union-find, per size.

Cells have scrambled ids; walls are visited in random order; find() follows
parent links through a dict (path halving), so every step depends on the
previous lookup: chains of dependent, scattered memory accesses.
"""

import gc
import json
import random
import sys
import time


def kruskal(side, rng):
    n = side * side
    ids = list(range(n))
    rng.shuffle(ids)
    walls = []
    for x in range(side):
        for y in range(side):
            c = x * side + y
            if x + 1 < side:
                walls.append((ids[c], ids[c + side]))
            if y + 1 < side:
                walls.append((ids[c], ids[c + 1]))
    rng.shuffle(walls)
    parent = {i: i for i in ids}
    rank = dict.fromkeys(ids, 0)

    def run():
        p = dict(parent)
        r = dict(rank)
        carved = 0
        for a, b in walls:
            while p[a] != a:  # find with path halving
                p[a] = p[p[a]]
                a = p[a]
            while p[b] != b:
                p[b] = p[p[b]]
                b = p[b]
            if a != b:
                if r[a] < r[b]:
                    a, b = b, a
                p[b] = a
                if r[a] == r[b]:
                    r[a] += 1
                carved += 1
        return carved

    return run


def main():
    sides = [int(a) for a in sys.argv[1:]] or [150, 200, 250, 300, 350, 400, 500, 700]
    for side in sides:
        run = kruskal(side, random.Random(42))
        best = None
        for _ in range(3):
            gc.collect()
            t = time.perf_counter()
            run()
            dt = time.perf_counter() - t
            best = dt if best is None or dt < best else best
        print(json.dumps({"side": side, "cells": side * side, "seconds": best, "ns_per_cell": best / side / side * 1e9}), flush=True)


if __name__ == "__main__":
    main()

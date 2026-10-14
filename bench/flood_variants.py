"""Flood variants on one maze: which formulation leans hardest on the caches?

  adjacency  dict id -> tuple of neighbour ids (scrambled ids), parent dict
  computed   open passages as a set of wall ids; neighbours computed by
             arithmetic (fresh int objects), visited/distance dicts keyed by
             cell (inserted in random order)
  weighted   'computed' plus a terrain-cost dict lookup per neighbour
"""

import gc
import json
import random
import sys
import time
from collections import deque


def carve(side, rng):
    """Recursive-backtracker maze; returns the set of open passages, each as
    min(a, b) * 2 + (vertical) on cell ids c = x * side + y."""
    n = side * side
    seen = bytearray(n)
    stack = [0]
    seen[0] = 1
    passages = set()
    while stack:
        c = stack[-1]
        x, y = divmod(c, side)
        opts = []
        if x > 0 and not seen[c - side]:
            opts.append(c - side)
        if x < side - 1 and not seen[c + side]:
            opts.append(c + side)
        if y > 0 and not seen[c - 1]:
            opts.append(c - 1)
        if y < side - 1 and not seen[c + 1]:
            opts.append(c + 1)
        if not opts:
            stack.pop()
            continue
        nb = opts[rng.randrange(len(opts))]
        seen[nb] = 1
        lo = min(c, nb)
        passages.add(lo * 2 + (abs(nb - c) == side))
        stack.append(nb)
    return passages


def flood_computed(side, passages, start, terrain=None):
    dist = {start: 0}
    q = deque([start])
    pop, push = q.popleft, q.append
    while q:
        c = pop()
        d = dist[c]
        x, y = divmod(c, side)
        for nb, wall in ((c - side, (c - side) * 2 + 1), (c + side, c * 2 + 1), (c - 1, (c - 1) * 2), (c + 1, c * 2)):
            if wall in passages and nb not in dist:
                dist[nb] = d + (terrain[nb] if terrain is not None else 1)
                push(nb)
    return dist


def adjacency(side, passages, rng):
    ids = list(range(side * side))
    rng.shuffle(ids)
    adj = {i: [] for i in ids}
    for p in passages:
        lo, vertical = divmod(p, 2)
        hi = lo + (side if vertical else 1)
        adj[ids[lo]].append(ids[hi])
        adj[ids[hi]].append(ids[lo])
    return {k: tuple(v) for k, v in adj.items()}, ids


def flood_adjacency(adj, start):
    parent = {start: start}
    q = deque([start])
    pop, push = q.popleft, q.append
    while q:
        c = pop()
        for nb in adj[c]:
            if nb not in parent:
                parent[nb] = c
                push(nb)
    return parent


def best_of(fn, repeat=3):
    best = None
    for _ in range(repeat):
        gc.collect()
        t = time.perf_counter()
        fn()
        dt = time.perf_counter() - t
        best = dt if best is None or dt < best else best
    return best


def main():
    sides = [int(a) for a in sys.argv[1:]] or [250, 300, 350, 400, 500]
    for side in sides:
        rng = random.Random(7)
        passages = carve(side, rng)
        # passages inserted in random order, like a set that grew over time
        passages = set(rng.sample(sorted(passages), len(passages)))
        cells = list(range(side * side))
        rng.shuffle(cells)
        terrain = {c: 1000 + rng.randrange(9) for c in cells}
        adj, ids = adjacency(side, passages, rng)
        for name, fn in (
            ("adjacency", lambda: flood_adjacency(adj, ids[0])),
            ("computed", lambda: flood_computed(side, passages, 0)),
            ("weighted", lambda: flood_computed(side, passages, 0, terrain)),
        ):
            dt = best_of(fn)
            print(json.dumps({"variant": name, "side": side, "seconds": dt, "ns_per_cell": dt / side / side * 1e9}), flush=True)


if __name__ == "__main__":
    main()

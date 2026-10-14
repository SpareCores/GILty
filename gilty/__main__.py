"""GILty: babbles in the style of Moby-Dick, as fast as one core allows.

    gilty                 babble forever; a live view on a terminal, one
                          status line per interval otherwise (logs)
    gilty --words N       stop after N words and print a summary
    gilty --bench         train and babble a fixed amount, print JSON

GILty is single-threaded by nature: its work is a chain of dependent hash
lookups, which the GIL serialises across threads (and which free-threaded
Python slows down, as the threads share the model). One fast core with a
fast cache is all it can use.
"""

import argparse
import json
import os
import platform
import sys
import textwrap
import time

from gilty import __version__
from gilty.markov import Babbler, load_book, tokenize, train

CHUNK = 100_000  # words generated between status checks


# Arm cores by (CPU implementer, CPU part), as lscpu names them: Linux on Arm
# has no "model name" in /proc/cpuinfo. Arm Ltd. cores cover AWS Graviton
# (2: Neoverse-N1, 3: V1, 4: V2, 5: V3) and most other Arm servers.
ARM_PARTS = {
    ("0x41", "0xd0c"): "Neoverse-N1",
    ("0x41", "0xd40"): "Neoverse-V1",
    ("0x41", "0xd49"): "Neoverse-N2",
    ("0x41", "0xd4f"): "Neoverse-V2",
    ("0x41", "0xd84"): "Neoverse-V3",
    ("0x41", "0xd8e"): "Neoverse-N3",
    ("0x41", "0xd08"): "Cortex-A72",
    ("0x41", "0xd0b"): "Cortex-A76",
    ("0xc0", "0xac3"): "Ampere-1",
    ("0xc0", "0xac4"): "Ampere-1a",
}


def cpu_model(cpuinfo="/proc/cpuinfo"):
    """The CPU model: "model name" on x86, the core named from its
    implementer and part number on Arm."""
    fields = {}
    try:
        with open(cpuinfo) as f:
            for line in f:
                key, sep, value = line.partition(":")
                key = key.strip()
                if not sep:
                    continue
                if key in ("model name", "Model"):
                    return value.strip()
                fields.setdefault(key, value.strip())
    except OSError:
        pass
    if "CPU part" in fields:
        impl, part = fields.get("CPU implementer", "").lower(), fields["CPU part"].lower()
        return ARM_PARTS.get((impl, part), f"Arm core {impl}/{part}")
    return platform.processor() or platform.machine()


def cpu_short(model=None):
    """A short CPU name for status lines: "EPYC 7571", "Xeon 8259CL",
    "Core i9-14900K", "Neoverse-V3"."""
    import re

    m = model or cpu_model()
    m = re.sub(r"\((R|TM)\)|\bCPU\b|@.*$|\b(AMD|Intel|Platinum|Gold|Silver|Processor)\b|\d+-Core", " ", m)
    return " ".join(m.split()) or "unknown CPU"


def where():
    """The machine, as far as the process can tell: the node name in
    Kubernetes (set from the downward API) and the CPU model."""
    parts = [cpu_model()]
    if os.environ.get("NODE_NAME"):
        parts.insert(0, os.environ["NODE_NAME"])
    return ", ".join(parts)


def sentence(words):
    """The tail of the babble, starting at a sentence if one starts there."""
    for i, w in enumerate(words[:-1]):
        if w.endswith((".", "!", "?")) and words[i + 1][:1].isupper():
            return " ".join(words[i + 1 :])
    return "… " + " ".join(words)


def prepare(order):
    t = time.perf_counter()
    tokens = tokenize(load_book())
    model = train(tokens, order)
    return tokens, model, time.perf_counter() - t


def run_bench(args):
    tokens, model, train_s = prepare(args.order)
    b = Babbler(model, args.order, tokens, seed=args.seed)
    t = time.perf_counter()
    remaining = args.words
    while remaining > 0:
        b.babble(min(CHUNK, remaining))
        remaining -= CHUNK
    gen_s = time.perf_counter() - t
    print(json.dumps({
        "version": __version__, "python": platform.python_version(), "cpu": cpu_model(),
        "order": args.order, "states": len(model), "train_seconds": round(train_s, 3),
        "words": args.words, "babble_seconds": round(gen_s, 3), "words_per_second": round(args.words / gen_s),
    }))


def run_log(args):
    """One status line per interval: for logs and pipes."""
    print(f"GILty {__version__} on {where()}, Python {platform.python_version()}", flush=True)
    tokens, model, train_s = prepare(args.order)
    print(f"learned Moby-Dick in {train_s:.1f} s: {len(tokens):,} words, {len(model):,} states", flush=True)
    b = Babbler(model, args.order, tokens, seed=args.seed)
    cpu = cpu_short()
    start = last = time.perf_counter()
    last_words = 0
    while args.words is None or b.words < args.words:
        tail = b.babble(CHUNK)
        now = time.perf_counter()
        if now - last >= args.interval:
            rate = (b.words - last_words) / (now - last)
            print(f"{cpu:<14.14} {rate:>11,.0f} words/s | {sentence(tail)[:60]}", flush=True)
            last, last_words = now, b.words
    total = time.perf_counter() - start
    print(f"babbled {b.words:,} words in {total:.1f} s: {b.words / total:,.0f} words/s", flush=True)


def run_live(args):
    """A live view: the babble scrolls, the speed updates ten times a second."""
    cols = max(40, min(os.get_terminal_size().columns, 100))
    out = sys.stdout
    out.write(f"\x1b[1mGILty {__version__}\x1b[0m  on {where()}, Python {platform.python_version()}\n")
    out.write("learning Moby-Dick… ")
    out.flush()
    tokens, model, train_s = prepare(args.order)
    out.write(f"{train_s:.1f} s ({len(tokens):,} words, {len(model):,} states)\n\n")
    b = Babbler(model, args.order, tokens, seed=args.seed)
    start = last = time.perf_counter()
    last_words = 0
    rate = 0.0
    lines = 6
    out.write("\n" * (lines + 2))
    try:
        while args.words is None or b.words < args.words:
            tail = b.babble(CHUNK // 4, keep=120)
            now = time.perf_counter()
            if now - last < 0.1:
                continue
            rate = (b.words - last_words) / (now - last)
            last, last_words = now, b.words
            text = textwrap.wrap(sentence(tail), cols - 2)[-lines:]
            out.write(f"\x1b[{lines + 2}F")
            for i in range(lines):
                out.write("\x1b[2K\x1b[3m" + (text[i] if i < len(text) else "") + "\x1b[0m\n")
            out.write(f"\x1b[2K\n\x1b[2K\x1b[1m{rate:,.0f} words/s\x1b[0m   {b.words:,} words in {now - start:.1f} s\n")
            out.flush()
    except KeyboardInterrupt:
        pass
    total = time.perf_counter() - start
    out.write(f"\nbabbled {b.words:,} words in {total:.1f} s: \x1b[1m{b.words / total:,.0f} words/s\x1b[0m\n")


def main(argv=None):
    p = argparse.ArgumentParser(prog="gilty", description=__doc__.split("\n\n")[0])
    p.add_argument("--words", type=int, help="stop after this many words (default: never; --bench: 5,000,000)")
    p.add_argument("--order", type=int, default=1, help="words of context (default: 1; 2 and 3 read more like the book)")
    p.add_argument("--seed", type=int, help="random seed")
    p.add_argument("--interval", type=float, default=2.0, help="seconds between status lines (default: 2)")
    p.add_argument("--bench", action="store_true", help="train, babble a fixed amount, print JSON")
    p.add_argument("--plain", action="store_true", help="status lines even on a terminal")
    p.add_argument("--version", action="version", version=f"gilty {__version__}")
    args = p.parse_args(argv)
    if args.bench:
        args.words = args.words or 5_000_000
        run_bench(args)
    elif sys.stdout.isatty() and not args.plain:
        run_live(args)
    else:
        run_log(args)


if __name__ == "__main__":
    main()

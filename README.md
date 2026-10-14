# GILty

GILty shows how much faster a CPU- and memory-bound application that cannot
use more than one CPU gets when it runs on a different cloud instance type,
often for the same money or less. It is the kind of program that does not
scale out: more vCPUs do nothing for it, only a faster core and a faster
cache do. [Spare Cores](https://sparecores.com) uses it to demonstrate picking
instance types by measured single-core and cache performance (for example
with [sc-karpenter-nodepool](https://github.com/SpareCores/sc-karpenter-nodepool))
instead of by name.

What it does: it babbles in the style of *Moby-Dick*, as fast as one core
allows. It learns the novel as a word-level Markov chain (each word → every
word that followed it in the book), then walks the chain forever: look up the
current word, pick a follower at random, move on, repeat. On a terminal it
shows the babble scrolling by and the speed in words per second; elsewhere
(container logs) it prints one status line every two seconds.

```console
$ docker run --rm ghcr.io/sparecores/gilty --words 20000000 --seed 4
GILty 0.2.0 on Intel(R) Core(TM) i9-14900K, Python 3.13.16
learned Moby-Dick in 0.1 s: 212,796 words, 33,089 states
Core i9-14900K         5,250,727 words/s | When the Parsee; who didst hurl him be sure enough, 
babbled 20,000,000 words in 3.8 s: 5,300,398 words/s
```

Every status line starts with the machine (the instance type when GILty can
tell, and the CPU), so the logs of several copies on different machines can
be compared line by line. With `-it` (a terminal), GILty shows a live view instead of status lines.

## Results

On AWS, us-east-1, CPython 3.13, one core each, best of two runs:

| | r5a.large | c8a.large |
|---|---|---|
| CPU | AMD EPYC 7571 (Zen 1, 2018) | AMD EPYC 9R45 (Zen 5, 2025) |
| On-demand price | $0.113/h | $0.108/h |
| Geekbench 6 single-core | 712 | 2,702 |
| PassMark cached memory read | 14,393 MB/s | 33,953 MB/s |
| **GILty (default, order 1)** | 1.88 M words/s | 8.98 M words/s (**4.8×**) |
| GILty `--order 2` | 1.45 M words/s | 5.24 M words/s (3.6×) |
| GILty `--order 3` | 1.52 M words/s | 5.71 M words/s (3.8×) |
| Learning the book | | 3.1–3.5× faster |

A cheaper instance, almost five times the speed.

A fast core alone is not enough. An r8g.large (AWS Graviton 4, $0.118/h) is
2.55× faster than the r5a.large in Geekbench 6 single-core, yet GILty babbles
only 1.29× faster there (2.28 M words/s at order 1, 1.22–1.42× across orders;
learning the book, more ordinary interpreter work, is 2× faster). Following
pointers through megabytes depends on the cache more than on the core: the
single-threaded cached-read benchmark (PassMark: 1.47× for this pair)
predicts it better than Geekbench does. Two m5a.large instances (the
same EPYC 7571) in other zones landed within 15% of the r5a.large: AWS builds
the r5a and m5a families on that CPU only, which makes them a stable
baseline. Not every instance type is: an m5.large can land on a Skylake
(8175M) or a Cascade Lake (8259CL) host, and the same hash-table lookups ran
3× to 8× slower than on c8a depending on which.

## What makes it fast

Each step is a hash-table lookup whose result is the next lookup's key: the
followers of the current word, then that word's followers, and so on, jumping
around a model of a few megabytes (33,089 words, 212,796 followers). Two
things set the speed: how fast the core runs the interpreter loop (about 2.5×
between these two CPUs, by single-core benchmarks) and how fast it gets at
memory that is too large for the core's private caches but fits a modern
last-level cache (the rest). With `--order 2` or `3` the model grows to
135,000 and 197,000 states and the gap is smaller (3.6–3.8×): more of the
lookups reach main memory, which Zen 5 does not reach faster than older CPUs
do.

`bench/` has the experiments behind these numbers: interpreter-bound kernels
(about 2–2.5× between old and new CPUs), cache-sized hash tables (up to 8× on
the slowest host), how the gap moves with the working-set size, and the
thread-scaling measurements below.

## Why it is GILty

One chain can never be split: every word depends on the one before. More text
could be produced in parallel, one chain per thread, but in standard CPython
the GIL lets only one thread run Python code at a time, so threads only make
GILty slower. With the Python most services run, GILty is one core's worth of
work, and the only way to make it faster is a faster core.

Without the GIL it is a different story, depending on the version
(`bench/threads.py`, independent chains per thread, i9-14900K, order 1):

| Interpreter | 1 thread | 2 threads | 4 threads | 8 threads |
|---|---|---|---|---|
| CPython 3.13 (GIL) | 5.44 M words/s | 5.11 M | 4.46 M | 3.39 M |
| 3.13t, free-threaded, shared model | 2.86 M | 3.00 M | 2.98 M | 1.85 M |
| 3.13t, free-threaded, a model per thread | 3.40 M | 6.90 M | 13.0 M | 19.7 M |
| 3.14t (rc2), free-threaded, shared model | 4.13 M | 9.53 M | 16.9 M | 28.6 M |

3.13t does not scale on a shared model, as every lookup updates the reference
counts of objects all threads share; 3.14t scales almost linearly. A threaded
GILty on free-threaded 3.14 would use every core, at a lower speed per core.
Separate processes would work with any Python, at the cost of a copy of the
model each.

## Usage

```text
gilty                 babble forever (Ctrl-C stops and prints a summary)
gilty --words N       stop after N words
gilty --order K       words of context (default 1; 2 and 3 read more like the book)
gilty --seed S        reproducible babble
gilty --bench         learn, babble 5,000,000 words, print JSON
gilty --plain         status lines even on a terminal
gilty --interval S    seconds between status lines (default 2)
```

The container image is `ghcr.io/sparecores/gilty` (linux/amd64 and
linux/arm64). From a checkout, `pip install .` installs the `gilty` command;
it has no dependencies.

Every status line starts with the instance type, when GILty can tell, and
the CPU. It looks the instance type up in this order: `GILTY_INSTANCE_TYPE`;
in Kubernetes, the `node.kubernetes.io/instance-type` label of its node
(`NODE_NAME` from the downward API, read with the pod's service account);
the AWS instance metadata service. In Kubernetes that takes:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata: {name: gilty}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: gilty-node-reader}
rules:
  - {apiGroups: [""], resources: [nodes], verbs: [get]}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: gilty-node-reader}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: gilty-node-reader}
subjects: [{kind: ServiceAccount, name: gilty, namespace: default}]
```

and in the pod spec:

```yaml
serviceAccountName: gilty
containers:
  - name: gilty
    image: ghcr.io/sparecores/gilty:0.2.0
    env:
      - name: NODE_NAME
        valueFrom: {fieldRef: {fieldPath: spec.nodeName}}
```

Without them, GILty names the CPU only.

## The book

*Moby-Dick; or, The Whale* by Herman Melville (1851), from
[Project Gutenberg eBook #2701](https://www.gutenberg.org/ebooks/2701), with
the Project Gutenberg header and footer removed. The text is in the public
domain in the United States.

## License

MPL-2.0 (the code). The book is in the public domain.

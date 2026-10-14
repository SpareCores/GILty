from gilty.__main__ import main
from gilty.markov import Babbler, load_book, tokenize, train


def test_book():
    tokens = tokenize(load_book())
    assert tokens[:2] == ["MOBY-DICK;", "or,"]
    assert 200_000 < len(tokens) < 230_000


def test_every_babbled_triple_is_in_the_book():
    tokens = tokenize(load_book())
    for order in (1, 2, 3):
        model = train(tokens, order)
        b = Babbler(model, order, tokens, seed=1)
        words = b.babble(5_000, keep=5_000)
        assert len(words) > 4_000
        seen = set(zip(tokens, tokens[1:]))
        pairs = list(zip(words, words[1:]))
        # restarts at a sentence start break the chain; everything else is a
        # transition that occurs in the book
        assert sum(p in seen for p in pairs) > 0.99 * len(pairs)


def test_seed_is_deterministic():
    tokens = tokenize(load_book())
    model = train(tokens, 2)
    a = Babbler(model, 2, tokens, seed=7).babble(1_000, keep=1_000)
    b = Babbler(model, 2, tokens, seed=7).babble(1_000, keep=1_000)
    assert a == b


def test_bench_prints_json(capsys):
    main(["--bench", "--words", "20000", "--seed", "1"])
    out = capsys.readouterr().out
    assert '"words_per_second"' in out and '"states"' in out


def test_cpu_short():
    from gilty.__main__ import cpu_short

    assert cpu_short("AMD EPYC 7571") == "EPYC 7571"
    assert cpu_short("Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz") == "Xeon 8259CL"
    assert cpu_short("Intel(R) Core(TM) i9-14900K") == "Core i9-14900K"


def test_cpu_model_on_arm(tmp_path):
    from gilty.__main__ import cpu_model, cpu_short

    # /proc/cpuinfo of an AWS Graviton 4 (r8g): no "model name" line
    info = tmp_path / "cpuinfo"
    info.write_text(
        "processor\t: 0\nBogoMIPS\t: 2000.00\nFeatures\t: fp asimd evtstrm aes pmull sha1\n"
        "CPU implementer\t: 0x41\nCPU architecture: 8\nCPU variant\t: 0x0\nCPU part\t: 0xd4f\nCPU revision\t: 1\n\n"
    )
    assert cpu_model(str(info)) == "Neoverse-V2"
    assert cpu_short("Neoverse-V2") == "Neoverse-V2"
    info.write_text("processor\t: 0\nCPU implementer\t: 0x99\nCPU part\t: 0x123\n")
    assert cpu_model(str(info)) == "Arm core 0x99/0x123"
    info.write_text("processor\t: 0\nmodel name\t: AMD EPYC 9R45\n")
    assert cpu_model(str(info)) == "AMD EPYC 9R45"

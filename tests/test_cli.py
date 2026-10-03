from ekiwalk.cli import build_parser


def test_parser_build():
    a = build_parser().parse_args(["build", "--region", "tokyo", "--scenario", "base", "--scenario", "oedo-ext"])
    assert a.command == "build" and a.region == "tokyo" and a.scenario == ["base", "oedo-ext"]
    assert a.start == "network"


def test_parser_fetch():
    a = build_parser().parse_args(["fetch", "n02"])
    assert a.command == "fetch" and a.keys == ["n02"]

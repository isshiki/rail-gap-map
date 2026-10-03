"""Command line: uv run ekiwalk <fetch|build> ..."""

from __future__ import annotations

import argparse
import logging
import time

from . import admin, blanks, contours, export, network, places, shortest, stations, surface, water
from .config import ROOT, load_region, load_scenario
from .fetch import download, load_sources, raw_path

log = logging.getLogger("ekiwalk")

STEPS = ["network", "water", "admin", "stations", "solve", "surface", "blanks", "contours", "places", "export"]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ekiwalk")
    sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="確認後に生データを data/raw/ へ取得する")
    f.add_argument("keys", nargs="*")
    f.add_argument("--all", action="store_true")
    b = sub.add_parser("build", help="データを作って web/data/<region>/ に書き出す")
    b.add_argument("--region", required=True)
    b.add_argument("--scenario", action="append", default=None)
    b.add_argument("--from", dest="start", default="network", choices=STEPS)
    return ap


def cmd_fetch(args) -> None:
    srcs = load_sources(ROOT)
    keys = list(srcs) if args.all else args.keys
    for k in keys:
        print(f"  {k}: {srcs[k]['file']}  {srcs[k]['url']}  ({srcs[k]['size_hint']}, {srcs[k]['license']})")
    if input("これらを取得しますか? [y/N] ").strip().lower() != "y":
        print("取得しませんでした")
        return
    for k in keys:
        print(k, download(ROOT, k, srcs[k]))


def cmd_build(args) -> None:
    region = load_region(args.region)
    names = args.scenario or ["base"]
    if names[0] != "base":
        names = ["base"] + [n for n in names if n != "base"]
    scenarios = [load_scenario(n) for n in names]
    todo = STEPS[STEPS.index(args.start):]

    def step(name, fn):
        if name not in todo:
            return None
        t = time.time()
        r = fn()
        log.info("%s done in %.1fs", name, time.time() - t)
        return r

    pbf = raw_path(ROOT, region.osm_source)
    step("network", lambda: network.run(region, pbf))
    step("water", lambda: water.run(region, pbf))
    step("admin", lambda: admin.run(region, [raw_path(ROOT, f"n03-{c}") for c in region.n03_prefectures]))
    for s in scenarios:
        log.info("scenario %s", s.name)
        step("stations", lambda s=s: stations.run(region, s, raw_path(ROOT, "n02")))
        step("solve", lambda s=s: shortest.run(region, s))
        step("surface", lambda s=s: surface.run(region, s))
    town_csv, pos_csv = raw_path(ROOT, f"abr-town-{region.pref_code}"), raw_path(ROOT, f"abr-town-pos-{region.pref_code}")
    step("blanks", lambda: blanks.run(region, scenarios, town_csv, pos_csv, raw_path(ROOT, "s12")))
    for s in scenarios:
        step("contours", lambda s=s: contours.run(region, s))
    step("places", lambda: places.run(region, town_csv, pos_csv))
    step("export", lambda: export.run(region, scenarios, ROOT))


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    {"fetch": cmd_fetch, "build": cmd_build}[args.command](args)

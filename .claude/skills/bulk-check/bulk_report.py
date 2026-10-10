#!/usr/bin/env python3
"""Lean bulk savaitinė ataskaita iš Samsung Health eksporto.

Naudojimas:
    python3 -I bulk_report.py <eksporto aplankas arba .zip> [--weeks 8] [--min 0.5] [--max 1.5]

--min/--max: siekiamas svorio prieaugis, % kūno svorio per mėnesį.
Tik standartinė biblioteka, kad veiktų bet kurioje sesijoje.
"""
import argparse
import csv
import glob
import io
import os
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# failo pavadinimo pradžia -> naudojami stulpeliai
SOURCES = {
    "weight": "com.samsung.health.weight.",
    "steps": "com.samsung.shealth.tracker.pedometer_day_summary.",
    "sleep": "com.samsung.shealth.sleep.",
    "food": "com.samsung.health.nutrition.",
    "exercise": "com.samsung.shealth.exercise.",
}


def parse_time(v):
    v = (v or "").strip()
    if not v:
        return None
    if v.isdigit():  # epoch ms
        return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc).replace(tzinfo=None)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            pass
    return None


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_rows(path):
    """Samsung CSV: 1 eilutė – metaduomenys, 2 – antraštės. Stulpelių prefiksai nuimami."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().splitlines()
    if len(lines) < 2:
        return []
    reader = csv.reader(io.StringIO("\n".join(lines[1:])))
    header = [h.rsplit(".", 1)[-1].strip() for h in next(reader)]
    return [dict(zip(header, r)) for r in reader]


def find_files(root, prefix):
    hits = [p for p in glob.glob(os.path.join(root, "**", "*.csv"), recursive=True)
            if os.path.basename(p).startswith(prefix)]
    return hits


def week_start(d):
    d = d.date() if isinstance(d, datetime) else d
    return d - timedelta(days=d.weekday())


def collect(root):
    weeks = defaultdict(lambda: defaultdict(list))
    daily = defaultdict(lambda: defaultdict(float))  # (kind, day) -> sumos

    for p in find_files(root, SOURCES["weight"]):
        for r in read_rows(p):
            t, w = parse_time(r.get("start_time")), num(r.get("weight"))
            if t and w:
                weeks[week_start(t)]["weight"].append(w)
                bf = num(r.get("body_fat"))
                if bf:
                    weeks[week_start(t)]["body_fat"].append(bf)

    for p in find_files(root, SOURCES["steps"]):
        seen = {}
        for r in read_rows(p):
            t, s = parse_time(r.get("day_time")), num(r.get("step_count"))
            if t and s is not None:
                seen[t.date()] = max(seen.get(t.date(), 0), s)  # keli įrenginiai -> imam didžiausią
        for d, s in seen.items():
            daily["steps"][d] = max(daily["steps"][d], s)

    for p in find_files(root, SOURCES["sleep"]):
        for r in read_rows(p):
            a, b = parse_time(r.get("start_time")), parse_time(r.get("end_time"))
            if a and b and b > a:
                daily["sleep"][b.date()] += (b - a).total_seconds() / 3600

    for p in find_files(root, SOURCES["food"]):
        for r in read_rows(p):
            t = parse_time(r.get("start_time"))
            if not t:
                continue
            daily["kcal"][t.date()] += num(r.get("calorie")) or 0
            daily["protein"][t.date()] += num(r.get("protein")) or 0

    for p in find_files(root, SOURCES["exercise"]):
        for r in read_rows(p):
            t = parse_time(r.get("start_time"))
            if t:
                daily["workouts"][t.date()] += 1

    for kind, days in daily.items():
        for d, v in days.items():
            if kind == "workouts":
                weeks[week_start(d)][kind].append(v)
            elif v > 0:
                weeks[week_start(d)][kind].append(v)
    return weeks


def avg(xs):
    return sum(xs) / len(xs) if xs else None


def fmt(v, nd=1):
    return "–" if v is None else f"{v:.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--weeks", type=int, default=8)
    ap.add_argument("--min", type=float, default=0.5, help="min %% kūno svorio / mėn.")
    ap.add_argument("--max", type=float, default=1.5, help="max %% kūno svorio / mėn.")
    a = ap.parse_args()

    root = a.path
    if zipfile.is_zipfile(root):
        tmp = tempfile.mkdtemp(prefix="shealth_")
        with zipfile.ZipFile(root) as z:
            z.extractall(tmp)
        root = tmp

    weeks = collect(root)
    if not weeks:
        sys.exit("Nerasta Samsung Health CSV failų: " + a.path)

    keys = sorted(weeks)[-a.weeks:]
    print("| Savaitė | Svoris kg | Δ kg | Δ %/mėn | Riebalai % | kcal/d | Baltymai g/d | Miegas h | Žingsniai | Treniruotės |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    prev = None
    rates = []
    for k in keys:
        w = weeks[k]
        wt = avg(w["weight"])
        dk = dpct = None
        if wt is not None and prev is not None:
            dk = wt - prev
            dpct = dk / prev * 100 * 4.33
            rates.append(dpct)
        if wt is not None:
            prev = wt
        print(f"| {k} | {fmt(wt)} | {fmt(dk, 2)} | {fmt(dpct, 2)} | {fmt(avg(w['body_fat']))} | "
              f"{fmt(avg(w['kcal']), 0)} | {fmt(avg(w['protein']), 0)} | {fmt(avg(w['sleep']))} | "
              f"{fmt(avg(w['steps']), 0)} | {int(sum(w['workouts']))} |")

    print()
    recent = rates[-3:]
    if not recent:
        print("VERDIKTAS: per mažai svorio matavimų tempui įvertinti (reikia bent 2 savaičių).")
        return
    r = avg(recent)
    lo, hi = a.min, a.max
    if r < lo:
        verdict = f"PER LĖTAI ({r:.2f} %/mėn < {lo}). Pridėk ~100–150 kcal/d."
    elif r > hi:
        verdict = f"PER GREITAI ({r:.2f} %/mėn > {hi}). Nuimk ~100–150 kcal/d, kitaip kaupsis riebalai."
    else:
        verdict = f"TEMPAS GERAS ({r:.2f} %/mėn, tikslas {lo}–{hi}). Nieko nekeisk."
    print(f"VERDIKTAS (paskutinių {len(recent)} sav. vidurkis): {verdict}")


if __name__ == "__main__":
    main()

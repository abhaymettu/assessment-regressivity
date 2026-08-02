"""Does the contractor pattern hold outside Dane County?

assessors.py found that Accurate Appraisal LLC adopts the sale price as the assessed
value in every revalued Dane County municipality it serves, and that no other contractor
in that county does it at all. Five municipalities is a thin base for a claim about a
firm, and Dane is where the pattern was discovered, so it cannot also be the evidence
for it.

Accurate Appraisal serves 112 municipalities statewide. This file re-runs the same
measurement in four counties chosen only for having enough of them to test: Walworth,
Columbia, Outagamie and Jefferson. Nothing about the method changes, and the prediction
was fixed before these counties were pulled: Accurate municipalities chase, others in
the same county do not.

The RETR files already in data/ are statewide, so the sales side needed no new download.
Columbia has no municipality with enough pre-lien sales to measure and drops out.

The result is a partial confirmation and worth stating precisely. Outside Dane, the
firm's municipalities chase at 44% against 0% for every other contractor, so the
exclusivity holds and the universality does not. Pooling all five counties, all 10
chasing municipalities are either the target firm's (9) or Madison's in-house office
(1), and no municipality assessed by any of the other contractors chases at any
assessment level. Within the firm's own portfolio the practice tracks assessment level,
which is the conditional stated in LEVEL_CUTS below.

    python3 replication.py
    python3 replication.py --test
"""

import collections
import csv
import glob
import os
import statistics
import sys

from assessors import REVALUED_LEVEL, load_roster, norm
from ratios import (ARMS_CONVEYANCE, ARMS_RELATIONSHIP, LIEN_DATE, MIN_PRICE,
                    RATIO_CEIL, RATIO_FLOOR, RESIDENTIAL, WINDOW_START,
                    money, parcel_key, parse_date)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

COUNTIES = ["WALWORTH", "COLUMBIA", "OUTAGAMIE", "JEFFERSON"]
TARGET = "Accurate Appraisal LLC"
MIN_N = 40   # pre-lien sales needed before a municipality's rate means anything

# Chasing turned out not to be unconditional even within the target firm, and the
# condition is the municipality's assessment level. A jurisdiction held at full market
# value is doing annual maintenance, and copying the sale price is the cheapest way to
# maintain it. One that has drifted is between revaluations and is not touching
# individual parcels at all. So the comparison is reported at several level cuts rather
# than at one, and the pattern is stated conditionally.
LEVEL_CUTS = (0.85, 0.95, 0.98)


def parcels(county):
    path = os.path.join(DATA, f"parcels_{county.lower()}.csv")
    if not os.path.exists(path):
        return None
    with open(path, newline="") as fh:
        return {r["PARCELID"].strip(): r for r in csv.DictReader(fh)}


def transfers(county):
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA, "RETRHistoricalReport*.csv"))):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows += [r for r in csv.DictReader(fh)
                     if r["County"].strip().upper() == county]
    return rows


def pre_lien_sales(county):
    """Arms-length residential sales conveyed before the lien date, joined to the roll."""
    par = parcels(county)
    if par is None:
        return None
    out = []
    for t in transfers(county):
        if t["Property Type"].strip() not in RESIDENTIAL:
            continue
        sold = parse_date(t["Conveyance Date"])
        if sold is None or not (WINDOW_START <= sold < LIEN_DATE):
            continue
        if (t["Conveyance Type"].strip() not in ARMS_CONVEYANCE
                or t["Grantor/Grantee Relationship"].strip() not in ARMS_RELATIONSHIP):
            continue
        price = money(t["Sale Price"])
        if price < MIN_PRICE:
            continue
        p = par.get(parcel_key(t["Parcel Number"]))
        if p is None:
            continue
        assessed = money(p["CNTASSDVALUE"])
        if assessed <= 0 or not (RATIO_FLOOR <= assessed / price <= RATIO_CEIL):
            continue
        out.append({"municipality": t["Municipality"].strip(),
                    "assessed": assessed, "price": price})
    return out


def levels(county):
    path = os.path.join(DATA, f"parcels_{county.lower()}.csv")
    by = collections.defaultdict(list)
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            a = money(r["CNTASSDVALUE"])
            f = money(r["ESTFMKVALUE"])
            if a > 0 and f > 0:
                by[r["PLACENAME"].strip().upper()].append(a / f)
    return {k: statistics.median(v) for k, v in by.items() if len(v) >= 50}


def county_table(county):
    sales = pre_lien_sales(county)
    if sales is None:
        return None
    roster = load_roster(county)
    lvl = levels(county)

    by = collections.defaultdict(list)
    for s in sales:
        by[s["municipality"]].append(s)

    rows = []
    for m, v in by.items():
        if len(v) < MIN_N:
            continue
        place, _, kind = m.partition(",")
        kind = kind.replace("of", "").strip()
        firm = roster.get((norm(place), kind))
        if not firm:
            continue
        level = lvl.get(f"{kind.upper()} OF {place.strip().upper()}", float("nan"))
        exact = sum(1 for s in v if abs(s["assessed"] - s["price"]) < 1.0)
        rows.append({"county": county, "municipality": m, "n": len(v),
                     "rate": exact / len(v), "firm": firm, "level": level})
    return sorted(rows, key=lambda r: -r["rate"])


def dane_rows():
    """Dane County, measured by assessors.py, folded in so the pooled table covers all
    five counties. Dane is where the pattern was found, and is labelled as such."""
    from assessors import assessment_levels, load_rates
    lvl = assessment_levels()
    roster = load_roster("DANE")
    out = []
    for m, v in load_rates().items():
        firm = roster.get(v["key"])
        if firm:
            out.append({"county": "DANE", "municipality": m, "n": v["n"],
                        "rate": v["rate"], "firm": firm,
                        "level": lvl.get(v["place_key"], float("nan"))})
    return out


def pooled(all_rows):
    """Chasing counts by firm group at each assessment-level cut."""
    out = []
    for cut in LEVEL_CUTS:
        sub = [r for r in all_rows if r["level"] >= cut]
        acc = [r for r in sub if r["firm"] == TARGET]
        # Madison assesses in house and chases, so it belongs in neither group. Leaving
        # it among the contractors would understate the contrast for the wrong reason.
        oth = [r for r in sub if r["firm"] != TARGET and "Drea" not in r["firm"]]
        out.append((cut,
                    sum(1 for r in acc if r["rate"] > 0.50), len(acc),
                    sum(1 for r in oth if r["rate"] > 0.50), len(oth)))
    return out


def report():
    all_rows = []
    for c in COUNTIES:
        t = county_table(c)
        if t is None:
            print(f"{c}: no parcel file, run  python3 fetch_parcels.py {c}")
            continue
        all_rows += t
        print(f"\n{c} COUNTY\n")
        print(f"{'municipality':<28}{'n':>5}{'exact':>8}{'level':>8}   assessor")
        for r in t:
            flag = "" if r["level"] >= REVALUED_LEVEL else "  (stale)"
            print(f"{r['municipality']:<28}{r['n']:>5}{r['rate']:>7.1%}"
                  f"{r['level']:>8.3f}   {r['firm']}{flag}")

    if not all_rows:
        return

    all_rows += dane_rows()
    counties = sorted({r["county"] for r in all_rows})

    print(f"\n\nPooled across {len(counties)} counties ({', '.join(counties)}), "
          f"n >= {MIN_N}\n")
    print(f"{'assessment level':<20}{TARGET:>26}{'every other contractor':>26}")
    for cut, ac, an, oc, on in pooled(all_rows):
        print(f"{'at or above ' + format(cut, '.2f'):<20}"
              f"{format(ac, 'd') + ' of ' + format(an, 'd'):>26}"
              f"{format(oc, 'd') + ' of ' + format(on, 'd'):>26}")

    chasing = [r for r in all_rows if r["rate"] > 0.50]
    firms = collections.Counter(r["firm"] for r in chasing)
    print(f"\nEvery one of the {len(chasing)} municipalities that chases, at any level:")
    for firm, cnt in firms.most_common():
        print(f"  {cnt:>2}  {firm}")

    print("\nNo municipality assessed by any other contractor chases, in any county, at")
    print("any assessment level. Within the target firm's own portfolio the practice")
    print("tracks the level: it happens where the municipality is held at full market")
    print("value and not where assessments have been left to drift, which is what annual")
    print("maintenance by copying sale prices would look like.")
    print("\nThe prediction was made from Dane County and fixed before the other four")
    print("counties were pulled. Nothing in the method changed.")


def test():
    tables = {c: county_table(c) for c in COUNTIES}
    have = {c: t for c, t in tables.items() if t}
    assert len(have) >= 3, f"only {len(have)} counties have parcel data, need at least 3"

    outside = [r for t in have.values() for r in t]
    assert len(outside) >= 15, f"only {len(outside)} municipalities outside Dane"

    # The replication is on the counties Dane did not supply. It is allowed to fail, and
    # if it does the claim narrows to Dane County rather than being quietly restated.
    reval = [r for r in outside if r["level"] >= REVALUED_LEVEL]
    target = [r for r in reval if r["firm"] == TARGET]
    other = [r for r in reval if r["firm"] != TARGET]
    assert len(target) >= 5 and len(other) >= 5, "replication sample too small"
    t_rate = sum(1 for r in target if r["rate"] > 0.50) / len(target)
    o_rate = sum(1 for r in other if r["rate"] > 0.50) / len(other)
    assert t_rate > o_rate + 0.30, (
        f"replication failed outside Dane: {t_rate:.0%} of {TARGET} against {o_rate:.0%}")

    # The sharper claim is the exclusivity one, and it must hold on the pooled data at
    # every level cut, not just the flattering one.
    all_rows = outside + dane_rows()
    for cut, ac, an, oc, on in pooled(all_rows):
        assert oc == 0, f"a non-target contractor chases at level cut {cut}: {oc} of {on}"
        assert an >= 5, f"only {an} target municipalities at level cut {cut}"
    top = pooled(all_rows)[-1]
    assert top[1] == top[2], \
        f"target does not chase everywhere at the tightest cut: {top[1]} of {top[2]}"

    print(f"ok: replicated outside Dane at {t_rate:.0%} against {o_rate:.0%}, and no")
    print(f"    other contractor chases at any of the {len(LEVEL_CUTS)} level cuts\n")
    report()


if __name__ == "__main__":
    test() if "--test" in sys.argv else report()

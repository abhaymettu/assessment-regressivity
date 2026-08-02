"""Split the county finding by municipality, because that is where the decision sits.

Wisconsin assesses at the municipal level. Dane County contains 60 assessing
jurisdictions, each with its own assessor, and a county-wide average hides whichever of
them is responsible for what.

This file exists mainly to test an alternative explanation for the chasing result. If
the assessed values in the state parcel layer were being refreshed from sale prices by
some county or state process rather than by assessors, every municipality would chase at
roughly the same rate, and the finding would be about a data pipeline rather than about
assessment practice. Sixty independent offices choosing the same shortcut to within a
few points would be a remarkable coincidence; a pipeline doing it would not.

So the question is the spread, not the average.

    python3 municipalities.py
    python3 municipalities.py --test
"""

import collections
import csv
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RATIOS = os.path.join(HERE, "data", "ratios.csv")

MIN_CHASE_N = 50    # pre-lien sales needed before a chasing rate means anything
MIN_STUDY_N = 100   # chase-free sales needed before a slope means anything


def load():
    with open(RATIOS, newline="") as fh:
        return list(csv.DictReader(fh))


def is_exact(r):
    return abs(float(r["assessed"]) - float(r["sale_price"])) < 1.0


def slope(rows):
    """Log assessment ratio per doubling of price. Negative is regressive."""
    xs = [math.log(float(r["price_adj"]), 2) for r in rows]
    ys = [math.log(float(r["ratio_adj"])) for r in rows]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def cod(rows):
    r = [float(x["ratio_adj"]) for x in rows]
    md = statistics.median(r)
    return 100.0 * sum(abs(x - md) for x in r) / len(r) / md


def group(rows, key):
    out = collections.defaultdict(list)
    for r in rows:
        out[r["municipality"]].append(r)
    return out


def chase_table(rows):
    pre = group([r for r in rows if r["post_lien"] == "0"], "municipality")
    out = []
    for m, v in pre.items():
        if len(v) < MIN_CHASE_N:
            continue
        out.append((m, len(v), sum(1 for r in v if is_exact(r)) / len(v),
                    statistics.median(float(r["ratio"]) for r in v)))
    return sorted(out, key=lambda x: -x[2])


def study_table(rows):
    st = group([r for r in rows if r["study"] == "1"], "municipality")
    out = []
    for m, v in st.items():
        if len(v) < MIN_STUDY_N:
            continue
        out.append((m, len(v), statistics.median(float(r["ratio_adj"]) for r in v),
                    cod(v), slope(v)))
    return sorted(out, key=lambda x: x[4])


def report(rows):
    ch = chase_table(rows)
    print(f"Sales chasing by municipality, pre-lien sales, n >= {MIN_CHASE_N}\n")
    print(f"{'municipality':<30}{'n':>6}{'exact':>9}{'median ratio':>15}")
    for m, n, rate, md in ch:
        print(f"{m:<30}{n:>6}{rate:>8.1%}{md:>15.4f}")

    rates = [r for _, _, r, _ in ch]
    print(f"\n{len(ch)} municipalities. Chasing rate ranges {min(rates):.1%} to "
          f"{max(rates):.1%},")
    print(f"median {statistics.median(rates):.1%}, spread {max(rates) - min(rates):.1%}.")

    perfect = [m for m, _, _, md in ch if abs(md - 1.0) < 1e-9]
    print(f"{len(perfect)} of {len(ch)} have a pre-lien median ratio of exactly 1.0000.")

    # The shape matters more than the spread. A gradient would suggest one practice
    # applied with varying diligence. A gap suggests a decision each office either takes
    # or does not.
    hi = [r for r in rates if r > 0.50]
    lo = [r for r in rates if r < 0.05]
    gap = min(hi) - max(lo) if hi and lo else 0.0

    if max(rates) - min(rates) > 0.20:
        print("\nThe spread is wide, so this is not one process applied uniformly to the")
        print("county. Municipalities differ by more than twenty points in how often they")
        print("adopt the sale price outright, which is what independent assessing offices")
        print("making their own choices looks like.")
    if hi and lo and len(hi) + len(lo) == len(rates):
        print(f"\nIt is not a gradient either. {len(hi)} municipalities sit at "
              f"{min(hi):.0%} or above and")
        print(f"{len(lo)} sit at {max(lo):.1%} or below, with nothing in the "
              f"{gap:.0%} points between.")
        print("Chasing is a practice an assessing office either uses or does not.")
    else:
        print("\nThe spread is narrow. That is what a shared data pipeline would produce,")
        print("and it would mean the finding is about how the parcel layer is populated")
        print("rather than about assessment practice.")

    st = study_table(rows)
    print(f"\n\nRegressivity by municipality, chase-free sales, n >= {MIN_STUDY_N}")
    print("Slope is log assessment ratio per doubling of price. Negative is regressive.\n")
    print(f"{'municipality':<30}{'n':>6}{'median':>9}{'COD':>8}{'slope':>9}")
    for m, n, md, c, s in st:
        print(f"{m:<30}{n:>6}{md:>9.3f}{c:>8.1f}{s:>9.3f}")

    slopes = [s for _, _, _, _, s in st]
    print(f"\nEvery one of {len(st)} municipalities has a negative slope."
          if all(s < 0 for s in slopes) else
          f"\n{sum(1 for s in slopes if s < 0)} of {len(st)} have a negative slope.")
    print(f"Range {min(slopes):.3f} to {max(slopes):.3f}, median "
          f"{statistics.median(slopes):.3f}.")

    # If chasing and regressivity moved together, chasing would be a candidate cause of
    # the measured regressivity rather than a separate problem. Worth knowing either way.
    chase_by = {m: r for m, _, r, _ in ch}
    paired = [(chase_by[m], s) for m, _, _, _, s in st if m in chase_by]
    if len(paired) >= 6:
        xs = [p[0] for p in paired]
        ys = [p[1] for p in paired]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
        r = num / den if den else 0.0
        print(f"\nCorrelation between chasing rate and regressivity slope across the "
              f"{len(paired)}")
        print(f"municipalities measurable on both: r = {r:+.2f}.")
        if abs(r) < 0.4:
            print("Weak. The two problems are close to independent, so correcting the")
            print("chasing would not by itself fix the regressivity.")


def test():
    rows = load()
    ch = chase_table(rows)
    assert len(ch) >= 8, f"only {len(ch)} municipalities clear n >= {MIN_CHASE_N}"

    rates = [r for _, _, r, _ in ch]
    # The county-level claim in chasing.py is only about assessment practice if the
    # municipalities actually differ. A narrow spread would mean a shared pipeline and
    # would force that claim to be rewritten, so it is asserted here rather than assumed.
    assert max(rates) - min(rates) > 0.20, \
        f"chasing rates span only {max(rates) - min(rates):.1%}, consistent with one shared process"

    st = study_table(rows)
    assert len(st) >= 8, f"only {len(st)} municipalities clear n >= {MIN_STUDY_N}"

    # The county-wide regressivity finding should not rest on Madison alone, since
    # Madison is 42% of the sample. If the smaller municipalities went the other way the
    # county number would be an artifact of aggregation.
    non_madison = [s for m, _, _, _, s in st if "Madison" not in m]
    assert sum(1 for s in non_madison if s < 0) > len(non_madison) * 0.7, \
        "regressivity does not hold outside Madison, so the county figure is an aggregation artifact"

    print(f"ok: {len(ch)} municipalities measurable for chasing, spread "
          f"{max(rates) - min(rates):.1%},")
    print(f"    and regressivity holds in {sum(1 for s in non_madison if s < 0)} of "
          f"{len(non_madison)} municipalities outside Madison\n")
    report(rows)


if __name__ == "__main__":
    test() if "--test" in sys.argv else report(load())

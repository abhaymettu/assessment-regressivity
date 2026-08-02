"""IAAO ratio-study statistics for the joined Dane County sales.

Three statistics, because they fail in different ways and a jurisdiction can pass one
while failing another:

  COD  dispersion. How inconsistent assessments are, ignoring direction.
  PRD  the mean ratio over the value-weighted mean ratio. Above 1.03 means low-value
       property carries a higher assessment ratio than high-value property.
  PRB  the change in assessment ratio per doubling of value, as a coefficient. Unlike
       PRD it does not depend on how the sample is spread across the price range,
       which is why IAAO added it.

The point of the project is that the state certifies on an aggregate ratio, and an
aggregate ratio is the one statistic here that cannot detect regressivity at all. That
comparison is printed alongside.

Confidence intervals are bootstrapped rather than taken from a normal approximation.
COD and PRD are ratios of sample statistics with no clean closed-form standard error,
and a normal interval on them is narrower than the truth.

    python3 iaao.py
    python3 iaao.py --test
"""

import csv
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RATIOS = os.path.join(HERE, "data", "ratios.csv")

BOOTSTRAP = 2000
SEED = 20260802

# IAAO Standard on Ratio Studies, single-family residential.
IAAO = {
    "median": (0.90, 1.10),
    "cod": (5.0, 15.0),
    "prd": (0.98, 1.03),
    "prb": (-0.05, 0.05),
}


def load():
    with open(RATIOS, newline="") as fh:
        return [{"ratio": float(r["ratio"]),
                 "price": float(r["sale_price"]),
                 "assessed": float(r["assessed"]),
                 "municipality": r["municipality"]} for r in csv.DictReader(fh)]


def median_ratio(rows):
    return statistics.median(r["ratio"] for r in rows)


def cod(rows):
    """Coefficient of dispersion: average absolute deviation from the median, as a %."""
    md = median_ratio(rows)
    dev = sum(abs(r["ratio"] - md) for r in rows) / len(rows)
    return 100.0 * dev / md


def prd(rows):
    """Price-related differential. Above 1.03 is the classic regressivity flag."""
    mean_ratio = sum(r["ratio"] for r in rows) / len(rows)
    weighted = sum(r["assessed"] for r in rows) / sum(r["price"] for r in rows)
    return mean_ratio / weighted


def prb(rows):
    """Price-related bias: OLS slope of proportional ratio deviation on log2 value.

    Reads directly as the fractional change in assessment ratio per doubling of value,
    so PRB = -0.04 means a home worth twice as much is assessed at 4% less of its
    value.
    """
    md = median_ratio(rows)
    xs, ys = [], []
    for r in rows:
        value = (r["assessed"] / md + r["price"]) / 2.0
        if value <= 0:
            continue
        xs.append(math.log(value) / math.log(2))
        ys.append((r["ratio"] - md) / md)
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / sxx


def boot_ci(rows, fn, reps=BOOTSTRAP, alpha=0.05):
    rng = random.Random(SEED)
    n = len(rows)
    vals = []
    for _ in range(reps):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        try:
            vals.append(fn(sample))
        except (ZeroDivisionError, statistics.StatisticsError):
            continue
    vals.sort()
    lo = vals[int(alpha / 2 * len(vals))]
    hi = vals[int((1 - alpha / 2) * len(vals)) - 1]
    return lo, hi


def verdict(name, value, lo, hi):
    low, high = IAAO[name]
    inside = low <= value <= high
    # A point estimate inside the standard means little if the interval straddles the
    # boundary, so the interval decides the wording.
    if inside and lo >= low and hi <= high:
        return "passes"
    if not inside and (lo > high or hi < low):
        return "FAILS"
    return "inconclusive"


def decile_table(rows):
    rows = sorted(rows, key=lambda r: r["price"])
    n = len(rows)
    out = []
    for d in range(10):
        chunk = rows[d * n // 10:(d + 1) * n // 10]
        if not chunk:
            continue
        out.append((d + 1,
                    len(chunk),
                    min(r["price"] for r in chunk),
                    max(r["price"] for r in chunk),
                    median_ratio(chunk)))
    return out


def report(rows):
    n = len(rows)
    print(f"Dane County, {n} arms-length residential sales joined to the 2025 roll\n")

    stats = [("median", median_ratio), ("cod", cod), ("prd", prd), ("prb", prb)]
    results = {}
    print(f"{'statistic':<10}{'estimate':>10}{'95% CI':>22}{'IAAO range':>16}   verdict")
    for name, fn in stats:
        val = fn(rows)
        lo, hi = boot_ci(rows, fn)
        results[name] = (val, lo, hi)
        rng = f"[{lo:.3f}, {hi:.3f}]"
        std = f"{IAAO[name][0]:.2f} to {IAAO[name][1]:.2f}"
        print(f"{name:<10}{val:>10.3f}{rng:>22}{std:>16}   {verdict(name, val, lo, hi)}")

    print("\nMedian assessment ratio by sale-price decile")
    print(f"{'decile':<8}{'n':>6}{'price range':>26}{'median ratio':>14}")
    tbl = decile_table(rows)
    for d, cnt, lo_p, hi_p, md in tbl:
        span = f"${lo_p:,.0f} to ${hi_p:,.0f}"
        print(f"{d:<8}{cnt:>6}{span:>26}{md:>14.3f}")

    if len(tbl) >= 10:
        bottom, top = tbl[0][4], tbl[-1][4]
        gap = (bottom - top) / top * 100
        print(f"\nBottom decile is assessed at {bottom:.3f} of sale price, "
              f"top decile at {top:.3f}.")
        print(f"The cheapest tenth carries an assessment ratio {gap:.1f}% higher "
              f"than the priciest tenth.")

    agg = sum(r["assessed"] for r in rows) / sum(r["price"] for r in rows)
    print(f"\nAggregate ratio, the statistic the state certifies on: {agg:.3f}")
    print("That number is a single figure for the whole jurisdiction. It is the same")
    print("whether the burden is spread evenly or concentrated on the cheapest homes.")
    return results


def test():
    rows = load()
    assert len(rows) > 100, f"only {len(rows)} rows, run ratios.py first"

    # A perfectly proportional roll must score as clean on every statistic, or the
    # implementations are wrong in a way the real data would hide.
    flat = [{"ratio": 1.0, "price": p, "assessed": p, "municipality": "X"}
            for p in range(100_000, 900_000, 1000)]
    assert abs(cod(flat)) < 1e-9, f"COD on a perfect roll should be 0, got {cod(flat)}"
    assert abs(prd(flat) - 1.0) < 1e-9, f"PRD on a perfect roll should be 1, got {prd(flat)}"
    assert abs(prb(flat)) < 1e-9, f"PRB on a perfect roll should be 0, got {prb(flat)}"

    # Now a roll built to be regressive: ratio falls as price rises. PRD must exceed 1
    # and PRB must come out negative, otherwise the sign convention is backwards and
    # every conclusion drawn from it would be inverted.
    reg = []
    for p in range(100_000, 900_000, 1000):
        ratio = 1.20 - 0.30 * (p - 100_000) / 800_000
        reg.append({"ratio": ratio, "price": p, "assessed": ratio * p, "municipality": "X"})
    assert prd(reg) > 1.03, f"PRD failed to flag a regressive roll: {prd(reg):.4f}"
    assert prb(reg) < -0.05, f"PRB failed to flag a regressive roll: {prb(reg):.4f}"

    # And progressive data must flip both signs.
    prog = [{"ratio": 2.0 - r["ratio"], "price": r["price"],
             "assessed": (2.0 - r["ratio"]) * r["price"], "municipality": "X"} for r in reg]
    assert prd(prog) < 1.0, f"PRD should drop below 1 on progressive data: {prd(prog):.4f}"
    assert prb(prog) > 0, f"PRB should be positive on progressive data: {prb(prog):.4f}"

    print("ok: statistics are 0/1/0 on a proportional roll and correctly signed on both")
    print("    a regressive and a progressive one\n")
    report(rows)


if __name__ == "__main__":
    test() if "--test" in sys.argv else report(load())

"""Sales chasing: the assessor copied 2024 sale prices onto the 2025 roll.

A ratio study assumes assessed values were set independently of the sales used to
judge them. When an assessor instead adopts a recent sale price as the new assessed
value, the sold parcels come out perfect and their unsold neighbours do not, and the
jurisdiction scores itself using exactly the parcels it just corrected.

The test here needs no model. Assessed values are set as of the 1 January 2025 lien
date, so sales conveyed after that date could not have informed the roll. They are a
control group the calendar provides for free. If assessments were set independently,
the share of sales assessed at exactly their sale price should look the same either
side of the date.

    python3 chasing.py
    python3 chasing.py --test
"""

import collections
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RATIOS = os.path.join(HERE, "data", "ratios.csv")

EXACT_DOLLARS = 1.0   # assessed within a dollar of the sale price


def load():
    with open(RATIOS, newline="") as fh:
        return list(csv.DictReader(fh))


def is_exact(r):
    return abs(float(r["assessed"]) - float(r["sale_price"])) < EXACT_DOLLARS


def by_month(rows):
    m = collections.defaultdict(list)
    for r in rows:
        m[r["conveyance_date"][:7]].append(r)
    return m


def report(rows):
    months = by_month(rows)
    print("Share of arms-length residential sales assessed at exactly the sale price,")
    print("by month of conveyance. The 2025 roll has a lien date of 1 January 2025.\n")
    print(f"{'month':<10}{'n':>6}{'exact':>9}{'median ratio':>15}")
    for k in sorted(months):
        v = months[k]
        exact = sum(1 for r in v if is_exact(r)) / len(v)
        med = statistics.median(float(r["ratio"]) for r in v)
        mark = "  <- lien date" if k == "2025-01" else ""
        print(f"{k:<10}{len(v):>6}{exact:>8.1%}{med:>15.4f}{mark}")

    pre = [r for r in rows if r["post_lien"] == "0"]
    post = [r for r in rows if r["post_lien"] == "1"]
    pre_rate = sum(1 for r in pre if is_exact(r)) / len(pre)
    post_rate = sum(1 for r in post if is_exact(r)) / len(post)

    print(f"\nBefore the lien date: {sum(1 for r in pre if is_exact(r))} of {len(pre)} "
          f"sales assessed to the dollar ({pre_rate:.1%})")
    print(f"After:                {sum(1 for r in post if is_exact(r))} of {len(post)} "
          f"({post_rate:.1%})")
    print(f"Ratio of the two rates: {pre_rate / post_rate:.0f} to 1")

    pre_med = statistics.median(float(r["ratio"]) for r in pre)
    print(f"\nMedian ratio on pre-lien sales is {pre_med:.4f}. Every single month of 2024")
    print("returns a median of exactly 1.0000, which is not a thing markets do.")

    print("\nWhy it matters beyond this study. The sold parcels were corrected to market")
    print("and their unsold neighbours were not, so identical houses now carry different")
    print("assessments according to whether one of them happened to change hands. That is")
    print("horizontal inequity created by the correction itself. It also means any ratio")
    print("study drawing on 2024 sales scores the assessor against the parcels the")
    print("assessor had already copied, and returns a cleaner verdict than the roll")
    print("deserves.")


def test():
    rows = load()
    pre = [r for r in rows if r["post_lien"] == "0"]
    post = [r for r in rows if r["post_lien"] == "1"]
    assert len(pre) > 1000 and len(post) > 1000, "need both sides of the lien date"

    pre_rate = sum(1 for r in pre if is_exact(r)) / len(pre)
    post_rate = sum(1 for r in post if is_exact(r)) / len(post)

    # The whole claim rests on this gap. If it ever narrows, the finding is gone and
    # the study window in ratios.py should be widened back out.
    assert pre_rate > 0.25, f"pre-lien exact-match rate collapsed to {pre_rate:.1%}"
    assert post_rate < 0.05, f"post-lien exact-match rate rose to {post_rate:.1%}"
    assert pre_rate / post_rate > 10, f"gap narrowed to {pre_rate / post_rate:.1f}x"

    # An exact dollar match is not something rounding produces. If a meaningful number
    # of post-lien sales matched too, the test would be picking up a coincidence of
    # round numbers rather than the assessor's clerical behaviour.
    months = by_month(rows)
    pre_months = [k for k in months if k < "2025-01"]
    assert all(abs(statistics.median(float(r["ratio"]) for r in months[k]) - 1.0) < 1e-9
               for k in pre_months), "not every pre-lien month has a median of exactly 1"

    print(f"ok: {pre_rate:.1%} exact before the lien date, {post_rate:.1%} after, and")
    print(f"    all {len(pre_months)} pre-lien months have a median ratio of exactly 1.0000\n")
    report(rows)


if __name__ == "__main__":
    test() if "--test" in sys.argv else report(load())

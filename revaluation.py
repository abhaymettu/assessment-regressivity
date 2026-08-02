"""Why the practice appears in some of a firm's municipalities and not others.

replication.py found the pattern held out of sample but not universally: the target firm
chases in some municipalities it assesses and not others, and assessment level predicted
which. Level is a proxy. Wisconsin publishes the real variable.

Every municipality files an assessment type each year, and DOR publishes it: FULL
REVALUATION, EXTERIOR REVALUATION, INTERIM MARKET, or MAINTENANCE. Only an interim market
update revalues property without a full revaluation, so it is the only type where an
assessor sets new values parcel by parcel using recent information. That is where copying
a sale price is even possible.

This splits the question in two, and the data separates them cleanly:

  the opportunity   does the municipality do an interim market update at all
  the choice        given the opportunity, does the assessor copy the sale price

Source: Wisconsin DOR, Wisconsin Real Estate Sales interactive data, the Tableau workbook
behind public.tableau.com/views/Sales0_1/Story1. Its `Asmt Type Unpivot` extract carries
assessment type by municipality and tax year. data/assessment_type.csv is that extract,
filtered to 2023 onward.

    python3 revaluation.py
    python3 revaluation.py --test
    python3 revaluation.py --extract   (re-read the .hyper, needs tableauhyperapi)
"""

import collections
import csv
import os
import re
import sys

import replication as R

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
TYPES = os.path.join(DATA, "assessment_type.csv")
HYPER = "/tmp/twb/Data/SLF Sales/Asmt Type Unpivot.hyper"

KIND = {"C": "City", "V": "Village", "T": "Town"}
TAX_YEAR = "2025"
# Order matters only for display: most to least invasive.
ORDER = ["FULL REVALUATION", "EXTERIOR REVALUATION", "INTERIM MARKET", "MAINTENANCE"]


def extract():
    """Re-read the Tableau extract. Only needed if the published workbook changes."""
    from tableauhyperapi import Connection, HyperProcess, Telemetry

    q = ('SELECT "AUTHCODE", "Municipality", "TAXYR", "VALUE_METRIC", "AMOUNT" '
         'FROM "Extract"."Extract" WHERE "TAXYR" >= 2023')
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, HYPER) as c:
            rows = c.execute_list_query(q)
    with open(TYPES, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["authcode", "municipality", "taxyr", "metric", "amount"])
        for r in rows:
            w.writerow([r[0], r[1], int(r[2]), r[3].strip(), int(r[4] or 0)])
    print(f"wrote {TYPES} with {len(rows)} rows")


def norm(name):
    return re.sub(r"[^A-Z]", "", name.upper())


def load_types(year=TAX_YEAR):
    """(county prefix, normalised name, kind) -> assessment type for the tax year.

    Municipality names repeat across Wisconsin counties, so the name alone is not a key.
    There are two Middletons and two Cottage Groves in this study's counties before you
    leave Dane. The authcode's first two digits are the county, which makes the key
    unique.
    """
    out = {}
    with open(TYPES, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["taxyr"] != year or r["amount"] != "1":
                continue
            m = re.match(r"^\d+ (.+) \(([TVC])\)$", r["municipality"].strip())
            if m:
                key = (r["authcode"][:2], norm(m.group(1)), KIND[m.group(2)])
                out[key] = r["metric"].replace(" (CT)", "")
    return out


def county_prefixes(types):
    """Map each study county to its authcode prefix, by matching municipality names.

    Wisconsin numbers counties alphabetically, but deriving the prefix from the data
    rather than assuming that keeps the join honest if the coding ever differs.
    """
    from assessors import load_roster
    out = {}
    for county in R.COUNTIES + ["DANE"]:
        want = {(norm(m), k) for m, k in load_roster(county)}
        best, score = None, 0
        for prefix in {p for p, _, _ in types}:
            have = {(n, k) for p, n, k in types if p == prefix}
            overlap = len(want & have)
            if overlap > score:
                best, score = prefix, overlap
        if best and score >= len(want) * 0.8:
            out[county] = best
    return out


def group_of(firm):
    if firm == R.TARGET:
        return R.TARGET
    if "Drea" in firm:
        return "Madison (in-house)"
    return "every other contractor"


def measured():
    """Every municipality measurable for chasing, with its 2025 assessment type."""
    types = load_types()
    prefix = county_prefixes(types)
    rows = []
    for c in R.COUNTIES:
        t = R.county_table(c)
        if t:
            rows += t
    rows += R.dane_rows()
    for r in rows:
        place, _, kind = r["municipality"].partition(",")
        key = (prefix.get(r["county"]), norm(place), kind.replace("of", "").strip())
        r["type"] = types.get(key, "unknown")
        r["group"] = group_of(r["firm"])
        r["chases"] = r["rate"] > 0.50
    return rows


def report():
    rows = measured()
    chasing = [r for r in rows if r["chases"]]

    print(f"{len(rows)} municipalities across 5 counties with enough pre-lien sales to")
    print(f"measure, joined to their {TAX_YEAR} assessment type.\n")

    print(f"{'2025 assessment type':<24}{'assessor':<26}{'chasing':>9}{'total':>7}")
    tab = collections.Counter()
    for r in rows:
        tab[(r["type"], r["group"])] += 1
    chase_tab = collections.Counter((r["type"], r["group"]) for r in chasing)
    for ty in ORDER + ["unknown"]:
        for g in (R.TARGET, "Madison (in-house)", "every other contractor"):
            n = tab[(ty, g)]
            if n:
                print(f"{ty:<24}{g:<26}{chase_tab[(ty, g)]:>9}{n:>7}")

    interim = [r for r in rows if r["type"] == "INTERIM MARKET"]
    other_types = [r for r in rows if r["type"] not in ("INTERIM MARKET", "unknown")]

    print(f"\nEvery one of the {len(chasing)} chasing municipalities did an interim market")
    print(f"update in {TAX_YEAR}. None of the {len(other_types)} municipalities on any other")
    print("assessment type chases, including every one of the target firm's own.")

    tgt = [r for r in interim if r["group"] == R.TARGET]
    oth = [r for r in interim if r["group"] == "every other contractor"]
    print(f"\nWithin interim market updates, where copying a sale price is possible at all:")
    print(f"  {R.TARGET}: {sum(1 for r in tgt if r['chases'])} of {len(tgt)}")
    print(f"  every other contractor: {sum(1 for r in oth if r['chases'])} of {len(oth)}")

    print("\nThat separates the opportunity from the choice. Interim market updates are")
    print("the only assessment type where an assessor sets new values parcel by parcel,")
    print("so they are the only place the practice can occur. Given that opportunity,")
    print("one firm takes it every time and no other contractor takes it at all.")
    print("\nIt also explains the municipalities where the firm does not chase. They are")
    print("not exceptions to a rule about the firm. They are maintenance years, where no")
    print("assessor is revaluing anything.")


def test():
    types = load_types()
    assert len(types) > 1800, f"only {len(types)} municipalities carry a {TAX_YEAR} type"

    prefix = county_prefixes(types)
    assert len(prefix) == len(R.COUNTIES) + 1, \
        f"only resolved county prefixes for {sorted(prefix)}"
    assert len(set(prefix.values())) == len(prefix), \
        f"two counties resolved to the same prefix: {prefix}"

    rows = measured()
    known = [r for r in rows if r["type"] != "unknown"]
    assert len(known) == len(rows), \
        f"{len(rows) - len(known)} municipalities did not match an assessment type"

    chasing = [r for r in rows if r["chases"]]
    assert len(chasing) >= 8, f"only {len(chasing)} chasing municipalities to explain"

    # The mechanism claim. Every chasing municipality must be an interim market update,
    # and it must not be true that interim market alone explains chasing, or the finding
    # would be about assessment type rather than about who does the assessing.
    assert all(r["type"] == "INTERIM MARKET" for r in chasing), \
        "a chasing municipality is on some other assessment type"

    interim = [r for r in rows if r["type"] == "INTERIM MARKET"]
    tgt = [r for r in interim if r["group"] == R.TARGET]
    oth = [r for r in interim if r["group"] == "every other contractor"]
    assert len(tgt) >= 5 and len(oth) >= 5, "not enough interim market municipalities"
    assert all(r["chases"] for r in tgt), \
        f"target firm does not chase in all its interim market municipalities"
    assert not any(r["chases"] for r in oth), \
        "another contractor chases during an interim market update"

    # And the firm's non-chasing municipalities must be explained, not left dangling.
    firm_rows = [r for r in rows if r["group"] == R.TARGET]
    unexplained = [r for r in firm_rows
                   if not r["chases"] and r["type"] == "INTERIM MARKET"]
    assert not unexplained, \
        f"{len(unexplained)} of the firm's interim market municipalities do not chase"

    print(f"ok: all {len(chasing)} chasing municipalities are interim market updates;")
    print(f"    within those, target {len(tgt)}/{len(tgt)} and other contractors "
          f"0/{len(oth)}\n")
    report()


if __name__ == "__main__":
    if "--extract" in sys.argv:
        extract()
    elif "--test" in sys.argv:
        test()
    else:
        report()

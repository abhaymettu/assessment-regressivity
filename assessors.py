"""Who assesses the municipalities that chase sales.

municipalities.py established that chasing is bimodal: six Dane County jurisdictions
adopt the sale price outright on most pre-lien sales, twelve essentially never do, and
nothing sits between. That rules out a shared data pipeline, but it leaves the more
useful question open. Wisconsin municipalities mostly do not employ their own assessor,
they contract one, and a handful of firms cover most of the state.

If the six chasers all contract the same firm, the finding stops being about six
independent offices and becomes about one vendor's methodology, which is a different and
larger claim. If they are spread across firms, then chasing is a choice made locally and
the six have to be addressed separately.

Roster: Wisconsin DOR, Wisconsin Municipal Assessors, data/assrlist.pdf.

    python3 assessors.py          (needs data/assessors_dane.csv, see --extract)
    python3 assessors.py --extract   (re-parse the PDF, needs pdfplumber)
    python3 assessors.py --test
"""

import collections
import csv
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RATIOS = os.path.join(DATA, "ratios.csv")
ROSTER = os.path.join(DATA, "assessors_dane.csv")
PARCELS = os.path.join(DATA, "parcels_dane.csv")
PDF = os.path.join(DATA, "assrlist.pdf")

# A municipality that did not revalue for 2025 has stale assessed values and no new
# assessments to set, so it cannot chase and is not evidence either way. Wisconsin
# publishes an estimated fair market value per parcel alongside the assessed value, and
# their ratio is the municipality's assessment level, computed by the state and entirely
# independent of the sales used elsewhere in this repo. Below this level a municipality
# is treated as not having revalued.
REVALUED_LEVEL = 0.85

KIND = {"C": "City", "V": "Village", "T": "Town"}
# Firm names are written inconsistently across rows of the roster, so they are folded
# before counting. Otherwise one firm splits into three and the answer inverts.
ALIASES = [
    (r"^ACCURATE APPRAISAL.*", "Accurate Appraisal LLC"),
    (r"^ASSOC(IATED)? APPR.*", "Associated Appraisal Consultants"),
    (r"^BRUCE GARDINER.*", "Bruce Gardiner Appraisals"),
    (r"^TYLER TECHNOLOGIES.*", "Tyler Technologies"),
    # Madison employs its own assessor rather than contracting one, and the roster row
    # runs the name into the office address, which the address heuristic cannot split.
    (r"^MICHELLE DREA.*", "Michelle Drea (Madison, in-house)"),
]


def norm(name):
    """Fold spacing and punctuation so MC FARLAND and MCFARLAND are one place."""
    return re.sub(r"[^A-Z]", "", name.upper())


def fold_firm(raw):
    raw = " ".join(raw.split()).rstrip(",.")
    for pattern, canonical in ALIASES:
        if re.match(pattern, raw.upper()):
            return canonical
    return raw.title()


def extract():
    """Parse the DOR roster PDF into data/assessors_dane.csv."""
    import pdfplumber  # only needed when re-extracting

    rows = []
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text(layout=True) or "").splitlines():
                line = " ".join(line.split())
                m = re.match(r"^(.+?) ([TVC]) DANE (.+)$", line)
                if not m:
                    continue
                place, kind, rest = m.groups()
                # The firm name runs until the address starts. Addresses begin with a
                # PO box, a house number, or a fire-number like N5375.
                firm = re.split(r"\s(?=PO BOX\b|\d+\s|[NWES]\d+\s)", rest, maxsplit=1)[0]
                rows.append({"municipality": place.strip(),
                             "kind": KIND[kind],
                             "firm": fold_firm(firm)})
    with open(ROSTER, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["municipality", "kind", "firm"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {ROSTER} with {len(rows)} Dane County municipalities")
    return rows


def load_roster():
    with open(ROSTER, newline="") as fh:
        return {(norm(r["municipality"]), r["kind"]): r["firm"]
                for r in csv.DictReader(fh)}


def assessment_levels():
    """Median assessed / state estimated fair market value, per municipality."""
    by = collections.defaultdict(list)
    with open(PARCELS, newline="") as fh:
        for r in csv.DictReader(fh):
            a = float(r["CNTASSDVALUE"] or 0)
            f = float(r["ESTFMKVALUE"] or 0)
            if a > 0 and f > 0:
                by[r["PLACENAME"].strip().upper()].append(a / f)
    return {k: statistics.median(v) for k, v in by.items() if len(v) >= 50}


def load_rates():
    """Pre-lien exact-match rate per municipality, the chasing measure."""
    with open(RATIOS, newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["post_lien"] == "0"]
    by = collections.defaultdict(list)
    for r in rows:
        by[r["municipality"]].append(r)
    out = {}
    for m, v in by.items():
        if len(v) < 50:
            continue
        exact = sum(1 for r in v
                    if abs(float(r["assessed"]) - float(r["sale_price"])) < 1.0)
        # "Madison, City of" -> ("MADISON", "City")
        place, _, kind = m.partition(",")
        kind = kind.replace("of", "").strip()
        out[m] = {"n": len(v), "rate": exact / len(v),
                  "key": (norm(place), kind),
                  "place_key": f"{kind.upper()} OF {place.strip().upper()}"}
    return out


def report():
    roster = load_roster()
    rates = load_rates()
    levels = assessment_levels()

    joined = []
    for m, v in rates.items():
        firm = roster.get(v["key"])
        if firm:
            joined.append((m, v["n"], v["rate"], firm,
                           levels.get(v["place_key"], float("nan"))))
    joined.sort(key=lambda x: -x[2])

    print("Chasing rate, assessment level and contracted assessor, Dane County")
    print("municipalities with at least 50 pre-lien sales\n")
    print(f"{'municipality':<28}{'n':>6}{'exact':>8}{'level':>8}   assessor")
    for m, n, rate, firm, lvl in joined:
        flag = "" if lvl >= REVALUED_LEVEL else "  (stale)"
        print(f"{m:<28}{n:>6}{rate:>7.1%}{lvl:>8.3f}   {firm}{flag}")

    stale = [j for j in joined if j[4] < REVALUED_LEVEL]
    if stale:
        print(f"\n{len(stale)} municipalities are below an assessment level of "
              f"{REVALUED_LEVEL:.2f} and did not")
        print("revalue for 2025. They set no new assessments, so they had nothing to")
        print("chase and are excluded from the comparison below:")
        for m, _, rate, firm, lvl in stale:
            print(f"  {m:<26}level {lvl:.3f}, chasing {rate:.1%}, {firm}")

    joined = [j for j in joined if j[4] >= REVALUED_LEVEL]
    print(f"\nAmong the {len(joined)} municipalities that did revalue:")

    chasers = [j for j in joined if j[2] > 0.50]
    clean = [j for j in joined if j[2] < 0.05]

    print(f"\n{len(chasers)} chasing, {len(clean)} not.\n")
    for label, group in (("Chasing", chasers), ("Not chasing", clean)):
        firms = collections.Counter(f for _, _, _, f, _ in group)
        print(f"{label}, by assessor:")
        for firm, cnt in firms.most_common():
            print(f"  {cnt:>2}  {firm}")
        print()

    chase_firms = {f for _, _, _, f, _ in chasers}
    clean_firms = {f for _, _, _, f, _ in clean}
    both = chase_firms & clean_firms

    # The interesting comparison is per contractor: of the revalued municipalities a
    # firm assesses, how many chase.
    print("Per assessor, among revalued municipalities:\n")
    print(f"{'assessor':<38}{'chasing':>9}{'total':>7}")
    tally = collections.defaultdict(lambda: [0, 0])
    for _, _, rate, firm, _ in joined:
        tally[firm][1] += 1
        if rate > 0.50:
            tally[firm][0] += 1
    for firm, (c, t) in sorted(tally.items(), key=lambda x: (-x[1][0] / x[1][1], -x[1][1])):
        print(f"{firm:<38}{c:>9}{t:>7}")

    contractors = {f: v for f, v in tally.items() if v[1] >= 3}
    perfect = [f for f, (c, t) in contractors.items() if c == t]
    none = [f for f, (c, t) in contractors.items() if c == 0]
    print()
    if perfect and none:
        for f in perfect:
            print(f"{f} chases in {contractors[f][0]} of {contractors[f][1]} of the")
            print("revalued municipalities it assesses.")
        for f in none:
            print(f"{f} chases in none of its {contractors[f][1]}.")
        print("\nThe two exceptions to the vendor pattern turned out not to be exceptions:")
        print("both are municipalities that did not revalue, so no assessment was set")
        print("that could have been copied from a sale.")
        print("\nThat makes this a property of who does the assessing, not of the")
        print("municipality. It is a claim about a contractor's methodology, and it is")
        print("the version worth taking to anyone who can act on it.")
    elif both:
        print(f"{len(both)} assessor(s) appear on both sides: {', '.join(sorted(both))},")
        print("so the practice does not track the vendor cleanly.")


def test():
    roster = load_roster()
    assert len(roster) >= 55, f"roster has only {len(roster)} Dane municipalities"

    rates = load_rates()
    matched = [m for m, v in rates.items() if v["key"] in roster]
    # If the name join silently degraded, the report would quietly drop municipalities
    # and could drop exactly the ones that matter.
    assert len(matched) == len(rates), \
        f"only {len(matched)} of {len(rates)} municipalities matched the roster"

    firms = collections.Counter(roster.values())
    assert len(firms) >= 3, f"only {len(firms)} distinct firms, folding is too aggressive"
    assert max(firms.values()) < len(roster), "folding collapsed every firm into one"

    print(f"ok: {len(rates)} municipalities all matched to the roster, "
          f"{len(firms)} distinct assessors\n")
    report()


if __name__ == "__main__":
    if "--extract" in sys.argv:
        extract()
    elif "--test" in sys.argv:
        test()
    else:
        report()

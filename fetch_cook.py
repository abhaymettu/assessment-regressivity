"""Pull Cook County residential sales and assessed values, joined, for 2015 to 2019.

This is the external-validation input. Chris Berry's Center for Municipal Finance
published a sales ratio study for Cook County over exactly these years, so the county
and the window are chosen to land on numbers someone else already printed rather than
to find anything new.

Two Socrata datasets on the Cook County open data portal:

  wvhk-k5uv  Assessor - Parcel Sales      pin, tax year, sale date, sale price, class
  uzyt-m557  Assessor - Assessed Values   pin, tax year, mailed / certified / board value

Cook assesses class 2 residential at 10% of market value, so the assessed values here
are multiplied by 10 downstream to be comparable with a sale price. All three
assessment stages are kept because the published study does not say which one it used,
and cook.py has to try each.

Writes data/cook_sales.csv, one row per residential sale with the three assessment
stages attached. The assessed-value side is 1.58 million rows a year and is streamed
and discarded except for pins that sold, so the file stays small.

    python3 fetch_cook.py
    python3 fetch_cook.py --test
"""

import csv
import io
import os
import sys
import urllib.parse
import urllib.request

PORTAL = "https://datacatalog.cookcountyil.gov/resource"
SALES = "wvhk-k5uv"
VALUES = "uzyt-m557"
YEARS = [2015, 2016, 2017, 2018, 2019]

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "cook_sales.csv")

SALE_FIELDS = ["pin", "year", "class", "township_code", "nbhd", "sale_date",
               "sale_price", "is_multisale", "num_parcels_sale", "deed_type",
               "sale_filter_same_sale_within_365", "sale_filter_less_than_10k",
               "sale_filter_deed_type"]
VALUE_FIELDS = ["pin", "year", "mailed_tot", "certified_tot", "board_tot"]
COLUMNS = SALE_FIELDS + ["mailed_tot", "certified_tot", "board_tot"]


def fetch(dataset, select, where, limit=3_000_000):
    """Socrata CSV export. One request per year, gzipped, streamed to a reader."""
    q = urllib.parse.urlencode({"$select": ",".join(select), "$where": where,
                                "$limit": limit})
    req = urllib.request.Request(f"{PORTAL}/{dataset}.csv?{q}",
                                 headers={"Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=600) as r:
        raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        import gzip
        raw = gzip.decompress(raw)
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))


def year_clause(y):
    """The sales dataset stores tax year as text and some rows carry '2015.0'."""
    return f"(year='{y}' OR year='{y}.0')"


def sales(y):
    rows = fetch(SALES, SALE_FIELDS, f"{year_clause(y)} AND starts_with(class,'2')")
    for r in rows:
        r["year"] = str(y)
    return rows


def values_for(y, pins):
    """Assessed values for one year, keeping only pins that sold that year."""
    out = {}
    for r in fetch(VALUES, VALUE_FIELDS, f"year='{y}' AND starts_with(class,'2')"):
        if r["pin"] in pins:
            out[r["pin"]] = r
    return out


def main():
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for y in YEARS:
            srows = sales(y)
            pins = {r["pin"] for r in srows}
            vals = values_for(y, pins)
            kept = 0
            for r in srows:
                v = vals.get(r["pin"])
                if not v:
                    continue
                r.update({k: v[k] for k in ("mailed_tot", "certified_tot", "board_tot")})
                w.writerow(r)
                kept += 1
            print(f"{y}: {len(srows)} sales, {kept} matched to an assessment "
                  f"({kept / len(srows):.1%})")
    print(f"wrote {OUT}")


def test():
    """One live year, checked for the fields the reproduction depends on."""
    srows = sales(2019)
    assert len(srows) > 50_000, f"only {len(srows)} class-2 sales in 2019"
    assert all(r["class"].startswith("2") for r in srows), "non-residential leaked in"
    # A third of recorded conveyances carry a nominal price (quitclaims, transfers into
    # trust). The published study drops anything at or below $100, so this only has to
    # leave a usable majority.
    priced = [r for r in srows if r["sale_price"] and float(r["sale_price"]) > 100]
    assert len(priced) > len(srows) * 0.6, f"only {len(priced)} of {len(srows)} priced"

    pins = {r["pin"] for r in srows}
    vals = values_for(2019, pins)
    assert len(vals) > len(pins) * 0.9, f"only {len(vals)} of {len(pins)} pins have a value"
    # Cook assesses class 2 at 10% of market, so a ratio near 1 only appears after
    # multiplying by 10. If that stops being true the whole reproduction is off by 10x.
    import statistics
    ratios = [float(vals[r["pin"]]["certified_tot"]) * 10 / float(r["sale_price"])
              for r in priced if r["pin"] in vals and float(vals[r["pin"]]["certified_tot"]) > 0]
    md = statistics.median(ratios)
    assert 0.7 < md < 1.2, f"median ratio {md:.3f}, the 10% assessment level is not holding"
    print(f"ok: {len(srows)} sales, {len(vals)} valued, median ratio {md:.3f}")


if __name__ == "__main__":
    test() if "--test" in sys.argv else main()

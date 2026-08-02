"""Pull the City of Madison assessor's parcel layer, which carries house characteristics.

The state parcel layer used everywhere else in this repo has an assessed value and an
address and nothing about the building. That is enough to say ratios differ across price
deciles, and not enough to say anything about why. Madison publishes its own layer with
the assessor's own inputs: year built, living area, bedrooms, baths, style, basement,
air conditioning, lot size, and the office's own neighborhood and assessment-area codes.

That turns the regressivity question from "do cheap houses carry higher ratios" into "do
two houses of the same age and size on the same street carry different ratios", which is
the version an assessor's office cannot answer by pointing at the market.

Only the characteristics are taken. Assessed values stay on the state layer so the
hedonic is run against exactly the same roll as findings 1 through 7, rather than
against whatever roll year Madison happens to be publishing today.

Writes data/parcels_madison.csv. Resumable.

    python3 fetch_madison.py
    python3 fetch_madison.py --test
"""

import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

SERVICE = ("https://maps.cityofmadison.com/arcgis/rest/services/Public/"
           "OPEN_DATA2/FeatureServer/0/query")
WHERE = "PropertyClass = 'Residential'"
FIELDS = [
    "Parcel", "Address", "PropertyClass", "PropertyUse", "HomeStyle",
    "YearBuilt", "TotalLivingArea", "FirstFloor", "SecondFloor",
    "Bedrooms", "FullBaths", "HalfBaths", "Fireplaces",
    "Basement", "FinishedBasement", "CentralAir", "ExteriorWall1",
    "LotSize", "LotWidth", "WaterFrontage", "TotalDwellingUnits",
    "NeighborhoodPrimary", "NeighborhoodSub", "AssessmentArea", "AreaName",
    "StreetName", "StreetType", "Ward",
    "CurrentLand", "CurrentImpr", "CurrentTotal",
]
PAGE = 2000
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "data", "parcels_madison.csv")


def query(params, tries=4):
    url = SERVICE + "?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                body = json.load(r)
            if "error" in body:
                raise RuntimeError(body["error"])
            return body
        except Exception as exc:
            if attempt == tries - 1:
                raise
            print(f"  retry {attempt + 1} after {exc}", file=sys.stderr)
            time.sleep(2 ** attempt)


def count():
    return query({"where": WHERE, "returnCountOnly": "true", "f": "json"})["count"]


def page(offset):
    body = query({
        "where": WHERE,
        "outFields": ",".join(FIELDS),
        "returnGeometry": "false",
        "orderByFields": "Parcel",
        "resultOffset": offset,
        "resultRecordCount": PAGE,
        "f": "json",
    })
    return [f["attributes"] for f in body["features"]]


def already_have():
    if not os.path.exists(OUT):
        return 0
    with open(OUT, newline="") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def main():
    total = count()
    done = already_have()
    print(f"Madison residential parcels: {total}, {done} already written")
    if done >= total:
        print("nothing to do")
        return
    with open(OUT, "a" if done else "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if not done:
            w.writeheader()
        offset = done
        while offset < total:
            rows = page(offset)
            if not rows:
                print(f"empty page at offset {offset}, stopping short of {total}")
                break
            w.writerows(rows)
            fh.flush()
            offset += len(rows)
            print(f"  {offset}/{total}", end="\r", flush=True)
    print(f"\nwrote {OUT}")


def test():
    """One live page, checked for the characteristics the hedonic needs."""
    rows = page(0)
    assert len(rows) == PAGE, f"expected {PAGE} rows, got {len(rows)}"
    assert set(FIELDS) <= set(rows[0]), "missing requested fields"
    # A hedonic with no living area is just the decile table again, so this is the one
    # field whose coverage decides whether finding 8 can exist at all.
    have = lambda f: sum(1 for r in rows if r[f] not in (None, "", 0))
    for f in ("YearBuilt", "TotalLivingArea"):
        assert have(f) > PAGE * 0.5, f"{f} present on only {have(f)} of {PAGE}"
    # Parcel is the join key back to the state layer, which is 12 digits with no
    # punctuation. If Madison ever reformats it, every join downstream goes to zero.
    assert all(r["Parcel"] and r["Parcel"].isdigit() and len(r["Parcel"]) == 12
               for r in rows), "Parcel is no longer a bare 12-digit key"
    print(f"ok: {len(rows)} rows, YearBuilt on {have('YearBuilt')}, "
          f"TotalLivingArea on {have('TotalLivingArea')}, "
          f"NeighborhoodPrimary on {have('NeighborhoodPrimary')}, "
          f"AssessmentArea on {have('AssessmentArea')}")


if __name__ == "__main__":
    test() if "--test" in sys.argv else main()

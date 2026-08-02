"""Pull class-1 residential parcels from the WI DOA statewide parcel layer.

Writes data/parcels_<county>.csv. Resumable: if the output exists, already-fetched
offsets are skipped, so a dropped connection costs one page rather than the whole pull.

    python3 fetch_parcels.py                    (Dane)
    python3 fetch_parcels.py WALWORTH COLUMBIA  (any counties, by name)
    python3 fetch_parcels.py --test
"""

import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

SERVICE = (
    "https://services3.arcgis.com/n6uYoouQZW75n5WI/arcgis/rest/services/"
    "Wisconsin_Statewide_Parcels_DB/FeatureServer/0/query"
)
COUNTY = "DANE"


def where():
    return f"CONAME='{COUNTY}' AND PROPCLASS='1'"
FIELDS = [
    "STATEID", "PARCELID", "TAXPARCELID", "TAXROLLYEAR",
    "SITEADRESS", "PLACENAME", "ZIPCODE", "SCHOOLDIST",
    "CNTASSDVALUE", "LNDVALUE", "IMPVALUE", "ESTFMKVALUE", "NETPRPTA",
    "PROPCLASS", "ASSDACRES", "LONGITUDE", "LATITUDE",
]
PAGE = 2000
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def out_path():
    return os.path.join(DATA, f"parcels_{COUNTY.lower().replace(' ', '_')}.csv")


def query(params, tries=4):
    """GET the FeatureServer with retries. ArcGIS returns 200 with an error body."""
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
    return query({"where": where(), "returnCountOnly": "true", "f": "json"})["count"]


def page(offset):
    body = query({
        "where": where(),
        "outFields": ",".join(FIELDS),
        "returnGeometry": "false",
        "orderByFields": "STATEID",
        "resultOffset": offset,
        "resultRecordCount": PAGE,
        "f": "json",
    })
    return [f["attributes"] for f in body["features"]]


def already_have():
    """Rows already written, so a rerun resumes instead of starting over."""
    if not os.path.exists(out_path()):
        return 0
    with open(out_path(), newline="") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def main():
    total = count()
    done = already_have()
    print(f"{COUNTY}: {total} parcels, {done} already written")
    if done >= total:
        print("nothing to do")
        return

    mode = "a" if done else "w"
    with open(out_path(), mode, newline="") as fh:
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
    print(f"\nwrote {out_path()}")


def test():
    """One live page, checked for the fields the ratio study actually depends on."""
    rows = page(0)
    assert len(rows) == PAGE, f"expected {PAGE} rows, got {len(rows)}"
    assert set(FIELDS) <= set(rows[0]), "missing requested fields"
    assert all(r["PROPCLASS"] == "1" for r in rows), "where clause leaked non-residential"
    valued = [r for r in rows if r["CNTASSDVALUE"]]
    assert len(valued) > PAGE * 0.9, f"only {len(valued)} of {PAGE} carry an assessed value"
    assert all(r["CNTASSDVALUE"] > 0 for r in valued), "non-positive assessed value"
    # Assessed total should be the land plus improvement split, or the split is unusable
    # for separating land-value error from building-value error later.
    split = [r for r in valued if r["LNDVALUE"] is not None and r["IMPVALUE"] is not None]
    agree = sum(1 for r in split if r["LNDVALUE"] + r["IMPVALUE"] == r["CNTASSDVALUE"])
    assert agree > len(split) * 0.95, f"land+improvement matches total on only {agree}/{len(split)}"
    print(f"ok: {len(rows)} rows, {len(valued)} valued, {agree}/{len(split)} splits reconcile")


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
    else:
        counties = [a.upper() for a in sys.argv[1:] if not a.startswith("-")] or ["DANE"]
        for c in counties:
            COUNTY = c
            main()

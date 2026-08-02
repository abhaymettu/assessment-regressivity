"""Join Dane County arms-length residential sales to the assessment roll.

Produces data/ratios.csv, one row per usable sale, carrying the sales ratio that the
IAAO statistics are computed from. Everything downstream depends on the filtering
decisions here, so they are explicit and each one is counted in the printed funnel
rather than applied silently.

    python3 ratios.py
    python3 ratios.py --test
"""

import csv
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PARCELS = os.path.join(DATA, "parcels_dane.csv")
OUT = os.path.join(DATA, "ratios.csv")

# A sale only measures market value if it is an actual arms-length exchange. RETR
# carries the two fields that establish this, so the filter is the state's own coding
# rather than a guess from the price.
ARMS_CONVEYANCE = {"Sale"}
ARMS_RELATIONSHIP = {"No relationship"}
RESIDENTIAL = {"Land and buildings/improvements", "Condominium"}

# A ratio study measures assessment error, not data entry error. Ratios this far from
# parity are almost always a parcel split, a partial interest, or a teardown, and IAAO
# guidance is to trim them before computing dispersion. Trimmed rows are reported.
RATIO_FLOOR, RATIO_CEIL = 0.10, 3.00
MIN_PRICE = 1000


def parcel_key(retr_parcel):
    """RETR writes '\\t251/070926102199'. The roll keys on the part after the slash."""
    return retr_parcel.strip().lstrip("\t").strip().split("/")[-1].strip()


def money(s):
    s = (s or "").strip().replace("$", "").replace(",", "")
    return float(s) if s else 0.0


def load_parcels():
    with open(PARCELS, newline="") as fh:
        return {r["PARCELID"].strip(): r for r in csv.DictReader(fh)}


def load_transfers():
    files = sorted(glob.glob(os.path.join(DATA, "RETRHistoricalReport*.csv")))
    if not files:
        sys.exit("no RETRHistoricalReport*.csv in data/")
    rows = []
    for path in files:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows += [r for r in csv.DictReader(fh)
                     if r["County"].strip().upper() == "DANE"]
    return files, rows


def build():
    parcels = load_parcels()
    files, transfers = load_transfers()

    funnel = {"dane transfers": len(transfers)}
    rows, dropped = [], {"not residential": 0, "not arms-length": 0,
                         "no price": 0, "unmatched parcel": 0,
                         "no assessed value": 0, "ratio out of range": 0}

    for t in transfers:
        if t["Property Type"].strip() not in RESIDENTIAL:
            dropped["not residential"] += 1
            continue
        if (t["Conveyance Type"].strip() not in ARMS_CONVEYANCE
                or t["Grantor/Grantee Relationship"].strip() not in ARMS_RELATIONSHIP):
            dropped["not arms-length"] += 1
            continue
        price = money(t["Sale Price"])
        if price < MIN_PRICE:
            dropped["no price"] += 1
            continue
        p = parcels.get(parcel_key(t["Parcel Number"]))
        if p is None:
            dropped["unmatched parcel"] += 1
            continue
        assessed = money(p["CNTASSDVALUE"])
        if assessed <= 0:
            dropped["no assessed value"] += 1
            continue
        ratio = assessed / price
        if not (RATIO_FLOOR <= ratio <= RATIO_CEIL):
            dropped["ratio out of range"] += 1
            continue
        rows.append({
            "parcel": p["PARCELID"],
            "municipality": t["Municipality"].strip(),
            "address": p["SITEADRESS"] or t["Physical Address"].strip(),
            "school_district": p["SCHOOLDIST"],
            "conveyance_date": t["Conveyance Date"].strip(),
            "sale_price": round(price, 2),
            "assessed": round(assessed, 2),
            "land": money(p["LNDVALUE"]),
            "improvement": money(p["IMPVALUE"]),
            "net_tax": money(p["NETPRPTA"]),
            "lat": p["LATITUDE"],
            "lon": p["LONGITUDE"],
            "ratio": round(ratio, 6),
        })

    funnel.update(dropped)
    funnel["usable sales"] = len(rows)

    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f"{len(files)} monthly RETR files")
    for k, v in funnel.items():
        print(f"  {k:>22}: {v}")
    print(f"wrote {OUT}")
    return rows


def test():
    rows = build()
    assert rows, "no usable sales"
    # The join is the project's single biggest risk. If it degrades, the ratio study is
    # measuring which parcels happen to match rather than which are over-assessed.
    parcels = load_parcels()
    _, transfers = load_transfers()
    arms = [t for t in transfers
            if t["Property Type"].strip() in RESIDENTIAL
            and t["Conveyance Type"].strip() in ARMS_CONVEYANCE
            and t["Grantor/Grantee Relationship"].strip() in ARMS_RELATIONSHIP]
    matched = sum(1 for t in arms if parcel_key(t["Parcel Number"]) in parcels)
    rate = matched / len(arms)
    assert rate > 0.80, f"join rate fell to {rate:.1%}, was 90% on 2025-01 and 2025-02"

    assert all(r["ratio"] > 0 for r in rows), "non-positive ratio survived"
    assert all(r["sale_price"] >= MIN_PRICE for r in rows), "sub-threshold price survived"
    # Median ratio should sit near the assessment level, not near zero or two.
    med = sorted(r["ratio"] for r in rows)[len(rows) // 2]
    assert 0.5 < med < 1.5, f"median ratio {med:.3f} is implausible for a current roll"
    print(f"ok: join {rate:.1%}, {len(rows)} usable sales, median ratio {med:.3f}")


if __name__ == "__main__":
    test() if "--test" in sys.argv else build()

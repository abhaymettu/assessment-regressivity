"""Does Madison's regressivity survive controls for what the house actually is?

The decile table says cheap homes carry higher assessment ratios than expensive ones. An
assessor's office has a ready answer to that: cheap and expensive homes are different
homes. They are older, smaller, in different parts of the city, and a mass appraisal
model doing its job produces different errors on different kinds of property without any
of it being about price.

The state parcel layer cannot answer that. It holds an assessed value and an address and
nothing about the building. The City of Madison publishes its assessor's own inputs, so
joining them lets the question be asked as "two houses of the same age, size, style and
assessment neighborhood, one of which sold for twice the other".

Assessed values come from the state layer, not Madison's, so this runs against exactly
the same 2025 roll as findings 1 through 7. Madison supplies characteristics only.

## The trap, which is most of what this script is for

The obvious specification is to regress log assessment ratio on log2 sale price and add
the characteristics as controls. It is wrong, and it is wrong in the direction that
flatters the finding.

The dependent variable is log(assessed) - log(price) and the regressor is log2(price), so
price appears on both sides. Controls that predict assessed value strip out the part of
the left side that is not price, and what is left over is driven by price alone. In the
limit where the controls explain the assessor's value completely, the coefficient goes to
-ln 2 = -0.693 no matter how fair the roll is. Adding controls does not test the finding,
it walks the estimate toward a constant that has nothing to do with assessment quality.

This is measured rather than asserted. A synthetic roll is built in which the assessor is
neutral by construction, its value being exactly the hedonic prediction of sale price with
no price grading of any kind, and every specification is run against it. That column is
the null. A specification whose null is -0.69 cannot be read as evidence of anything.

## The specification that does work

Regress log assessment ratio on log2 of *predicted* price, where the prediction comes
from the characteristics and the assessment area rather than from the sale. The
prediction contains no information from the individual transaction, so the sale-price
noise that contaminates the naive specifications cannot enter the regressor. On the
neutral synthetic roll this returns exactly zero, which is what a valid test looks like.

    python3 hedonic.py
    python3 hedonic.py --test
"""

import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RATIOS = os.path.join(HERE, "data", "ratios.csv")
MADISON = os.path.join(HERE, "data", "parcels_madison.csv")

MUNICIPALITY = "Madison, City of"
ROLL_YEAR = 2025

CATEGORICAL = ["HomeStyle", "PropertyUse", "ExteriorWall1"]
NUMERIC = ["area", "age", "beds", "fullbaths", "halfbaths", "fireplaces",
           "lot", "basement", "air"]

# IAAO's neutral band for a per-doubling regressivity coefficient.
IAAO_BAND = 0.05


def num(s):
    try:
        return float(s or 0)
    except ValueError:
        return 0.0


def load():
    """Chase-free Madison sales joined to Madison's own parcel characteristics."""
    with open(MADISON, newline="") as fh:
        chars = {r["Parcel"].strip(): r for r in csv.DictReader(fh)}

    rows, drops = [], {"not Madison": 0, "chased window": 0, "no parcel match": 0,
                       "no characteristics": 0}
    with open(RATIOS, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["municipality"] != MUNICIPALITY:
                drops["not Madison"] += 1
                continue
            if r["study"] != "1":
                drops["chased window"] += 1
                continue
            c = chars.get(r["parcel"].strip())
            if c is None:
                drops["no parcel match"] += 1
                continue
            area, built = num(c["TotalLivingArea"]), num(c["YearBuilt"])
            if area <= 200 or not (1800 < built <= ROLL_YEAR):
                drops["no characteristics"] += 1
                continue
            rows.append({
                "y": math.log(float(r["ratio_adj"])),
                "logprice": math.log(float(r["price_adj"])),
                "log2price": math.log(float(r["price_adj"]), 2),
                "area": math.log(area),
                "age": ROLL_YEAR - built,
                "beds": num(c["Bedrooms"]),
                "fullbaths": num(c["FullBaths"]),
                "halfbaths": num(c["HalfBaths"]),
                "fireplaces": num(c["Fireplaces"]),
                "lot": math.log(max(num(c["LotSize"]), 1.0)),
                "basement": float(num(c["Basement"]) > 0),
                "air": float((c["CentralAir"] or "").strip().upper() == "YES"),
                "area_code": (c["AssessmentArea"] or "?").strip(),
                "ratio": float(r["ratio_adj"]),
                "price": float(r["price_adj"]),
                **{k: (c[k] or "?").strip() for k in CATEGORICAL},
            })
    return rows, drops


def controls(rows):
    """The hedonic columns, without the price term."""
    cols = [(f, [r[f] for r in rows]) for f in NUMERIC]
    cols.append(("age2", [r["age"] ** 2 / 1000 for r in rows]))
    for f in CATEGORICAL:
        levels = sorted({r[f] for r in rows})
        ref = max(levels, key=lambda v: sum(1 for r in rows if r[f] == v))
        cols += [(f"{f}={lv}", [float(r[f] == lv) for r in rows])
                 for lv in levels if lv != ref]
    return cols


def demean(vec, groups):
    """Within-transformation. Absorbs one fixed effect per group."""
    total, count = {}, {}
    for v, g in zip(vec, groups):
        total[g] = total.get(g, 0.0) + v
        count[g] = count.get(g, 0) + 1
    return [v - total[g] / count[g] for v, g in zip(vec, groups)], \
           {g: total[g] / count[g] for g in total}


def solve(a, b):
    """Gaussian elimination on the normal equations, with collinear columns zeroed.

    A rare style level can go collinear inside a single assessment area. That should
    cost one coefficient rather than the whole fit.
    """
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    dropped = []
    for c in range(n):
        p = max(range(c, n), key=lambda i: abs(m[i][c]))
        if abs(m[p][c]) < 1e-9:
            dropped.append(c)
            continue
        m[c], m[p] = m[p], m[c]
        for i in range(n):
            if i == c or abs(m[i][c]) < 1e-15:
                continue
            f = m[i][c] / m[c][c]
            for j in range(c, n + 1):
                m[i][j] -= f * m[c][j]
    x = [0.0] * n
    for c in range(n):
        if c not in dropped:
            x[c] = m[c][n] / m[c][c]
    return x, dropped


def ols(y, cols, groups=None):
    """Coefficient on column 0, its standard error, R-squared, and fitted values.

    The intercept is handled by demeaning. With groups the demeaning is by group, which
    absorbs a fixed effect per group without materialising the dummy columns.
    """
    n = len(y)
    if groups is None:
        my = sum(y) / n
        yy = [v - my for v in y]
        xs, means = [], []
        for _, col in cols:
            mc = sum(col) / n
            xs.append([v - mc for v in col])
            means.append(mc)
        base = [my] * n
        absorbed = 1
    else:
        yy, gm = demean(y, groups)
        xs, means = [], []
        for _, col in cols:
            d, _ = demean(col, groups)
            xs.append(d)
            means.append(0.0)
        base = [gm[g] for g in groups]
        absorbed = len(gm)

    k = len(xs)
    a = [[sum(xs[i][t] * xs[j][t] for t in range(n)) for j in range(k)] for i in range(k)]
    b = [sum(xs[i][t] * yy[t] for t in range(n)) for i in range(k)]
    beta, dropped = solve(a, b)

    fitted = [base[t] + sum(beta[i] * xs[i][t] for i in range(k)) for t in range(n)]
    resid = [yy[t] - sum(beta[i] * xs[i][t] for i in range(k)) for t in range(n)]
    rss = sum(e * e for e in resid)
    tss = sum(v * v for v in yy)
    df = max(n - (k - len(dropped)) - absorbed, 1)

    # Standard error of beta[0] needs the (0,0) entry of the inverse of X'X. One more
    # elimination against the first unit vector gets it without inverting the whole thing.
    inv_col, _ = solve([row[:] for row in a], [1.0] + [0.0] * (k - 1))
    se = math.sqrt(max(rss / df * inv_col[0], 0.0))
    return {"beta": beta[0], "se": se, "n": n, "r2": 1 - rss / tss if tss else 0.0,
            "fitted": fitted}


def predicted_log_price(rows):
    """Hedonic prediction of log sale price from characteristics and assessment area.

    Carries no information from the individual transaction beyond what the assessor
    could also see, which is exactly what makes it usable as a regressor.
    """
    y = [r["logprice"] for r in rows]
    fit = ols(y, controls(rows), [r["area_code"] for r in rows])
    return fit["fitted"], fit["r2"]


SPECS = [
    ("price only", False, False),
    ("plus house characteristics", True, False),
    ("plus assessment-area fixed effects", False, True),
    ("plus both", True, True),
]


def naive(rows, y):
    """The four specifications that put realised sale price on both sides."""
    out = []
    for name, hedonic, fe in SPECS:
        cols = [("log2price", [r["log2price"] for r in rows])]
        if hedonic:
            cols += controls(rows)
        groups = [r["area_code"] for r in rows] if fe else None
        out.append((name, ols(y, cols, groups)))
    return out


def valid(rows, y, x):
    """Log ratio on log2 predicted price. No realised price on the right-hand side."""
    return ols(y, [("log2pred", x)])


def neutral_roll(rows, phat):
    """A synthetic roll on which the assessor is neutral by construction.

    Its assessed value is the hedonic prediction of sale price, so it has no price
    grading at all. Any slope a specification returns here is mechanical.
    """
    return [phat[t] - rows[t]["logprice"] for t in range(len(rows))]


def deciles(rows, values):
    order = sorted(range(len(rows)), key=lambda t: values[t])
    n = len(order)
    out = []
    for d in range(10):
        idx = order[d * n // 10:(d + 1) * n // 10]
        rs = sorted(rows[t]["ratio"] for t in idx)
        out.append((d + 1, len(idx),
                    math.exp(values[idx[0]]), math.exp(values[idx[-1]]),
                    rs[len(rs) // 2]))
    return out


def slope_only(pairs):
    """Plain log ratio on log2 price, for comparing sample definitions."""
    xs = [math.log(p, 2) for p, _ in pairs]
    ys = [math.log(r) for _, r in pairs]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    return (sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            / sum((x - mx) ** 2 for x in xs))


def full_study_sample():
    """Every chase-free Madison sale, joined or not. This is what municipalities.py
    reports, and the difference between the two is worth stating out loud."""
    with open(RATIOS, newline="") as fh:
        return [(float(r["price_adj"]), float(r["ratio_adj"]))
                for r in csv.DictReader(fh)
                if r["municipality"] == MUNICIPALITY and r["study"] == "1"]


def report():
    rows, drops = load()
    y = [r["y"] for r in rows]
    phat, price_r2 = predicted_log_price(rows)
    x_pred = [v / math.log(2) for v in phat]

    print("Madison, City of. Chase-free sales joined to the assessor's own "
          "characteristics.\n")
    for k, v in drops.items():
        print(f"  {k:>22}: {v}")
    print(f"  {'usable':>22}: {len(rows)}")
    print(f"  {'assessment areas':>22}: {len({r['area_code'] for r in rows})}")
    print(f"\nThe hedonic explains {price_r2:.1%} of the variance of log sale price")
    print("within an assessment area, on top of whatever the area itself explains.")

    # The join is not neutral, and pretending otherwise would hide a real sensitivity.
    everything = full_study_sample()
    joined = [(r["price"], r["ratio"]) for r in rows]
    print(f"\nThe {len(everything) - len(joined)} chase-free Madison sales that do not "
          f"join move the uncontrolled")
    print(f"slope from {slope_only(everything):+.4f} on all "
          f"{len(everything)} to {slope_only(joined):+.4f} on the {len(joined)} that do.")
    print("They are parcels the state layer codes as class-1 residential but Madison")
    print("holds no house record for: apartment buildings, assemblies, and a $3.4m")
    print("parcel assessed at 0.14 of it. The joined sample is the narrower and cleaner")
    print("one and it is also the more regressive one. Both are reported rather than")
    print("whichever is convenient.")

    y_null = neutral_roll(rows, phat)
    obs = naive(rows, y)
    nul = naive(rows, y_null)

    print("\nSlope of log assessment ratio on log2 sale price, and what the same")
    print("specification returns on a roll with no regressivity built into it")
    print(f"{'specification':<38}{'slope':>9}{'se':>8}{'null':>9}{'excess':>9}")
    for (name, o), (_, z) in zip(obs, nul):
        print(f"{name:<38}{o['beta']:>+9.4f}{o['se']:>8.4f}"
              f"{z['beta']:>+9.4f}{o['beta'] - z['beta']:>+9.4f}")
    print(f"\n-ln 2 = {-math.log(2):.4f}. The fully controlled null sits on it to four")
    print("decimals, which is the algebra: once the controls explain the assessor's value,")
    print("the regression is log(A) - log(P) on log(P) with the log(A) part held fixed.")
    print("Every one of these four numbers is contaminated. The most heavily controlled")
    print("specification is the most contaminated, not the most convincing.")

    v = valid(rows, y, x_pred)
    vnull = valid(rows, y_null, x_pred)
    print("\nThe specification that is not contaminated")
    print(f"{'log ratio on log2 predicted price':<38}"
          f"{v['beta']:>+9.4f}{v['se']:>8.4f}{vnull['beta']:>+9.4f}"
          f"{v['beta'] - vnull['beta']:>+9.4f}")
    print(f"\nt = {v['beta'] / v['se']:.1f}. The null is zero to four decimals, by")
    print("construction rather than by luck: the regressor contains nothing from the sale.")

    raw = obs[0][1]["beta"]
    print(f"\nMadison's uncontrolled slope is {raw:+.4f}. Controlling properly for age,")
    print(f"size, bedrooms, baths, lot, style, use, basement, air conditioning and the")
    print(f"assessor's own neighborhood leaves {v['beta']:+.4f}, "
          f"{v['beta'] / raw:.0%} of it.")
    print(f"IAAO's neutral band is plus or minus {IAAO_BAND:.2f}. "
          f"{'Outside it.' if abs(v['beta']) > IAAO_BAND else 'Inside it.'}")

    print("\nMedian assessment ratio by decile of predicted price")
    print(f"{'decile':<8}{'n':>6}{'predicted price range':>28}{'median ratio':>14}")
    tbl = deciles(rows, phat)
    for d, cnt, lo, hi, md in tbl:
        print(f"{d:<8}{cnt:>6}{f'${lo:,.0f} to ${hi:,.0f}':>28}{md:>14.3f}")
    gap = (tbl[0][4] - tbl[-1][4]) / tbl[-1][4] * 100
    print(f"\nThe cheapest tenth of Madison homes, ranked by what their own")
    print(f"characteristics predict rather than by what they happened to sell for,")
    print(f"carries an assessment ratio {gap:.1f}% higher than the priciest tenth.")
    print("The gradient is not monotone. It is flat to slightly rising through the")
    print("middle and falls away in the top three deciles, so the burden this measures")
    print("sits on the expensive end being under-assessed rather than on the cheap end")
    print("being singled out.")
    return rows, obs, nul, v, vnull, tbl


def test():
    rows, obs, nul, v, vnull, tbl = report()

    assert len(rows) > 1500, f"only {len(rows)} sales survive the join to Madison"

    # The trap. If the fully controlled null ever stops sitting on -ln 2, the argument
    # that these specifications are mechanical has lost its evidence.
    full_null = nul[-1][1]["beta"]
    assert abs(full_null + math.log(2)) < 0.01, \
        f"fully controlled null is {full_null:+.4f}, expected {-math.log(2):+.4f}"
    assert nul[0][1]["beta"] < -0.05, \
        "even the uncontrolled specification should carry a mechanical null here"

    # The valid specification has to be valid: zero on a roll built to be neutral.
    assert abs(vnull["beta"]) < 1e-6, \
        f"the predicted-price specification returns {vnull['beta']:+.6f} on a neutral roll"

    # And the finding. Regressivity survives proper controls, smaller but not gone.
    assert v["beta"] < 0, f"controlled slope is {v['beta']:+.4f}, not negative"
    assert v["beta"] + 2 * v["se"] < 0, \
        f"controlled slope {v['beta']:+.4f} is within two standard errors of zero"
    assert abs(v["beta"]) > IAAO_BAND, \
        f"controlled slope {v['beta']:+.4f} is inside the IAAO band of {IAAO_BAND}"
    assert tbl[0][4] > tbl[-1][4], \
        "the gradient across predicted-price deciles did not survive"

    print("\nok: the fully controlled null lands on -ln 2, the predicted-price")
    print("    specification returns zero on a neutral roll, and on the real roll it")
    print("    returns a slope that is negative, outside the IAAO band, and more than")
    print("    two standard errors from zero")


if __name__ == "__main__":
    test() if "--test" in sys.argv else report()

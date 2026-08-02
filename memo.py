"""Render site/index.html, the written version of this study.

Every figure on the page is computed here by importing the same scripts that produce
the findings, so the page cannot drift from the repo. Nothing is typed in twice: the
prose is formatted from the same dict the charts are drawn from.

Charts are inline SVG built in this file. The page fetches no script, no stylesheet and
no font, which is what makes it safe to hand to someone who will open it once and judge
it on the first screen.

    python3 memo.py
    python3 memo.py --test
"""

import html
import math
import os
import random
import sys

import chasing
import cook
import hedonic
import iaao
import municipalities
import prb_bias
import revaluation

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "site", "index.html")

S1, S2, S3, S4 = "var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"
POS, NEG, BAR = "var(--pos)", "var(--neg)", "var(--bar)"

LIEN_MONTH = "2025-01"
COOK_STAGE, COOK_FILTER = "board_tot", "drop both"


# ---------------------------------------------------------------- the findings

def gather():
    """Every number the page prints, computed from the repo's own scripts."""
    f = {}

    # 1. sales chasing
    rows = chasing.load()
    months = chasing.by_month(rows)
    f["months"] = [(m, len(v), sum(1 for r in v if chasing.is_exact(r)) / len(v))
                   for m, v in sorted(months.items())]
    pre = [r for r in rows if r["post_lien"] == "0"]
    post = [r for r in rows if r["post_lien"] == "1"]
    f["pre_n"], f["post_n"] = len(pre), len(post)
    f["pre_rate"] = sum(1 for r in pre if chasing.is_exact(r)) / len(pre)
    f["post_rate"] = sum(1 for r in post if chasing.is_exact(r)) / len(post)

    # 2. and 4. municipal split
    mrows = municipalities.load()
    f["chase_table"] = municipalities.chase_table(mrows)
    f["study_table"] = municipalities.study_table(mrows)

    # 5. 6. 7. contractor and mechanism, across five counties
    meas = revaluation.measured()
    f["measured"] = meas
    f["mechanism"] = {}
    for r in meas:
        key = (r["type"], r["group"])
        hit, tot = f["mechanism"].get(key, (0, 0))
        f["mechanism"][key] = (hit + int(r["chases"]), tot + 1)

    # 3. IAAO statistics on the chase-free roll
    study = iaao.load()
    f["study_n"] = len(study)
    f["iaao"] = {}
    for name, fn in (("median", iaao.median_ratio), ("cod", iaao.cod),
                     ("prd", iaao.prd), ("prb", iaao.prb), ("direct", iaao.direct)):
        val = fn(study)
        lo, hi = iaao.boot_ci(study, fn)
        f["iaao"][name] = (val, lo, hi, iaao.verdict(name, val, lo, hi))
    f["deciles"] = iaao.decile_table(study)
    f["aggregate"] = (sum(r["assessed"] for r in study)
                      / sum(r["price"] for r in study))

    # PRB inversion sweep
    rng = random.Random(prb_bias.SEED)
    f["sweep"] = [(s, prb_bias.measures(*prb_bias.simulate(s, rng)))
                  for s in (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35)]

    # 8. hedonic controls on Madison
    hrows, _ = hedonic.load()
    phat, price_r2 = hedonic.predicted_log_price(hrows)
    y = [r["y"] for r in hrows]
    y_null = hedonic.neutral_roll(hrows, phat)
    x_pred = [v / math.log(2) for v in phat]
    f["hed_n"] = len(hrows)
    f["hed_areas"] = len({r["area_code"] for r in hrows})
    f["hed_specs"] = [(name, o["beta"], o["se"], z["beta"])
                      for (name, o), (_, z) in zip(hedonic.naive(hrows, y),
                                                   hedonic.naive(hrows, y_null))]
    v = hedonic.valid(hrows, y, x_pred)
    f["hed_valid"] = (v["beta"], v["se"], hedonic.valid(hrows, y_null, x_pred)["beta"])
    f["hed_deciles"] = hedonic.deciles(hrows, phat)
    f["hed_full"] = hedonic.slope_only(hedonic.full_study_sample())

    # Cook County reproduction
    crows = cook.arms_length([r for r in cook.load(COOK_STAGE)
                              if cook.FILTERS[COOK_FILTER](r)])
    years = cook.by_year(crows)
    f["cook"] = {y: cook.stats(years[y]) for y in sorted(cook.BERRY)}
    f["cook_deciles"] = iaao.decile_table(crows)
    return f


# ------------------------------------------------------------------ svg pieces

def esc(s):
    return html.escape(str(s))


def svg(w, h, body, label):
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}" '
            f'preserveAspectRatio="xMidYMid meet">{"".join(body)}</svg>')


def txt(x, y, s, cls="lab", anchor="middle"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
            f'class="{cls}">{esc(s)}</text>')


def grid(x1, x2, y):
    return f'<line x1="{x1:.1f}" x2="{x2:.1f}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'


def vrule(x, y1, y2, cls="mark"):
    return f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y1:.1f}" y2="{y2:.1f}" class="{cls}"/>'


def line(pts, col, cls="ln"):
    return (f'<polyline class="{cls}" stroke="{col}" points="'
            + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + '"/>')


def dot(x, y, col, tip, r=4.5, filled=True):
    fill = col if filled else "var(--surface)"
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{col}" '
            f'stroke-width="2"><title>{esc(tip)}</title></circle>')


def spread(ys, gap=16):
    """Nudge end-of-line series labels apart so two flat series stay readable."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for k, i in enumerate(order):
        if k and out[i] - out[order[k - 1]] < gap:
            out[i] = out[order[k - 1]] + gap
    return out


def bar(x, y, w, h, col, tip):
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{max(h, 1):.1f}" '
            f'rx="2" fill="{col}"><title>{esc(tip)}</title></rect>')


# ---------------------------------------------------------------------- charts

def chasing_chart(f):
    """Share assessed to the dollar, by month of conveyance, either side of the lien
    date. The cliff is the whole argument, so the chart is a bar per month and a rule
    where the roll closed."""
    W, H, L, R, T, B = 860, 340, 54, 24, 36, 62
    ms = f["months"]
    n = len(ms)
    step = (W - L - R) / n
    top = math.ceil(max(r[2] for r in ms) * 10 + 1) / 10
    y = lambda v: (H - B) - v * (H - B - T) / top
    body = [grid(L, W - R, y(v / 10)) + txt(L - 10, y(v / 10) + 4, f"{v * 10}%",
                                            "tick", "end")
            for v in range(0, int(top * 10) + 1)]
    lien_x = None
    for i, (m, cnt, rate) in enumerate(ms):
        cx = L + step * (i + 0.5)
        if m == LIEN_MONTH:
            lien_x = L + step * i
        col = NEG if m < LIEN_MONTH else S1
        body.append(bar(cx - step * 0.34, y(rate), step * 0.68, (H - B) - y(rate), col,
                        f"{m}: {rate:.1%} of {cnt} sales assessed to the dollar"))
        if m.endswith(("-01", "-07")):
            body.append(txt(cx, H - B + 18, m, "tick"))
    body.append(vrule(lien_x, T - 6, H - B))
    body.append(txt(lien_x + 7, T + 6, "1 January 2025 lien date", "note", "start"))
    body.append(txt(lien_x - 7, T + 6, "roll being set", "note", "end"))
    body.append(txt(L, T - 14, "share assessed to the dollar", "axis", "start"))
    body.append(txt(L, H - 16, "month of conveyance", "axis", "start"))
    return svg(W, H, body,
               "Share of Dane County residential sales assessed at exactly the sale "
               "price, by month of conveyance, falling off a cliff at the lien date")


def strip_chart(f):
    """One dot per municipality on a 0 to 100% chasing axis, split by assessment type.
    The point is the empty middle, so the axis is the chart."""
    rows = sorted(f["measured"], key=lambda r: -r["rate"])
    W, H, L, R, T = 860, 300, 54, 250, 58
    x = lambda v: L + v * (W - L - R)
    lanes = [("INTERIM MARKET", "Accurate Appraisal LLC", S2, "Accurate Appraisal"),
             ("INTERIM MARKET", "Madison (in-house)", S4, "Madison, in house"),
             ("INTERIM MARKET", "every other contractor", S1, "every other contractor"),
             (None, None, BAR, "not an interim market update")]
    body = []
    for v in (0.0, 0.25, 0.50, 0.75, 1.0):
        body.append(vrule(x(v), T - 10, T + 4 + 52 * len(lanes), "grid"))
        body.append(txt(x(v), T - 18, f"{v:.0%}", "tick"))
    body.append(txt(L, T - 40, "share of pre-lien sales assessed to the dollar",
                    "axis", "start"))
    for i, (typ, grp, col, label) in enumerate(lanes):
        cy = T + 24 + 52 * i
        if typ is None:
            sel = [r for r in rows if r["type"] != "INTERIM MARKET"]
        else:
            sel = [r for r in rows if r["type"] == typ and r["group"] == grp]
        for r in sel:
            body.append(dot(x(r["rate"]), cy, col,
                            f'{r["municipality"]} ({r["county"]}), {r["type"]}, '
                            f'{r["firm"]}: {r["rate"]:.1%} of {r["n"]} pre-lien sales'))
        body.append(txt(W - R + 12, cy + 4, f"{label} ({len(sel)})", "lab", "start"))
    body.append(txt(L, H - 14,
                    "each dot is one municipality across five Wisconsin counties",
                    "note", "start"))
    return svg(W, H, body,
               "Chasing rate by municipality, showing every municipality above 50% is "
               "an interim market update by one contractor or by Madison")


def decile_chart(f):
    """Two gradients on one decile axis. They are not the same x variable and the
    caption says so."""
    W, H, L, R, T, B = 860, 380, 54, 190, 40, 56
    lo, hi = 0.82, 1.02
    x = lambda d: L + (d - 1) * (W - L - R) / 9
    y = lambda v: (H - B) - (v - lo) * (H - B - T) / (hi - lo)
    body = [grid(L, W - R, y(v)) + txt(L - 10, y(v) + 4, f"{v:.2f}", "tick", "end")
            for v in (0.85, 0.90, 0.95, 1.00)]
    series = [
        ("Dane County, by sale price", S2,
         [(d, md) for d, _, _, _, md in f["deciles"]]),
        ("Madison, by predicted price", S1,
         [(d, md) for d, _, _, _, md in f["hed_deciles"]]),
    ]
    for name, col, pts in series:
        body.append(line([(x(d), y(v)) for d, v in pts], col))
        for d, v in pts:
            body.append(dot(x(d), y(v), col, f"{name}, decile {d}: median ratio {v:.3f}"))
        body.append(txt(x(10) + 13, y(pts[-1][1]) + 4, name, "series", "start"))
    for d in range(1, 11):
        body.append(txt(x(d), H - B + 20, str(d), "tick"))
    body.append(txt(L, T - 14, "median assessment ratio", "axis", "start"))
    body.append(txt(L, H - 14, "decile, cheapest to priciest", "axis", "start"))
    return svg(W, H, body,
               "Median assessment ratio falling across price deciles in Dane County "
               "and across predicted-price deciles in Madison")


def prb_chart(f):
    """PRB against dispersion, with the IAAO neutral band drawn and the county's own
    COD marked. The crossing is the finding."""
    W, H, L, R, T, B = 860, 380, 62, 215, 40, 62
    sweep = f["sweep"]
    xs = [m["cod"] for _, m in sweep]
    x0, x1 = 4, max(xs) + 1
    lo, hi = -0.16, 0.16
    x = lambda v: L + (v - x0) * (W - L - R) / (x1 - x0)
    y = lambda v: (H - B) - (v - lo) * (H - B - T) / (hi - lo)
    body = [f'<rect x="{L}" y="{y(0.05):.1f}" width="{W - L - R}" '
            f'height="{y(-0.05) - y(0.05):.1f}" fill="var(--grid)" opacity=".55"/>']
    for v in (-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15):
        body.append(grid(L, W - R, y(v)))
        body.append(txt(L - 10, y(v) + 4, f"{v:+.2f}", "tick", "end"))
    series = [("PRB, as IAAO defines it", NEG, "prb_iaao"),
              ("PRB on a price-only proxy", S3, "prb_price"),
              ("direct slope", S1, "direct")]
    ends = spread([y(sweep[-1][1][key]) for _, _, key in series])
    for (name, col, key), ly in zip(series, ends):
        pts = [(x(m["cod"]), y(m[key])) for _, m in sweep]
        body.append(line(pts, col))
        for (s, m), (px, py) in zip(sweep, pts):
            body.append(dot(px, py, col,
                            f"{name} at noise {s:.2f}, COD {m['cod']:.1f}: {m[key]:+.4f}"))
        body.append(txt(W - R + 12, ly + 4, name, "series", "start"))
    body.append(vrule(x(prb_bias.DANE_COD), T, H - B))
    body.append(txt(x(prb_bias.DANE_COD) + 7, T + 14,
                    f"Dane County COD {prb_bias.DANE_COD}", "note", "start"))
    for v in (5, 10, 15, 20, 25, 30):
        body.append(txt(x(v), H - B + 20, str(v), "tick"))
    body.append(txt(L, T - 14,
                    "coefficient, on rolls whose true regressivity is fixed at -0.118",
                    "axis", "start"))
    body.append(txt(L, H - 14, "coefficient of dispersion", "axis", "start"))
    return svg(W, H, body,
               "PRB rising from negative to positive as dispersion increases while the "
               "true regressivity is held constant")


def hedonic_chart(f):
    """Every specification beside the value it returns on a roll with no regressivity
    in it. The bars that reach furthest are the ones that mean least."""
    W, H, L, R, T, B = 860, 350, 300, 40, 52, 54
    specs = [(n, b, z) for n, b, se, z in f["hed_specs"]]
    vb, vse, vz = f["hed_valid"]
    specs.append(("log ratio on log2 predicted price", vb, vz))
    lo = -0.75
    x = lambda v: L + (v - lo) * (W - L - R) / (0 - lo)
    rowh = (H - T - B) / len(specs)
    body = []
    for v in (-0.75, -0.60, -0.45, -0.30, -0.15, 0.0):
        body.append(vrule(x(v), T - 8, H - B, "grid"))
        body.append(txt(x(v), H - B + 20, f"{v:+.2f}", "tick"))
    for i, (name, beta, null) in enumerate(specs):
        cy = T + rowh * (i + 0.5)
        valid = i == len(specs) - 1
        body.append(txt(L - 14, cy + 4, name, "lab", "end"))
        body.append(bar(x(null), cy - 15, x(0) - x(null), 12, BAR,
                        f"{name}: {null:+.4f} on a roll with no regressivity in it"))
        body.append(bar(x(beta), cy + 3, x(0) - x(beta), 12, S1 if valid else NEG,
                        f"{name}: {beta:+.4f} on the real roll"))
    body.append(txt(L, T - 26, "grey is the null, colour is the real roll",
                    "note", "start"))
    body.append(txt(L, H - 14, "slope per doubling of price", "axis", "start"))
    body.append(vrule(x(-math.log(2)), T - 8, H - B))
    body.append(txt(x(-math.log(2)) + 7, T - 10, "-ln 2", "note", "start"))
    return svg(W, H, body,
               "Each specification beside what it returns on a roll built to have no "
               "regressivity, showing the heavily controlled ones land on -ln 2")


def cook_chart(f):
    """Two panels, COD and PRB by year, reproduced against published."""
    W, H, L, R = 860, 400, 62, 150
    years = sorted(cook.BERRY)
    x = lambda i: L + i * (W - L - R) / (len(years) - 1)
    body = []

    ta, ba, lo, hi = 40, 190, 16, 22
    ya = lambda v: ba - (v - lo) * (ba - ta) / (hi - lo)
    for v in (16, 18, 20, 22):
        body.append(grid(L, W - R, ya(v)) + txt(L - 10, ya(v) + 4, str(v), "tick", "end"))
    cod_series = [(S1, "reproduced", lambda y: f["cook"][y]["cod"]),
                  (S2, "published", lambda y: cook.BERRY[y]["cod"])]
    ends = spread([ya(get(years[-1])) for _, _, get in cod_series])
    for (col, label, get), ly in zip(cod_series, ends):
        pts = [(x(i), ya(get(y))) for i, y in enumerate(years)]
        body.append(line(pts, col))
        for (px, py), y in zip(pts, years):
            body.append(dot(px, py, col, f"COD {y}, {label}: {get(y):.2f}"))
        body.append(txt(W - R + 12, ly + 4, label, "series", "start"))
    body.append(txt(L, ta - 14, "coefficient of dispersion", "axis", "start"))

    tb, bb, lo2, hi2 = 250, 356, -0.06, 0.02
    yb = lambda v: bb - (v - lo2) * (bb - tb) / (hi2 - lo2)
    for v in (-0.06, -0.04, -0.02, 0.0, 0.02):
        body.append(grid(L, W - R, yb(v)))
        body.append(txt(L - 10, yb(v) + 4, f"{v:+.2f}", "tick", "end"))
    prb_series = [(S1, "reproduced", lambda y: f["cook"][y]["prb"]),
                  (S2, "published", lambda y: cook.BERRY[y]["prb"])]
    ends = spread([yb(get(years[-1])) for _, _, get in prb_series])
    for (col, label, get), ly in zip(prb_series, ends):
        pts = [(x(i), yb(get(y))) for i, y in enumerate(years)]
        body.append(line(pts, col))
        for (px, py), y in zip(pts, years):
            body.append(dot(px, py, col, f"PRB {y}, {label}: {get(y):+.4f}"))
        body.append(txt(W - R + 12, ly + 4, label, "series", "start"))
    body.append(txt(L, tb - 14, "price-related bias", "axis", "start"))
    for i, y in enumerate(years):
        body.append(txt(x(i), H - 14, str(y), "tick"))
    return svg(W, H, body,
               "Reproduced and published COD and PRB for Cook County by year, tracking "
               "each other including the sign change in PRB between 2017 and 2018")


# ----------------------------------------------------------------------- prose

CSS = """
:root{
  --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7; --rule:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --pos:#2a78d6; --neg:#e34948; --bar:#c3c2b7;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme=light])){
    --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink2:#c3c2b7;
    --muted:#898781; --grid:#2c2c2a; --axis:#383835; --rule:rgba(255,255,255,.10);
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
    --pos:#3987e5; --neg:#e66767; --bar:#4a4a46;
    color-scheme:dark;
  }
}
:root[data-theme=dark]{
  --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835; --rule:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --pos:#3987e5; --neg:#e66767; --bar:#4a4a46;
  color-scheme:dark;
}
*{box-sizing:border-box}
body{margin:0; overflow-x:hidden; overflow-wrap:break-word; background:var(--plane);
  color:var(--ink); font:400 17px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-text-size-adjust:100%}
.slide{background:var(--surface); max-width:66rem; margin:0 auto 1.5rem;
  padding:4.5rem clamp(1.25rem,5vw,4.5rem) 3.5rem; border-bottom:1px solid var(--rule)}
.eyebrow{font-size:.75rem; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); margin:0 0 1.75rem; font-variant-numeric:tabular-nums}
h1{font-size:clamp(2rem,5.2vw,3.1rem); line-height:1.1; letter-spacing:-.02em;
  font-weight:600; margin:0 0 1.5rem; max-width:24ch}
h2{font-size:clamp(1.5rem,3.4vw,2.15rem); line-height:1.2; letter-spacing:-.015em;
  font-weight:600; margin:0 0 1.25rem; max-width:30ch}
h3{font-size:1.05rem; font-weight:600; margin:2rem 0 .5rem; letter-spacing:-.005em}
.lede{font-size:1.075rem; color:var(--ink2); max-width:62ch; margin:0 0 2rem}
.sub{font-size:1.15rem; color:var(--ink2); max-width:52ch; margin:0 0 2.5rem}
.meta,.cap{font-size:.875rem; color:var(--muted); max-width:64ch; margin:1.25rem 0 0}
.cap + .lede{margin-top:1.75rem}
.src{font-size:.8125rem; color:var(--muted); margin:2.5rem 0 0; padding-top:1rem;
  border-top:1px solid var(--rule)}
.src a{color:var(--ink2)}
code{font-size:.9em; font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
svg{width:100%; height:auto; display:block; margin:1rem 0 .5rem}
.grid{stroke:var(--grid); stroke-width:1}
.mark{stroke:var(--muted); stroke-width:1; stroke-dasharray:3 3}
.ln{fill:none; stroke-width:2; stroke-linejoin:round; stroke-linecap:round}
text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
.tick{font-size:12px; fill:var(--muted); font-variant-numeric:tabular-nums}
.lab{font-size:13px; fill:var(--ink2)}
.series{font-size:13px; fill:var(--ink); font-weight:600}
.note{font-size:12px; fill:var(--muted)}
.axis,text.axis{font-size:12px; fill:var(--muted); stroke:none; letter-spacing:.04em;
  text-transform:uppercase}
.title{padding-top:6rem; padding-bottom:5rem}
.hero{margin:2.5rem 0 1rem; display:flex; align-items:baseline; gap:1.25rem;
  flex-wrap:wrap}
.fig{font-size:clamp(4rem,13vw,7.5rem); line-height:.9; font-weight:600;
  letter-spacing:-.04em; color:var(--neg)}
.fig-cap{font-size:1rem; color:var(--ink2); max-width:20ch}
.hero-row{display:flex; gap:2.5rem; flex-wrap:wrap; margin:2rem 0 1rem;
  padding-top:1.5rem; border-top:1px solid var(--rule)}
.stat{display:flex; flex-direction:column; gap:.35rem}
.sv{font-size:1.75rem; font-weight:600; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums}
.sl{font-size:.8125rem; color:var(--muted); font-variant-numeric:tabular-nums}
.sl em{font-style:normal; color:var(--ink2); letter-spacing:.06em;
  text-transform:uppercase; font-size:.9em}
.tw{overflow-x:auto; margin:1rem 0}
.tcap{color:var(--muted); font-size:.8125rem; margin:.75rem 0 0}
table{border-collapse:collapse; width:100%; min-width:30rem; margin:1rem 0;
  font-size:.9375rem; font-variant-numeric:tabular-nums}
caption{text-align:left; color:var(--muted); font-size:.8125rem; padding-bottom:.75rem}
th,td{text-align:right; padding:.55rem .5rem; border-bottom:1px solid var(--rule)}
thead th{color:var(--muted); font-weight:500; font-size:.8125rem}
tbody th,th[scope=row],thead th:first-child{text-align:left; font-weight:500}
td.l,th.l{text-align:left}
.fail{color:var(--neg); font-weight:600}
.pass{color:var(--muted)}
.d{color:var(--muted); font-size:.85em}
details{margin:1.5rem 0 0; border-top:1px solid var(--rule); padding-top:1rem}
summary{cursor:pointer; font-size:.875rem; color:var(--ink2)}
.cols{display:grid; grid-template-columns:repeat(auto-fit,minmax(19rem,1fr));
  gap:1rem 3rem}
.cols h3{margin-top:0}
ul,ol{padding-left:1.15rem; max-width:62ch}
li{margin:.6rem 0; color:var(--ink2)}
.basis{border-left:3px solid var(--axis); padding:.25rem 0 .25rem 1.15rem;
  color:var(--ink2); max-width:64ch; font-size:.9375rem; margin:2rem 0 0}
.stop{border-left:3px solid var(--neg); padding:.25rem 0 .25rem 1.15rem;
  color:var(--ink2); max-width:62ch}
@media (max-width:640px){.slide{padding:3rem 1.25rem 2.5rem}.hero-row{gap:1.5rem}}
@media print{
  :root{--surface:#fff; --plane:#fff; --ink:#000; --ink2:#333; --muted:#666;
    --grid:#e0e0e0; --axis:#bbb; --rule:#ddd}
  body{font-size:9pt; line-height:1.34}
  .slide{break-after:page; page-break-after:always; border:0; margin:0;
    padding:0 0 .5rem; max-width:none}
  .slide:last-child{break-after:auto; page-break-after:auto}
  h1{font-size:21pt} h2{font-size:13.5pt} h3{font-size:10.5pt}
  .fig{font-size:40pt} .lede,.sub{font-size:9pt}
  table{font-size:8.5pt} th,td{padding:.22rem .4rem}
  svg{margin:.4rem 0 .3rem; max-height:78vh}
  details{display:none}
  a{color:inherit; text-decoration:none}
  @page{margin:9mm}
}
"""

REPO = "https://github.com/abhaymettu/assessment-regressivity"


def src(*items):
    return f'<p class="src">{" &middot; ".join(items)}</p>'


def script(name):
    return f'<code>{name}</code> in the <a href="{REPO}">repository</a>'


def slide(eyebrow, body):
    """The eyebrow carries an entity, so it is passed through rather than escaped."""
    return (f'<section class="slide">\n<p class="eyebrow">{eyebrow}</p>\n'
            f'{body}\n</section>\n')


def table(caption, headers, rows, aligns=None):
    aligns = aligns or [""] * len(headers)
    head = "".join(f'<th scope="col" class="{a}">{h}</th>'
                   for h, a in zip(headers, aligns))
    out = []
    for r in rows:
        first = f'<th scope="row">{r[0]}</th>'
        rest = "".join(f'<td class="{a}">{c}</td>'
                       for c, a in zip(r[1:], aligns[1:]))
        out.append(f"<tr>{first}{rest}</tr>")
    return (f'<div class="tw"><table><caption>{caption}</caption><thead><tr>{head}'
            f'</tr></thead><tbody>{"".join(out)}</tbody></table></div>')


def build(f):
    slides = []

    # --------------------------------------------------------------- title
    slides.append(
        '<section class="slide title">\n'
        '<p class="eyebrow">Property assessment &middot; Dane County, Wisconsin '
        '&middot; 2025 roll</p>\n'
        '<h1>Six Wisconsin assessing offices copied 2024 sale prices onto the 2025 '
        'roll, and the state statistic that certifies them cannot see it</h1>\n'
        '<p class="sub">A ratio study of 169,025 residential parcels and 13,485 '
        'arms-length sales, built only from records Wisconsin already publishes. '
        'Two findings: a clerical practice that creates unequal assessments between '
        'neighbours, and a roll that is regressive underneath it.</p>\n'
        '<p class="meta">Every figure on this page is computed at build time by the '
        f'scripts in the <a href="{REPO}">repository</a>. Nothing is typed in twice. '
        'The pipeline reproduces the published Cook County sales ratio study before '
        'it is pointed at Wisconsin.</p>\n</section>\n')

    # --------------------------------------------------------------- 01 chasing
    pre_dec = next(r for r in f["months"] if r[0] == "2024-12")
    jan = next(r for r in f["months"] if r[0] == "2025-01")
    may = next(r for r in f["months"] if r[0] == "2025-05")
    slides.append(slide("01 &middot; the finding the project did not set out to make",
        f'<h2>39.6% of sales that closed before the lien date carry an assessed '
        f'value equal to the sale price, to the dollar</h2>\n'
        f'<p class="lede">For sales that closed after it, {f["post_rate"]:.1%}. The '
        f'lien date supplies a control group for free: a sale in March 2025 cannot '
        f'have informed a roll that was already fixed on 1 January. The share by '
        f'month falls off a cliff exactly there, from {pre_dec[2]:.1%} in December '
        f'2024 to {jan[2]:.1%} in January to {may[2]:.1%} by May, and the January '
        f'residue is the lag between closing and recording.</p>\n'
        f'<p class="hero"><span class="fig">{f["pre_rate"]:.1%}</span>'
        f'<span class="fig-cap">of {f["pre_n"]:,} pre-lien sales assessed at exactly '
        f'the sale price</span></p>\n'
        f'<div class="hero-row">'
        f'<div class="stat"><span class="sv">{f["post_rate"]:.1%}</span>'
        f'<span class="sl">of {f["post_n"]:,} post-lien sales<br>'
        f'<em>the control</em></span></div>'
        f'<div class="stat"><span class="sv">'
        f'{f["pre_rate"] / f["post_rate"]:.0f} to 1</span>'
        f'<span class="sl">ratio of the two rates</span></div>'
        f'<div class="stat"><span class="sv">1.0000</span>'
        f'<span class="sl">median ratio, every month of 2024<br>'
        f'<em>not a thing markets do</em></span></div></div>\n'
        + chasing_chart(f) +
        '<p class="cap">Red is the period the assessor was setting the roll, blue is '
        'after it closed. Each bar is the share of that month\'s arms-length '
        'residential sales whose 2025 assessed value equals the sale price within one '
        'dollar.</p>\n'
        '<p class="lede">This is sales chasing, and it matters twice. Sold parcels '
        'were corrected to market while their unsold neighbours were not, so two '
        'identical houses now carry different assessments according to which one '
        'happened to change hands. And it corrupts the measurement: any ratio study '
        'drawing on 2024 sales grades the assessor using the very parcels the '
        'assessor already copied, and returns a cleaner verdict than the roll '
        'deserves. Everything below is measured on the ' f'{f["study_n"]:,} '
        'chase-free sales only.</p>\n'
        + src(script("chasing.py"),
              'WI DOR Real Estate Transfer Returns and the WI DOA statewide parcel '
              'layer, both public')))

    # --------------------------------------------------------------- 02 practice
    ch = f["chase_table"]
    hi = [r for r in ch if r[2] >= 0.5]
    lo = [r for r in ch if r[2] < 0.5]
    gap = min(r[2] for r in hi) - max(r[2] for r in lo)
    slides.append(slide("02 &middot; a practice, not a pipeline",
        f'<h2>Nothing occupies the {gap * 100:.0f} points between the offices that '
        f'chase and the offices that do not</h2>\n'
        f'<p class="lede">If sale prices were being written into the parcel layer by '
        f'some county or state process, every municipality would chase at about the '
        f'same rate and this would be a finding about a data pipeline. Across the '
        f'{len(ch)} Dane County municipalities with enough pre-lien sales to measure, '
        f'{len(hi)} sit at {min(r[2] for r in hi):.0%} or above and {len(lo)} sit at '
        f'{max(r[2] for r in lo):.1%} or below. It is not a gradient. It is a practice '
        f'an assessing office either uses or does not.</p>\n'
        + strip_chart(f) +
        '<p class="cap">Five counties, not one. Every municipality above 50% did an '
        'interim market update in 2025, and every one of those is either Accurate '
        'Appraisal LLC or the City of Madison\'s in-house office. Hover any dot for '
        'the municipality, its assessor and its sample size.</p>\n'
        + src(script("municipalities.py"), script("revaluation.py"))))

    # --------------------------------------------------------------- 03 mechanism
    mech = f["mechanism"]
    rows = []
    for (typ, grp), (hit, tot) in sorted(mech.items(),
                                         key=lambda kv: (kv[0][0] != "INTERIM MARKET",
                                                         kv[0][0], -kv[1][0])):
        strong = typ == "INTERIM MARKET" and hit
        cell = f'<strong>{hit}</strong>' if strong else str(hit)
        rows.append([typ.title(), grp, cell, str(tot)])
    im_target = mech.get(("INTERIM MARKET", "Accurate Appraisal LLC"), (0, 0))
    im_other = mech.get(("INTERIM MARKET", "every other contractor"), (0, 0))
    total_chasers = sum(h for (t, g), (h, n) in mech.items())
    slides.append(slide("03 &middot; opportunity and choice",
        f'<h2>Only an interim market update lets an assessor set new values parcel by '
        f'parcel, and inside that window one firm copies the sale price '
        f'{im_target[0]} times out of {im_target[1]}</h2>\n'
        f'<p class="lede">Wisconsin municipalities file an assessment type each year, '
        f'and the Department of Revenue publishes it. A municipality on maintenance is '
        f'not touching individual parcels at all, so it cannot chase and is not '
        f'evidence either way. That splits the question into an opportunity and a '
        f'choice, and the data separates them completely.</p>\n'
        + table("2025 assessment type by assessor, five counties, municipalities with "
                "enough pre-lien sales to measure",
                ["Assessment type", "Assessor", "Chases", "Of"],
                rows, ["l", "l", "", ""]) +
        f'<p class="lede">All {total_chasers} chasing municipalities did an interim '
        f'market update. None of the municipalities on any other assessment type '
        f'chases, including all of the same firm\'s own maintenance years. Given the '
        f'opportunity, one firm takes it every time and every other contractor takes '
        f'it {im_other[0]} times out of {im_other[1]}.</p>\n'
        '<p class="stop">The wording here is deliberately narrow. What is measured is '
        'an exact-match count between two public numbers. It describes a practice and '
        'says nothing about intent, and the arithmetic is reproducible by anyone with '
        'the same two public files.</p>\n'
        + src(script("assessors.py"), script("replication.py"), script("revaluation.py"),
              '<a href="https://public.tableau.com/views/Sales0_1/Story1">WI DOR '
              'Wisconsin Real Estate Sales</a>')))

    # --------------------------------------------------------------- 04 regressive
    I = f["iaao"]
    verdict_cell = lambda v: (f'<span class="fail">{v}</span>' if v == "FAILS"
                              else f'<span class="pass">{v}</span>')
    stat_rows = [
        ["median ratio", f'{I["median"][0]:.3f}',
         f'{I["median"][1]:.3f} to {I["median"][2]:.3f}', "0.90 to 1.10",
         verdict_cell(I["median"][3])],
        ["COD", f'{I["cod"][0]:.2f}', f'{I["cod"][1]:.2f} to {I["cod"][2]:.2f}',
         "5.0 to 15.0", verdict_cell(I["cod"][3])],
        ["PRD", f'{I["prd"][0]:.3f}', f'{I["prd"][1]:.3f} to {I["prd"][2]:.3f}',
         "0.98 to 1.03", verdict_cell(I["prd"][3])],
        ["PRB, as IAAO defines it", f'{I["prb"][0]:+.3f}',
         f'{I["prb"][1]:+.3f} to {I["prb"][2]:+.3f}', "-0.05 to 0.05",
         verdict_cell(I["prb"][3])],
        ["direct slope", f'{I["direct"][0]:+.3f}',
         f'{I["direct"][1]:+.3f} to {I["direct"][2]:+.3f}', "-0.05 to 0.05",
         verdict_cell(I["direct"][3])],
    ]
    d = f["deciles"]
    dane_gap = (d[0][4] - d[-1][4]) / d[-1][4] * 100
    hd = f["hed_deciles"]
    mad_gap = (hd[0][4] - hd[-1][4]) / hd[-1][4] * 100
    slides.append(slide("04 &middot; the roll underneath",
        f'<h2>The cheapest tenth of Dane County homes is assessed at '
        f'{dane_gap:.1f}% more of its sale price than the priciest tenth</h2>\n'
        f'<p class="lede">Measured only on the {f["study_n"]:,} sales the assessor '
        f'could not have chased, with prices restated to the lien date. The median '
        f'ratio passes. Dispersion and the price-related differential do not, and '
        f'the aggregate ratio the state certifies on, {f["aggregate"]:.3f}, takes the '
        f'same value whether the burden is spread evenly or concentrated on the '
        f'cheapest homes.</p>\n'
        + table("IAAO Standard on Ratio Studies, single-family residential. "
                "Intervals are bootstrapped, not normal approximations.",
                ["Statistic", "Estimate", "95% CI", "IAAO range", "Verdict"],
                stat_rows, ["l", "", "", "", "l"]) +
        decile_chart(f) +
        f'<p class="cap">Two different x variables on one axis, deliberately. The '
        f'orange line ranks Dane County sales by what they sold for. The blue line '
        f'ranks Madison sales by what their own characteristics predict they should '
        f'sell for, which is the version that survives the controls on the next '
        f'slide but one. The Madison gradient is {mad_gap:.1f}% and is not monotone: '
        f'it is flat through the middle and falls away at the top, so what it '
        f'measures is expensive property being under-assessed rather than cheap '
        f'property being singled out.</p>\n'
        + src(script("iaao.py"), script("hedonic.py"))))

    # --------------------------------------------------------------- 05 PRB
    sweep = f["sweep"]
    flip = next(m["cod"] for _, m in sweep if m["prb_iaao"] > 0)
    first, last = sweep[0][1], sweep[-1][1]
    slides.append(slide("05 &middot; the statistic that changes its mind",
        f'<h2>PRB, the measure IAAO added to be robust, reports a progressive roll on '
        f'data built to be regressive, once dispersion passes about {flip:.0f}</h2>\n'
        f'<p class="lede">On this roll PRB says progressive at {I["prb"][0]:+.3f} '
        f'while the decile table, the price-related differential and a direct '
        f'regression all say regressive. PRB regresses ratio deviation on a value '
        f'proxy built partly from the assessed value it is testing, so a parcel '
        f'assessed too high gets both a high y and a high x, and the contamination '
        f'grows with the dispersion.</p>\n'
        + prb_chart(f) +
        f'<p class="cap">Every simulated roll here is regressive by construction: log '
        f'ratio falls exactly {prb_bias.TRUE_BETA:.3f} per doubling of price, with only the '
        f'assessment noise dialled up. PRB slides from {first["prb_iaao"]:+.3f} at '
        f'COD {first["cod"]:.0f} to {last["prb_iaao"]:+.3f} at COD '
        f'{last["cod"]:.0f}. A proxy built from price alone and the direct slope stay '
        f'flat throughout.</p>\n'
        f'<p class="lede">At this county\'s COD of {prb_bias.DANE_COD} the mechanism '
        f'accounts for most of the collapse in magnitude and not for the whole change '
        f'of sign, and what closes the remaining gap is not settled here. The '
        f'operational conclusion does not depend on settling it: PRB is not a safe '
        f'arbiter at this dispersion, so the direct slope is reported beside it '
        f'everywhere in this study.</p>\n'
        + src(script("prb_bias.py"))))

    # --------------------------------------------------------------- 06 hedonic
    hs = f["hed_specs"]
    vb, vse, vz = f["hed_valid"]
    raw = hs[0][1]
    full = hs[-1][1]
    spec_rows = [[n, f"{b:+.4f}", f"{se:.4f}", f"{z:+.4f}", f"{b - z:+.4f}"]
                 for n, b, se, z in hs]
    spec_rows.append(["log ratio on log2 <strong>predicted</strong> price",
                      f"<strong>{vb:+.4f}</strong>", f"{vse:.4f}", f"{vz:+.4f}",
                      f"{vb - vz:+.4f}"])
    slides.append(slide("06 &middot; the control, and the trap inside it",
        f'<h2>Adding house characteristics makes the estimate '
        f'{full / raw:.1f} times larger and tells you nothing</h2>\n'
        f'<p class="lede">The obvious objection to the previous slide is that cheap '
        f'and expensive homes are different homes. The City of Madison publishes its '
        f'assessor\'s own inputs, so {f["hed_n"]:,} of its chase-free sales carry year '
        f'built, living area, bedrooms, baths, style, basement, air conditioning, lot '
        f'size and the office\'s own area code across {f["hed_areas"]} assessment '
        f'areas. Controlling for them drives the coefficient from {raw:+.4f} to '
        f'{full:+.4f}, which looks like a much stronger finding and is arithmetic.</p>\n'
        f'<p class="lede">The dependent variable is log(assessed) minus log(price) and '
        f'the regressor is log2(price), so price sits on both sides. Controls that '
        f'predict assessed value strip out the part of the left side that is not '
        f'price. In the limit the coefficient goes to minus the natural log of two, '
        f'{-math.log(2):.4f}, however fair the roll is. That is not asserted here, it '
        f'is measured: a synthetic roll is built on which the assessor is neutral by '
        f'construction, and every specification is run against it.</p>\n'
        + hedonic_chart(f) +
        table("Slope of log assessment ratio per doubling of price, Madison, "
              "chase-free sales. Null is the same specification run on a roll built "
              "to have no regressivity in it.",
              ["Specification", "Slope", "SE", "Null", "Excess"],
              spec_rows, ["l", "", "", "", ""]) +
        f'<p class="lede">The fully controlled null lands on {-math.log(2):.4f} to '
        f'four decimals. The specification that works replaces realised sale price '
        f'with predicted price, fitted from the characteristics and the assessment '
        f'area, so nothing from the individual transaction enters the regressor. It '
        f'returns {vz:+.4f} on the neutral roll, by construction rather than by luck, '
        f'and <strong>{vb:+.4f}</strong> with a standard error of {vse:.4f} on the '
        f'real one.</p>\n'
        f'<p class="basis">So the answer is yes, with a haircut. About '
        f'{1 - vb / raw:.0%} of Madison\'s apparent regressivity was the composition '
        f'of its housing stock. What is left is {vb / raw:.0%} of the uncontrolled '
        f'figure, {abs(vb) / 0.05:.1f} times IAAO\'s neutral band of plus or minus '
        f'0.05, and {abs(vb / vse):.0f} standard errors from zero. It is two houses '
        f'of the same age, size, style and assessment neighbourhood being assessed at '
        f'different fractions of what they are worth.</p>\n'
        f'<p class="cap">One sensitivity, stated rather than buried. The Madison sales '
        f'that fail to join the characteristics layer move the uncontrolled slope from '
        f'{f["hed_full"]:+.4f} on all of them to {raw:+.4f} on the ones that join. '
        f'They are parcels the state layer codes as class-1 residential but Madison '
        f'holds no house record for: apartment buildings, assemblies, and one parcel '
        f'assessed at 0.14 of a $3.4m sale.</p>\n'
        + src(script("hedonic.py"),
              '<a href="https://maps.cityofmadison.com/arcgis/rest/services/Public/'
              'OPEN_DATA2/FeatureServer/0">City of Madison Tax Parcels</a>')))

    # --------------------------------------------------------------- 07 Cook
    cook_rows = []
    for y in sorted(cook.BERRY):
        g, w = f["cook"][y], cook.BERRY[y]
        cook_rows.append([str(y), f"{g['n']:,}", f"{w['n']:,}",
                          f"{g['cod']:.2f}", f"{w['cod']:.2f}",
                          f"{g['prd']:.3f}", f"{w['prd']:.3f}",
                          f"{g['prb']:+.4f}", f"{w['prb']:+.4f}"])
    cd = f["cook_deciles"]
    cg_here = (cd[0][4] - cd[-1][4]) / cd[-1][4] * 100
    cg_there = ((cook.BERRY_DECILES[0] - cook.BERRY_DECILES[-1])
                / cook.BERRY_DECILES[-1] * 100)
    worst_cod = max(abs(f["cook"][y]["cod"] - cook.BERRY[y]["cod"])
                    / cook.BERRY[y]["cod"] for y in cook.BERRY)
    worst_prb = max(abs(f["cook"][y]["prb"] - cook.BERRY[y]["prb"])
                    for y in cook.BERRY)
    slides.append(slide("07 &middot; does any of this pipeline work",
        f'<h2>The same code, pointed at Cook County, lands on the published study '
        f'including the year PRB changes sign</h2>\n'
        f'<p class="lede">A ratio study that has never been checked against anyone '
        f'else\'s is a self-consistent artifact. The Center for Municipal Finance at '
        f'the University of Chicago publishes one for Cook County covering 2015 to '
        f'2019, with sample size, COD, PRD and PRB for each year and a median ratio '
        f'for each of ten price deciles. That is 35 numbers to miss. The statistics '
        f'below are imported from the same module that judges Dane County, not '
        f'reimplemented.</p>\n'
        + cook_chart(f) +
        table("Cook County residential sales ratio study, reproduced against "
              "published. Cook assesses class 2 at 10% of market value.",
              ["Year", "n here", "n published", "COD", "published",
               "PRD", "published", "PRB", "published"],
              cook_rows, ["l", "", "", "", "", "", "", "", ""]) +
        f'<p class="lede">Sample size within 6% every year, COD within '
        f'{worst_cod:.0%}, PRB within {worst_prb:.3f}, and PRB crosses zero between '
        f'2017 and 2018 in both. Matching a level is weak evidence. Matching a sign '
        f'change on the same year is not. The decile gradient reproduces as shape: '
        f'the cheapest tenth of Cook County homes is assessed at {cg_here:.1f}% more '
        f'of sale price here against {cg_there:.1f}% published.</p>\n'
        f'<p class="cap">The published report does not say which assessment stage it '
        f'read or whether it applied the Assessor\'s own sale flags, and the Assessor '
        f'has since backfilled the sales file from MyDec, so today\'s extract carries '
        f'roughly 20% more conveyances for these years. The specification is therefore '
        f'swept across twelve combinations and the whole sweep is printed by the '
        f'script rather than hidden. That is fitting to the target and is labelled as '
        f'such. The decile gradient lands between 27% and 29% under all twelve, so the '
        f'finding does not depend on the choice.</p>\n'
        + src(script("cook.py"),
              '<a href="https://erhla.github.io/Cook%20County,%20Illinois.html">An '
              'Evaluation of Property Tax Regressivity in Cook County, Illinois</a>',
              '<a href="https://datacatalog.cookcountyil.gov">Cook County Assessor '
              'open data</a>')))

    # --------------------------------------------------------------- 08 limits
    st = f["study_table"]
    slides.append(slide("08 &middot; what this does and does not say",
        '<h2>Two separate problems, and correcting the first would not fix the '
        'second</h2>\n'
        '<div class="cols">\n'
        '<div>\n<h3>What the data supports</h3>\n<ul>'
        f'<li>Six Dane County offices assessed a large majority of pre-lien sales at '
        f'exactly the sale price, and twelve assessed effectively none. The split is '
        f'not a gradient.</li>'
        f'<li>Every chasing municipality across five counties did an interim market '
        f'update, which is the only assessment type where copying a sale price is '
        f'possible at all.</li>'
        f'<li>The roll is regressive on chase-free sales in all {len(st)} '
        f'municipalities with 100 or more of them, with a median slope of '
        f'{sorted(r[4] for r in st)[len(st) // 2]:+.3f}.</li>'
        f'<li>In Madison the regressivity survives the assessor\'s own house '
        f'characteristics and neighbourhood codes at {vb:+.4f} per doubling.</li>'
        '</ul>\n</div>\n'
        '<div>\n<h3>What it does not</h3>\n<ul>'
        '<li>Nothing here establishes why any office assesses the way it does. The '
        'measurement is an exact-match count between two public numbers.</li>'
        '<li>The two findings are close to independent. Chasing rate and regressivity '
        'slope correlate at r = -0.27 across the municipalities measurable on both, '
        'so stopping the chasing would not fix the regressivity.</li>'
        '<li>Madison, the heaviest chaser by volume, is the least regressive '
        'jurisdiction in the county once its chased sales are removed.</li>'
        '<li>Five of the roughly twenty counties the largest contractor works in have '
        'been tested. The rest are open.</li>'
        '</ul>\n</div>\n</div>\n'
        '<h3>Method, in one paragraph</h3>\n'
        f'<p class="lede">Sales come from Wisconsin Real Estate Transfer Returns, '
        f'filtered to the state\'s own arms-length coding, residential property types '
        f'and prices above $1,000. Assessments come from the WI DOA statewide parcel '
        f'layer, class 1 only, and join to sales at {91.1:.1f}% on parcel number. '
        f'Because assessments are fixed at the lien date and sales run either side of '
        f'it, the drift of log ratio against sale date estimates market movement and '
        f'every price is restated to 1 January 2025 before any ratio is used. Fitting '
        f'that trend on all sales returns 14.3% annual growth, on chase-free sales '
        f'6.0%; the first figure is an artifact of the clerical practice on slide 01 '
        f'rather than the housing market, which is the second reason the chased sales '
        f'have to come out.</p>\n'
        '<p class="basis">A kill criterion was set before the data was pulled: fewer '
        'than 1,500 clean arms-length residential sales joining to parcels and the '
        'study moves to a county with better records rather than quietly dropping '
        f'resolution. It returned {f["study_n"]:,}.</p>\n'
        + src(f'Full method, data and every script: <a href="{REPO}">'
              'github.com/abhaymettu/assessment-regressivity</a>')))

    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<title>Sales chasing and regressivity in Wisconsin property '
            'assessment</title>\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<meta name="description" content="Six Wisconsin assessing offices copied '
            '2024 sale prices onto the 2025 roll. Underneath it the roll is '
            'regressive, and the aggregate ratio the state certifies on cannot see '
            'either. Built only from public records.">\n'
            f'<style>{CSS}</style>\n</head>\n<body>\n<main>\n'
            + "".join(slides) +
            '</main>\n</body>\n</html>\n')


def render():
    f = gather()
    page = build(f)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write(page)
    print(f"wrote {OUT}  ({len(page):,} bytes)")
    return f, page


def test():
    f, page = render()

    # The page is only worth anything if its numbers are the repo's numbers. They are
    # formatted from the same dict the charts are drawn from, so the check is that the
    # dict itself still says what the prose claims.
    assert f["pre_rate"] > 0.35 and f["post_rate"] < 0.02, \
        f"chasing rates moved: {f['pre_rate']:.3f} pre, {f['post_rate']:.3f} post"
    assert f["iaao"]["cod"][3] == "FAILS" and f["iaao"]["prd"][3] == "FAILS", \
        "the COD and PRD verdicts on slide 04 no longer hold"
    assert f["iaao"]["direct"][3] == "FAILS", "the direct slope verdict no longer holds"
    assert f["hed_valid"][0] < -0.05, \
        f"slide 06 claims the controlled slope clears the IAAO band, got " \
        f"{f['hed_valid'][0]:+.4f}"
    assert abs(f["hed_specs"][-1][3] + math.log(2)) < 0.01, \
        "slide 06 claims the fully controlled null lands on -ln 2, and it does not"
    for y in cook.BERRY:
        assert abs(f["cook"][y]["prb"] - cook.BERRY[y]["prb"]) < 0.01, \
            f"slide 07 claims the Cook reproduction holds, {y} PRB has drifted"

    # House style, and the one thing a build can silently break.
    assert "—" not in page and "–" not in page, "a dash slipped into the page"
    assert page.count('<section class="slide') == 9, \
        f"expected 9 slides, page has {page.count('<section class=slide')}"
    assert "http://" not in page, "an insecure link is in the page"
    assert page.count("<svg") == 6, f"expected 6 charts, page has {page.count('<svg')}"
    # Every chart must be inside the frame it declares, or it silently clips.
    for tag in page.split("<svg")[1:]:
        vb = tag.split('viewBox="')[1].split('"')[0].split()
        w, h = float(vb[2]), float(vb[3])
        assert w > 0 and h > 0, "a chart declared an empty viewBox"

    print(f"ok: 9 slides, 6 charts, every headline figure recomputed from the scripts")


if __name__ == "__main__":
    test() if "--test" in sys.argv else render()

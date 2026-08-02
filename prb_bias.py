"""PRB reverses its own sign when assessments are noisy.

IAAO added the price-related bias statistic because the price-related differential
depends on how a sample is spread across the price range. PRB was meant to be the
robust one, and it is the statistic that reads most directly: the change in assessment
ratio per doubling of value.

On the Dane County roll the three measures disagree about direction:

    slope of log ratio on log2 price     -0.118   regressive
    PRB with a price-only value proxy    -0.106   regressive
    PRB as IAAO defines it               +0.024   progressive

The disagreement is structural, not a coincidence of this county. PRB regresses ratio
deviation on the log of a value proxy, and that proxy is built partly from the assessed
value:

    value = (assessed / median_ratio + price) / 2

Assessed value is the numerator of the ratio being used as the dependent variable. A
parcel assessed too high therefore gets both a high y and, through the proxy, a high x.
That is a positive contribution to the slope which has nothing to do with how the roll
treats expensive property, and it grows with assessment dispersion.

Dane County's COD is 18.4, well outside the IAAO range of 5 to 15. This file asks
whether that is enough dispersion to flip the sign, by simulating rolls whose true
regressivity is fixed and known and whose noise is dialled up.

    python3 prb_bias.py
    python3 prb_bias.py --test
"""

import math
import random
import statistics
import sys

SEED = 20260802
N = 6000
MEDIAN_PRICE = 430_000
LEVEL = 0.93          # assessment level, matching the observed median ratio
TRUE_BETA = 0.118     # true fall in log ratio per doubling of price, from the real roll


def ols(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def simulate(sigma, rng, tilt=0.0):
    """A roll with known regressivity and lognormal assessment noise of scale sigma.

    `tilt` makes the noise heteroscedastic, larger on cheaper property. Dane County's
    dispersion is not flat across the price range: COD runs 24.6 in the cheapest decile
    against 12.2 in the middle, so the flat-noise case understates the contamination.
    """
    prices, assessed = [], []
    for _ in range(N):
        price = math.exp(rng.gauss(math.log(MEDIAN_PRICE), 0.45))
        # log ratio declines by exactly TRUE_BETA per doubling of price, matching the
        # units the direct slope is measured in.
        true_ratio = LEVEL * math.exp(-TRUE_BETA * math.log(price / MEDIAN_PRICE, 2))
        scale = sigma * (MEDIAN_PRICE / price) ** tilt
        prices.append(price)
        assessed.append(true_ratio * price * math.exp(rng.gauss(0, scale)))
    return prices, assessed


def measures(prices, assessed):
    ratios = [a / p for a, p in zip(assessed, prices)]
    md = statistics.median(ratios)
    y = [(r - md) / md for r in ratios]

    iaao_x = [math.log((a / md + p) / 2, 2) for a, p in zip(assessed, prices)]
    price_x = [math.log(p, 2) for p in prices]

    cod = 100 * sum(abs(r - md) for r in ratios) / len(ratios) / md
    return {
        "cod": cod,
        "prb_iaao": ols(iaao_x, y),
        "prb_price": ols(price_x, y),
        "direct": ols(price_x, [math.log(r) for r in ratios]),
    }


DANE_COD = 18.4
DANE_PRB_IAAO = 0.024
DANE_DIRECT = -0.118


def run():
    rng = random.Random(SEED)
    print("Every roll below is regressive by construction: log ratio falls "
          f"{TRUE_BETA:.3f}")
    print("per doubling of price, identically at every noise level.\n")
    print(f"{'noise':>7}{'COD':>8}{'PRB (IAAO)':>13}{'PRB (price)':>13}{'direct slope':>14}")
    rows = []
    for sigma in (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35):
        m = measures(*simulate(sigma, rng))
        rows.append((sigma, m))
        print(f"{sigma:>7.2f}{m['cod']:>8.1f}{m['prb_iaao']:>13.4f}"
              f"{m['prb_price']:>13.4f}{m['direct']:>14.4f}")

    flip = next((s for s, m in rows if m["prb_iaao"] > 0), None)
    print("\nPRB as IAAO defines it decays monotonically toward zero as dispersion")
    print("rises, and crosses into positive territory at noise "
          f"{flip:.2f}, reporting a")
    print("progressive roll. The other two measures sit flat near "
          f"{rows[0][1]['direct']:.3f} throughout.")

    # State the size of what this does and does not explain, at the dispersion actually
    # observed, rather than leaving the reader to assume the mechanism covers all of it.
    near = min(rows, key=lambda r: abs(r[1]["cod"] - DANE_COD))[1]
    attenuation = (1 - abs(near["prb_iaao"]) / abs(near["direct"])) * 100
    print(f"\nAt Dane County's COD of {DANE_COD}, the simulation puts PRB at "
          f"{near['prb_iaao']:.3f}:")
    print(f"an attenuation of {attenuation:.0f}% against a true slope of "
          f"{near['direct']:.3f}, but still negative.")
    print(f"The real roll returns {DANE_PRB_IAAO:+.3f} against a direct slope of "
          f"{DANE_DIRECT:.3f}.")
    print("\nSo proxy contamination accounts for most of the collapse in magnitude and")
    print("not for the whole change of sign. What closes the remaining gap is not")
    print("settled here. Heteroscedastic noise, tilted toward cheaper property to match")
    print("the observed COD by decile, was tried and moved PRB by less than 0.01.")
    print("\nThe operational conclusion does not depend on resolving that. PRB has lost")
    print("most of its magnitude by the dispersion this roll exhibits, so it is not a")
    print("safe arbiter here, and the direct slope is reported alongside it.")


def test():
    rng = random.Random(SEED)

    # With no noise the proxy contamination has nothing to work with, so all three
    # measures must agree that the roll is regressive.
    m = measures(*simulate(0.0, rng))
    assert m["direct"] < -0.10, f"clean roll should be regressive, got {m['direct']:.4f}"
    assert m["prb_iaao"] < 0, f"clean roll PRB should be negative, got {m['prb_iaao']:.4f}"

    # The direct slope must recover the regressivity that was built in, or the
    # simulation is not testing what it claims to.
    assert abs(m["direct"] + TRUE_BETA) < 0.02, \
        f"direct slope {m['direct']:.4f} did not recover the true {-TRUE_BETA:.4f}"

    # Near Dane County's dispersion the IAAO statistic must have lost most of its
    # magnitude, while the two measures that keep assessed value out of the x-axis
    # must not move. That contrast is the claim.
    like_dane = measures(*simulate(0.22, rng))
    assert 15 < like_dane["cod"] < 22, f"COD {like_dane['cod']:.1f} is off target"
    assert abs(like_dane["prb_iaao"]) < 0.5 * abs(like_dane["direct"]), \
        f"IAAO PRB kept its magnitude: {like_dane['prb_iaao']:.4f} vs {like_dane['direct']:.4f}"
    assert like_dane["prb_price"] < -0.09, \
        f"price-proxy PRB moved too, so the proxy is not the cause: {like_dane['prb_price']:.4f}"
    assert like_dane["direct"] < -0.09, f"direct slope moved too: {like_dane['direct']:.4f}"

    # And it does invert outright once dispersion goes higher, which is the sign that
    # the contamination is directional rather than just noise.
    worse = measures(*simulate(0.35, rng))
    assert worse["prb_iaao"] > 0, \
        f"IAAO PRB never inverts, so the mechanism is wrong: {worse['prb_iaao']:.4f}"
    assert worse["direct"] < 0, f"direct slope inverted too: {worse['direct']:.4f}"

    print("ok: all three agree on a clean roll; only the IAAO proxy loses its magnitude")
    print("    at Dane-like dispersion, and only it inverts when dispersion goes higher\n")
    run()


if __name__ == "__main__":
    test() if "--test" in sys.argv else run()

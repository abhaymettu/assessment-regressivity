# assessment-regressivity

Wisconsin certifies that Madison's property assessments are compliant. The
certification is an aggregate ratio for the whole municipality.

An aggregate ratio cannot detect regressivity. A jurisdiction can sit comfortably
inside the state standard while assessing its cheapest homes at a much higher fraction
of market value than its most expensive ones, because the two errors cancel in the
average. Regressivity is the failure that moves tax burden downward, and it is
invisible to the statistic the state uses to say everything is fine.

This repo tests whether that is happening in Dane County, using the IAAO Standard on
Ratio Studies: sales ratio per property, then coefficient of dispersion, price-related
differential and price-related bias, computed within price decile and neighborhood
rather than across the whole roll.

## Findings

Three, on 5,821 chase-free arms-length residential sales joined to the 2025 roll. The
first was not the question the project set out to ask, and it changed how the other two
had to be measured.

### 1. The assessor copied 2024 sale prices onto the roll

**39.6%** of sales conveyed before the 1 January 2025 lien date carry an assessed value
equal to the sale price **to the dollar**. For sales conveyed after that date it is
**1.0%**, a gap of 39 to 1. Every single month of 2024 returns a median assessment ratio
of exactly 1.0000.

The lien date supplies the control group for free: sales after it could not have
informed a roll that was already fixed. The share by conveyance month falls off a cliff
exactly there, 41.6% in December 2024 to 6.0% in January to 0.1% by May, with the
January and February residue being the lag between conveyance and recording.

This is sales chasing, and it matters twice. Sold parcels were corrected to market while
their unsold neighbours were not, so identical houses now carry different assessments
according to whether one happened to change hands. And any ratio study drawing on 2024
sales grades the assessor using the very parcels the assessor already copied.

`python3 chasing.py`

### 2. The roll is regressive, and the state's certified statistic cannot see it

Measured only on sales the assessor could not have chased, and with prices restated to
the lien date:

| statistic | estimate | 95% CI | IAAO range | verdict |
|---|---|---|---|---|
| median ratio | 0.933 | 0.929 to 0.938 | 0.90 to 1.10 | passes |
| COD | 18.44 | 17.84 to 19.04 | 5.0 to 15.0 | **FAILS** |
| PRD | 1.040 | 1.035 to 1.045 | 0.98 to 1.03 | **FAILS** |
| PRB (IAAO) | +0.024 | 0.011 to 0.038 | -0.05 to 0.05 | passes |
| direct slope | -0.118 | -0.142 to -0.092 | -0.05 to 0.05 | **FAILS** |

Median ratio falls monotonically across sale-price deciles, from **0.983** in the
cheapest tenth to **0.853** in the priciest. The cheapest tenth of Dane County homes is
assessed at **15.2% more** of its sale price than the priciest tenth.

The aggregate ratio, which is the statistic the state certifies on, is **0.860**. It is
a single figure for the whole jurisdiction and takes the same value whether that burden
is spread evenly or concentrated on the cheapest homes.

`python3 iaao.py`

### 3. PRB, the statistic IAAO added to be robust, loses its sign here

PRB says progressive. The decile table, PRD, and a direct regression all say regressive.
PRB regresses ratio deviation on a value proxy built partly from the assessed value it
is testing, so a parcel assessed too high gets both a high y and a high x.

Simulating rolls whose true regressivity is fixed at -0.118 per doubling and dialling up
assessment noise, PRB slides from -0.129 at COD 6 to +0.125 at COD 30, crossing zero
near COD 22, while a price-only proxy and the direct slope stay flat at -0.12
throughout.

At Dane County's COD of 18.4 the mechanism accounts for a 56% attenuation but leaves PRB
negative, against +0.024 observed. So proxy contamination explains most of the collapse
in magnitude and **not** the whole change of sign. What closes the remaining gap is not
settled here; heteroscedastic noise tilted toward cheaper property was tried and moved
PRB by less than 0.01. The operational conclusion does not depend on it: PRB is not a
safe arbiter at this dispersion, so the direct slope is reported beside it.

`python3 prb_bias.py`

### What the time adjustment cost

Fitting the market trend on all sales returns 14.3% annual price growth for Dane County.
On post-lien sales, 13.8%. On chase-free sales, **6.0%**, which is the credible figure.
Two of those three are artifacts of the assessor's clerical practice rather than the
housing market.

## Status

The three findings above are stable on the full 24-month pull. Still open: the Cook
County reproduction described below, and municipality-level breakdowns within the
county.

## Data

| source | what | access |
|---|---|---|
| Wisconsin Statewide Parcels DB (WI DOA) | 169,025 class-1 residential parcels in Dane County, 2025 roll, with assessed value, land and improvement split, tax, address, coordinates | ArcGIS FeatureServer, public |
| WI DOR Real Estate Transfer Returns | parcel-level sale price and date, five year window | `propertyinfo.revenue.wi.gov`, public |

Raw pulls land in `data/` and are gitignored. Every script that touches the network
writes exactly one file and can be rerun.

## Validation before extension

The method is not novel. Chris Berry's Cook County work is the reference
implementation, and this pipeline is checked against his published figures before it is
pointed at a county nobody has studied. If the Cook reproduction does not land, the
Dane result is not trustworthy either and does not get published.

## Kill criterion, set in advance

If fewer than 1,500 clean arms-length residential sales join to parcels, Dane County
cannot support a ratio study at neighborhood resolution. In that case the study moves
to a Wisconsin county with cleaner records, and this README says so rather than
quietly dropping the resolution.

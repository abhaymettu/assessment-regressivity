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

Eight, on 5,821 chase-free arms-length residential sales joined to the 2025 roll. The
first was not the question the project set out to ask, and it changed how the rest had
to be measured.

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

### 4. Chasing is a municipal choice, and six offices make it

Wisconsin assesses at the municipal level, and Dane County holds 60 assessing
jurisdictions. If the sale prices were being written into the parcel layer by some
county or state process, every municipality would chase at about the same rate and this
would be a finding about a data pipeline rather than about assessment practice.

They do not. Across the 18 municipalities with enough pre-lien sales to measure:

| municipality | n | assessed to the dollar | pre-lien median ratio |
|---|---|---|---|
| Windsor, Village of | 163 | 82.2% | 1.0000 |
| McFarland, Village of | 130 | 81.5% | 1.0000 |
| Oregon, Village of | 199 | 80.9% | 1.0000 |
| Monona, City of | 87 | 80.5% | 1.0000 |
| Stoughton, City of | 223 | 72.2% | 1.0000 |
| **Madison, City of** | **2,909** | **69.0%** | **1.0000** |
| Mount Horeb, Village of | 106 | 0.9% | 0.9101 |
| Verona, City of | 218 | 0.9% | 0.9219 |
| DeForest, Village of | 247 | 0.8% | 0.9437 |
| Sun Prairie, City of | 551 | 0.7% | 0.9043 |
| Fitchburg, City of | 420 | 0.2% | 0.9981 |
| Middleton (Town), Waunakee, Middleton (City), Cottage Grove, Cross Plains, Belleville, Dunn | 62 to 304 each | 0.0% | 0.68 to 1.01 |

It is not a gradient. Six municipalities sit at **69% or above**, twelve sit at **0.9% or
below**, and **nothing occupies the 68 points between them**. Chasing is a practice an
assessing office either uses or does not, and six of them do, including the City of
Madison on 2,909 sales.

### Regressivity is everywhere, and it is not caused by the chasing

On chase-free sales, all 11 municipalities with 100 or more usable sales have a negative
slope. Range -0.516 to -0.050, median -0.159.

| municipality | n | median ratio | COD | slope |
|---|---|---|---|---|
| Windsor, Village of | 114 | 0.969 | 33.3 | -0.516 |
| Sun Prairie, City of | 434 | 0.874 | 19.1 | -0.473 |
| Stoughton, City of | 212 | 0.952 | 22.6 | -0.413 |
| McFarland, Village of | 109 | 0.969 | 20.9 | -0.283 |
| DeForest, Village of | 170 | 0.896 | 16.5 | -0.273 |
| Verona, City of | 187 | 0.906 | 14.0 | -0.159 |
| Fitchburg, City of | 360 | 0.963 | 17.1 | -0.134 |
| Oregon, Village of | 164 | 1.012 | 20.4 | -0.134 |
| Waunakee, Village of | 211 | 0.961 | 18.8 | -0.108 |
| Middleton, City of | 269 | 0.736 | 22.4 | -0.060 |
| Madison, City of | 2,473 | 0.979 | 12.2 | -0.050 |

Two things fall out of this. The county-wide regressivity result is not an aggregation
artifact, since it holds in all ten municipalities outside Madison. And Madison, the
heaviest chaser by volume, is the **least** regressive jurisdiction in the table once its
chased sales are removed.

The correlation between chasing rate and regressivity slope across the 11 municipalities
measurable on both is **r = -0.27**. Weak. These are two separate problems, and stopping
the chasing would not fix the regressivity.

`python3 municipalities.py`

### 5. It tracks the contractor, not the municipality

Wisconsin municipalities mostly contract their assessor rather than employing one, so
the six chasers may be six choices or one vendor's method. Joining the chasing rates to
the [Wisconsin DOR municipal assessor roster](https://www.revenue.wi.gov/Dor%20publications/assrlist.pdf)
answers it.

First a control. A municipality that did not revalue for 2025 set no new assessments, so
it could not chase and is not evidence either way. The state publishes an estimated fair
market value per parcel, and its ratio to assessed value is the assessment level,
computed independently of any sale used in this repo. Five of the eighteen sit between
0.65 and 0.78 and are excluded.

Among the thirteen that did revalue:

| assessor | chases | of |
|---|---|---|
| **Accurate Appraisal LLC** | **5** | **5** |
| Michelle Drea (Madison, in-house) | 1 | 1 |
| Associated Appraisal Consultants | 0 | 3 |
| Samuel Monroe | 0 | 1 |
| Peter Krystowiak | 0 | 1 |
| Chris Leitz | 0 | 1 |
| Paul Musser | 0 | 1 |

Accurate Appraisal LLC chases in **every revalued municipality it assesses**: Windsor,
McFarland, Oregon, Monona and Stoughton, at rates of 72% to 82%. Every other contractor
chases in none of theirs. Madison, the one jurisdiction here that assesses in house,
also chases, at 69% on 2,909 sales.

The two apparent counterexamples dissolved under the control. Cross Plains and
Belleville contract Accurate Appraisal and do not chase, but their assessment levels are
0.653 and 0.667. They did not revalue, so no assessment was set that could have been
copied from a sale.

That points at the contractor rather than the town hall. Finding 6 tests it outside Dane
County and narrows it: the firm does not chase everywhere it works, but no other
contractor chases anywhere.

`python3 assessors.py`

### 6. Replicated out of sample, and it narrowed the claim

Five Dane County municipalities are a thin base for a statement about a firm, and Dane is
where the pattern was found, so it cannot also be the evidence for it. Accurate Appraisal
serves 112 municipalities statewide, so the same measurement was re-run in four counties
picked only for having enough of them: Walworth, Columbia, Outagamie and Jefferson. The
RETR files were already statewide, so the sales side needed no new download. Columbia has
no municipality with enough pre-lien sales and drops out.

**Outside Dane the exclusivity held and the universality did not.** The firm's
municipalities chase at 44% (4 of 9), against **0 of 12** for every other contractor. So
the Dane result overstated it: the firm does not chase everywhere it works.

Pooled across all five counties:

| assessment level | Accurate Appraisal LLC | every other contractor |
|---|---|---|
| at or above 0.85 | 9 of 14 | **0 of 19** |
| at or above 0.95 | 9 of 11 | **0 of 10** |
| at or above 0.98 | **8 of 8** | **0 of 5** |

All 10 chasing municipalities across five counties are either Accurate Appraisal's (9) or
the City of Madison's in-house office (1). No municipality assessed by any other
contractor chases, in any county, at any assessment level.

Within the firm's own portfolio the practice tracks the assessment level. It happens
where a municipality is held at full market value and not where assessments have drifted,
which is what annual maintenance by copying sale prices would look like: a jurisdiction
between revaluations is not touching individual parcels at all.

So the defensible claim is conditional, not universal. Chasing is confined to one
contractor plus one in-house office, and within that contractor it appears where the
municipality is maintained at full market value.

`python3 replication.py`

### 7. The mechanism, measured directly instead of by proxy

Finding 6 used assessment level as a stand-in for whether a municipality was revaluing.
Wisconsin publishes the real variable. Every municipality files an assessment type each
year, and DOR publishes it inside the Tableau workbook behind its
[Wisconsin Real Estate Sales](https://public.tableau.com/views/Sales0_1/Story1)
dashboard: FULL REVALUATION, EXTERIOR REVALUATION, INTERIM MARKET, or MAINTENANCE.

Only an interim market update sets new values parcel by parcel without a full
revaluation, so it is the only assessment type where copying a sale price is possible at
all. That splits the question into an opportunity and a choice, and the data separates
them completely:

| 2025 assessment type | assessor | chasing | total |
|---|---|---|---|
| FULL REVALUATION | every other contractor | 0 | 1 |
| **INTERIM MARKET** | **Accurate Appraisal LLC** | **9** | **9** |
| **INTERIM MARKET** | Madison (in-house) | 1 | 1 |
| **INTERIM MARKET** | every other contractor | **0** | **8** |
| MAINTENANCE | Accurate Appraisal LLC | 0 | 8 |
| MAINTENANCE | every other contractor | 0 | 16 |

**All 10 chasing municipalities did an interim market update in 2025. None of the 25 on
any other assessment type chases, including all 8 of the target firm's own.**

Given the opportunity, one firm takes it 9 times out of 9 and no other contractor takes
it at all.

This retires the loose end from finding 6. The firm's non-chasing municipalities were
never exceptions to a rule about the firm. They are maintenance years, where no assessor
is revaluing anything, so there was nothing to chase. Assessment level was picking that
up indirectly; assessment type states it.

`python3 revaluation.py`

### 8. The regressivity survives the controls, at about half its size

Finding 2 says ratios differ across price deciles. The obvious objection is that cheap
and expensive homes are different homes, and a mass appraisal model doing its job will
make different errors on different kinds of property without any of it being about price.
The state parcel layer cannot answer that, because it holds an assessed value and an
address and nothing about the building.

The [City of Madison parcel layer](https://maps.cityofmadison.com/arcgis/rest/services/Public/OPEN_DATA2/FeatureServer/0)
holds the assessor's own inputs: year built, living area, bedrooms, baths, style,
basement, air conditioning, lot size, and the office's own assessment-area codes. 2,405
of Madison's 2,473 chase-free sales join to it.

**Most of this finding is a trap, and the trap is the interesting part.** The natural
specification regresses log assessment ratio on log2 sale price and adds the
characteristics as controls. It is wrong, and it is wrong in the direction that flatters
the finding. The dependent variable is `log(assessed) - log(price)` and the regressor is
`log2(price)`, so price sits on both sides. Controls that predict assessed value strip
out the part of the left side that is not price, and in the limit the coefficient goes to
`-ln 2 = -0.693` however fair the roll is.

That is measured, not asserted. A synthetic roll is built on which the assessor is neutral
by construction, its value being exactly the hedonic prediction of sale price with no
price grading whatsoever, and every specification is run against it:

| specification | slope | se | null | excess |
|---|---|---|---|---|
| price only | -0.1130 | 0.0068 | -0.0995 | -0.0134 |
| plus house characteristics | -0.2547 | 0.0120 | -0.3458 | +0.0910 |
| plus assessment-area fixed effects | -0.2599 | 0.0114 | -0.3337 | +0.0737 |
| plus both | -0.4132 | 0.0156 | **-0.6931** | +0.2800 |

The fully controlled null lands on -ln 2 to four decimals. **Adding controls made the
estimate 3.7 times larger and told us nothing.** The most heavily controlled
specification is the most contaminated, not the most convincing. Anyone reporting -0.413
as a stronger version of -0.113 would be reporting arithmetic.

The specification that works replaces realised sale price with *predicted* price, fitted
from the characteristics and the assessment area. The prediction contains nothing from
the individual transaction, so sale-price noise cannot enter the regressor:

| specification | slope | se | t | null |
|---|---|---|---|---|
| log ratio on log2 **predicted** price | **-0.0626** | 0.0077 | -8.1 | +0.0000 |

Zero on the neutral roll by construction rather than by luck. On the real roll, **-0.063
per doubling, 55% of the uncontrolled -0.113, and outside IAAO's neutral band of plus or
minus 0.05.**

So the answer is yes, with a haircut. Half of Madison's apparent regressivity was the
composition of cheap and expensive housing stock. The other half is two houses of the
same age, size, style and assessment neighborhood being assessed at different fractions
of what they are worth, and that half is eight standard errors from zero.

Ranked by predicted rather than realised price, the cheapest tenth of Madison homes
carries an assessment ratio **4.8%** higher than the priciest tenth. The gradient is not
monotone: it is flat to slightly rising through the middle and falls away in the top
three deciles, so what this measures is the expensive end being under-assessed rather
than the cheap end being singled out.

One caveat stated rather than buried. The 68 sales that fail to join move the
uncontrolled Madison slope from -0.050 to -0.113. They are parcels the state layer codes
as class-1 residential but Madison holds no house record for: apartment buildings,
assemblies, and a $3.4m parcel assessed at 0.14 of it. The joined sample is the narrower
and cleaner one and it is also the more regressive one.

`python3 fetch_madison.py && python3 hedonic.py`

### What the time adjustment cost

Fitting the market trend on all sales returns 14.3% annual price growth for Dane County.
On post-lien sales, 13.8%. On chase-free sales, **6.0%**, which is the credible figure.
Two of those three are artifacts of the assessor's clerical practice rather than the
housing market.

## Status

The findings above are stable on the full 24-month pull and split by municipality. The
Cook County reproduction described below has been run and it lands. Still open: whether
the contractor pattern holds in the target firm's remaining counties. Five of the
roughly twenty counties it works in have been tested.

## Data

| source | what | access |
|---|---|---|
| Wisconsin Statewide Parcels DB (WI DOA) | 169,025 class-1 residential parcels in Dane County, 2025 roll, with assessed value, land and improvement split, tax, address, coordinates | ArcGIS FeatureServer, public |
| WI DOR Real Estate Transfer Returns | parcel-level sale price and date, five year window | `propertyinfo.revenue.wi.gov`, public |
| WI DOR Wisconsin Municipal Assessors | contracted assessor for all 1,913 Wisconsin municipalities across 71 counties | `assrlist.pdf`, public |
| WI DOR Wisconsin Real Estate Sales | assessment type per municipality per year, 1,913 municipalities | Tableau workbook extract, public |
| City of Madison Tax Parcels | 72,347 residential parcels with year built, living area, bedrooms, baths, style, basement, air conditioning, lot size and the assessor's own area codes | ArcGIS FeatureServer, public |
| Cook County Assessor, Parcel Sales and Assessed Values | 559,483 class-2 residential sales 2015 to 2019 with mailed, certified and board values | `datacatalog.cookcountyil.gov`, Socrata, public |

Raw pulls land in `data/` and are gitignored. Every script that touches the network
writes exactly one file and can be rerun.

## Validation: the Cook County reproduction

The method is not novel. Christopher Berry's Center for Municipal Finance work is the
reference implementation, and until this section was written the pipeline here was
self-consistent and externally unverified.

The reference is
[An Evaluation of Property Tax Regressivity in Cook County, Illinois](https://erhla.github.io/Cook%20County,%20Illinois.html),
covering residential sales from 2015 to 2019. It publishes N, COD, PRD and PRB for each
of five years and a median ratio for each of ten price deciles, so there are 35 numbers
to miss rather than one. It was produced with the
[`cmfproperty`](https://github.com/cmf-uchicago/cmfproperty) R package, whose source
settles the two methodological questions that matter: arms-length means a ratio inside
`[Q1 - 1.5 IQR, Q3 + 1.5 IQR]` computed within sale year, and the CPI adjustment scales
sale price and assessed value by the same factor, so every statistic is invariant to it.

The same `iaao.py` that judges Dane County, imported not reimplemented, run against Cook
County Assessor open data:

| year | n here | n published | COD | published | PRD | published | PRB | published |
|---|---|---|---|---|---|---|---|---|
| 2015 | 52,750 | 51,879 | 21.31 | 19.70 | 1.082 | 1.105 | -0.0540 | -0.0514 |
| 2016 | 61,280 | 62,852 | 21.10 | 20.26 | 1.067 | 1.084 | -0.0413 | -0.0462 |
| 2017 | 62,644 | 65,961 | 20.85 | 20.25 | 1.052 | 1.056 | -0.0226 | -0.0269 |
| 2018 | 64,299 | 65,298 | 19.30 | 19.29 | 1.023 | 1.016 | +0.0090 | +0.0133 |
| 2019 | 62,565 | 62,041 | 18.60 | 18.06 | 1.022 | 1.011 | +0.0086 | +0.0098 |

Sample size within 6% every year, COD within 8%, PRD within 2%, PRB within 0.005. **PRB
crosses zero between 2017 and 2018 in both.** That is the most specific thing the
published table says, and matching a sign change on the same year is stronger evidence
than matching a level.

The decile gradient reproduces as shape rather than as level. Median ratios here run
about 0.015 below the published ones at every decile, a uniform offset and not a
different pattern, and the summary statistic the gradient exists to support lands on it:
the cheapest tenth of Cook County homes is assessed at **27.2%** more of sale price than
the priciest, against **28.4%** published.

### Two things the report does not say, and one thing that changed

The report does not state which assessment stage it read, and does not state whether it
applied the Assessor's own sale flags. Separately, the Assessor has since backfilled the
sales file from MyDec, so today's extract carries roughly 20% more conveyances for these
years than existed when the report was written. Taking the file as-is returns CODs 12%
to 27% high on 15% to 22% more sales, which is what adding a tail of lower-quality
conveyances to a dispersion statistic does.

So the specification is swept rather than assumed and the whole sweep is printed. Twelve
combinations, best is board-of-review values with multi-parcel and flagged sales
dropped. That is fitting to the target and is labelled as such. What is **not** fitted is
the gradient: it lands between 27% and 29% under all twelve, including the unfiltered
one, so the regressivity finding does not depend on the choice.

The pipeline lands on someone else's published numbers. The Dane County findings above
are now externally anchored rather than only internally consistent.

`python3 fetch_cook.py && python3 cook.py`

## Kill criterion, set in advance

If fewer than 1,500 clean arms-length residential sales join to parcels, Dane County
cannot support a ratio study at neighborhood resolution. In that case the study moves
to a Wisconsin county with cleaner records, and this README says so rather than
quietly dropping the resolution.

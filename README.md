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

## Status

Preliminary, on two months of sales out of a twenty-four month window. The direction is
clear and the magnitude is not yet settled.

On 739 arms-length residential sales joined to the 2025 roll:

| statistic | estimate | 95% CI | IAAO range | verdict |
|---|---|---|---|---|
| median ratio | 0.960 | 0.950 to 0.970 | 0.90 to 1.10 | passes |
| COD | 14.06 | 12.74 to 15.50 | 5.0 to 15.0 | inconclusive |
| PRD | 1.039 | 1.027 to 1.052 | 0.98 to 1.03 | inconclusive |
| PRB | -0.063 | -0.104 to -0.028 | -0.05 to 0.05 | inconclusive |

Median ratio by sale-price decile falls from **1.000** in the cheapest tenth to
**0.899** in the priciest. The cheapest tenth carries an assessment ratio 11.2% higher
than the priciest tenth.

The aggregate ratio, which is the statistic the state certifies on, is **0.914**, and
it is the same number whether that burden is spread evenly or concentrated.

Both PRD and PRB have point estimates outside the IAAO range and confidence intervals
that straddle the boundary, so neither is called a failure yet. Two months is a tenth
of the intended sample. The remaining twenty-two months are what settle it, and they
are the next step rather than a caveat to be waved away.

### Time bias, to handle before the window widens

These two months of sales sit immediately after the 1 January 2025 assessment date, so
sale price and assessed value refer to nearly the same moment. Extending the window
back through 2024 compares 2025 assessments against older prices in a rising market,
which mechanically depresses ratios for earlier sales. IAAO handles this with a time
adjustment, and the ratios need one before the full window is analysed. Skipping it
would manufacture regressivity if cheaper homes turn over at different times of year
than expensive ones.

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

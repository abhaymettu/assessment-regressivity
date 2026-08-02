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

In progress. Nothing here is a finding yet.

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

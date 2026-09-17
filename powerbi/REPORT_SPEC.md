# Power BI report implementation

The final PBIP contains two visible pages. This document records the implemented business questions and acceptance rules. The executable report layout is under `EV Charging Intelligence.Report/`.

Visible page count: **2**.

## Page 1: Executive and Regional Screening

**Question:** What is happening nationally, and which large BEV markets warrant further investigation?

Implemented content:

- Registered BEVs, public charging points, fast charging points and the `53 of 100` screening signal.
- Total-versus-fast regional provision scatter with regional median reference lines.
- National normal-versus-fast charging mix.
- Large-market fast-provision gap chart.
- Top regions to investigate and Top 10 BEV market context.
- Source dates and the 62-day KBA-to-BNetzA lag.
- No map is included because the governed product is defined at a custom 400-region analytical grain.

The page describes comparative registered provision. It does not rank investments or claim observed charging demand.

## Page 2: Region Profile

**Question:** Why did the selected region surface, and how does it compare with the regional benchmark?

Implemented content:

- Single-region slicer with `München, Stadt` as the delivered example.
- Dynamic regional summary and BEV stock rank.
- Registered BEVs, total points per 1,000 BEVs and fast points per 1,000 BEVs.
- Selected-region-versus-regional-median comparison for total, fast and facility provision.
- Compact infrastructure details and normal-versus-fast point mix.
- Screening-scope note and compact publication-quality strip.

The report must never display a multi-region aggregate as though it belongs to one region.

## Presentation rules

- Two visible pages only.
- Clear business labels, normal punctuation and no promotional language.
- Teal for primary analytical context, muted magenta for attention and gray for benchmarks.
- Median comparisons are screening context, not targets.
- Facility nominal power must not be described as grid capacity or charging capacity.
- Do not add forecasts, a composite investment score, site recommendations or investment claims.

## Validation status

The delivered Windows PBIP includes both report pages, the adjacent semantic model, 74 measures and the embedded final theme. The public copy has been cleaned of local caches, authoring state, live workspace identifiers and credentials. A Power BI Service deployment is not claimed.

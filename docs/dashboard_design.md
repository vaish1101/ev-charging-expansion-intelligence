# Dashboard Visual Design, Writing and Labeling Standard

This standard applies to the final two-page Databricks AI/BI dashboard and two-page Power BI report. It governs presentation only. It does not change Gold calculations, business keys, source values or analytical grain.

## Visual design and theme

Use restrained, role-based color systems. The implemented Databricks dashboard uses:

| Role | Color |
|---|---|
| Canvas | Dark teal `#071A1F` |
| Panels | Deep teal `#0D242A` |
| Primary or selected observation | Teal `#18B3AE` |
| Screening attention | Magenta `#D94F8A` |
| Secondary analytical focus | Cyan `#38A8C7` |
| Benchmark or background context | Slate `#7F969B` |
| Main text | Off-white `#E8F1F2` |
| Border | Dark slate `#17343B` |
| Genuine pass/readiness state only | Green `#2E7D5B` |
| Genuine error/failure only | Red `#B84A4A` |

Colors communicate analytical roles rather than permanent metric identities: teal is primary/selected, magenta is screening attention, cyan is secondary focus, and slate is benchmark/background. Never use red or green to classify a region as above or below a median. A regional median is a descriptive comparison, not a target.

The Power BI report deliberately uses a light executive treatment:

| Role | Color |
|---|---|
| Canvas | Off-white `#F5F7F9` |
| Main text | Deep navy `#12263A` |
| Primary or selected observation | Teal `#0F8B8D` |
| Screening attention | Muted magenta `#B34B78` |
| Benchmark or background context | Gray `#7B8794` / `#A7B2BC` |
| Genuine pass/readiness state only | Green `#2E7D5B` |

Power BI visuals use whitespace and alignment instead of boxes inside boxes. Default borders, shadows, filled containers, decorative header strips, and rounded-card effects are disabled. Databricks remains the dark analytical product; Power BI is the calm light executive report.

Avoid gradients, neon or rainbow palettes, glass effects, decorative icons, emojis, giant title banners, excessive rounded cards, shadows, donuts, gauges and unnecessary chart variety. Pages use aligned edges, consistent headers, regular spacing, no more than two or three visual rows where practical, and no unused areas filled with prose.

## Dashboard writing standard

All visible text must read like it was written by a senior data analyst for business stakeholders.

Do not use marketing language, generic filler or synthetic phrasing. Prohibited examples include:

- unlocking insights
- data-driven excellence
- empowering decision-making
- actionable intelligence
- strategic opportunities
- optimize your journey
- leverage the power of
- key takeaways
- landscape
- deep dive
- comprehensive overview
- robust solution

Visible dashboard copy must also avoid:

- em dashes;
- long subtitles;
- sentence fragments that sound generated;
- unnecessary adjectives;
- dramatic or causal claims;
- repeated caveats written in different ways;
- technical jargon where plain business language works.

Use clear, direct English. Keep titles short and specific. One short subtitle may explain what a visual shows or how to interpret it. Do not add a paragraph when the visual is self-explanatory.

Preferred titles include:

- Executive Summary
- Regional Provision Screening
- Total vs Fast Charging Provision
- Region Profile
- Data Quality & Definitions
- Evidence Still Required
- Source Dates
- Pipeline Status

Preferred wording examples:

- `Regional Provision Screening`, not `A Comprehensive Deep Dive into Regional Charging Infrastructure`.
- `55 regions have above-median total provision but below-median fast provision`, not `A notable divergence can be observed across the regional charging landscape`.
- `Further evidence is needed before an investment decision`, not `Additional multidimensional analysis is required to unlock investment readiness`.
- `Compares registered public charging provision with registered BEV stock across 400 analysis regions.`

Use one term for each concept throughout:

- registered BEVs;
- registered charging points;
- fast charging points;
- regional median;
- points per 1,000 BEVs;
- screening signal;
- warrants further investigation.

Write for an intelligent business stakeholder who does not know the data model. Never expose database column names as visual labels. Axis labels must state meaningful units.

Before release, review every page title, subtitle, card label, chart title, axis label, legend, callout, methodology note and tooltip. Rewrite anything promotional, vague, overly technical or inconsistent. Every visible sentence must pass this test: would a senior analyst put it in a client dashboard or management presentation?

## Platform-specific product roles

- **Databricks AI/BI:** two visible business pages: Germany Market & Provision Screening, and Region Profile. All 400 regions remain in the scatter, the Top 100 receive visual emphasis, and trust evidence is a single compact line.
- **Power BI:** two visible pages demonstrating concise executive BI and interaction: Executive & Regional Screening, and Region Profile & Decision Context. Page 1 has four cards, one dominant scatter, one compact composition visual, and one screening table. Page 2 has three main cards, one comparison chart, one infrastructure strip, and compact scope/trust footers. Methodology appears through an information button and bookmark panel, not a third visible page.

The two products share metric definitions and terminology, but they are not visual copies.

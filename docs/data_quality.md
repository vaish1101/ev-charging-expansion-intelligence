# Data Quality

The release uses blocking checks rather than warning-only validation. A Gold candidate is not published unless all 73 checks pass.

## Control areas

- approved source filenames, sizes and SHA-256 checksums;
- physical schemas, required columns and parsing contracts;
- expected row grain and source keys;
- 400 unique KBA statistical keys with numeric BEV stock;
- 401 current Destatis districts reconciled to 400 analysis regions;
- no silent loss of unmatched BNetzA geography;
- charging facilities, points and connectors kept at distinct grains;
- operational eligibility limited to exact `Status = 'In Betrieb'`;
- registered facility nominal power counted once per eligible facility;
- regional rows reconciled to national controls;
- candidate publication isolated from the prior published result;
- published serving views restricted to a validated snapshot.

## Published controls

| Control | Value |
|---|---:|
| Analysis regions | 400 |
| Registered BEVs | 2,362,218 |
| Registered passenger cars | 49,644,855 |
| In-service facilities | 116,423 |
| In-service charging points | 209,098 |
| Normal points | 154,702 |
| Fast points | 54,396 |
| Registered cumulative nominal power of in-service facilities | 9,086,313.500 kW |
| Blocking checks | 73 passed, 0 failed |

Twenty facilities with `Status = 'In Wartung'` remain in lineage but are excluded from operational KPIs. They account for 38 registered charging points and 484.000 kW in the approved source snapshot.

Controlled schema and checksum failures were rejected before publication, and the prior published Gold values remained unchanged. The machine-readable evidence is in [`../evidence/`](../evidence/).

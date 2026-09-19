# Final Release Manifest

This manifest identifies the principal public release artifacts. `FILE_INVENTORY.sha256` contains a checksum for every public file except the inventory itself.

## Databricks workspace retirement

The Databricks workspace was intentionally decommissioned after export and archival. Authenticated Bundle validation cannot be repeated against the deleted workspace. Reproducibility is supported by the source-controlled Bundle configuration, preserved clean deployment proof, reference outputs and automated tests.

The complete Power BI PBIP source is included. Raw provider files are not redistributed.

| Artifact | Path | SHA-256 | Visibility | Purpose |
|---|---|---|---|---|
| Root README | `README.md` | `9f09be5631475f1c681d50b9f3e3818dce556fbe31bb64cc2234fc8e2bcdb1de` | Public | Business and technical project guide |
| Databricks dashboard PDF | `dashboards/databricks/databricks-dashboard.pdf` | `2221e4acc302b7e9a58fa7c35b95bb85cfe8bbfe9dd427af57bc2051d92b440f` | Public | Final dashboard pages and successful workflow |
| Power BI dashboard PDF | `dashboards/powerbi/power-bi-dashboard.pdf` | `3c46fc915fb29f5fa495f1c6b9c85e3c7d34505248d288932f947ace48763e8a` | Public | Final two-page executive report |
| Power BI Project | `powerbi/EV Charging Intelligence.pbip` | `581b110fd500ad9307f479271cff22388693688b2a43d0bfc1995372963acc29` | Public | Entry point for the version-controlled PBIP source |
| Databricks dashboard source | `databricks/dashboards/ev_charging_intelligence.template.lvdash.json` | `ef59a3eb7d4112c22bcecb53d6b39323b53ba9fdc09ffb56d5d5b44b966f9393` | Public | Catalog-parameterized dashboard definition |
| Source manifest | `data/source_manifest.json` | `49bfd7080d4dd1343913d7c874352a469ca83e3e6e1c0b830987fb8b37935280` | Public | Official source URLs, dates, sizes and checksums |
| Regional reference output | `data/reference/regional_kpi_snapshot.csv` | `8e0ec038231beca5255304d80b624a346d71f91b4dbac1cf27d8b7f2b83b9904` | Public | Portable 400-region Gold reference |
| Quality reference output | `data/reference/dataset_quality.csv` | `e2f5068b93cd1443a89582a0b98ad32e6364fe17f9adb4e57dd2566890e93c66` | Public | Portable publication-quality reference |
| Clean deployment proof | `evidence/clean_deployment_proof.md` | `a78f2a4324a6ab1f69ebab8b0062017ec2fed0c5b4c8acc648e75ba1dded44a3` | Public | Bundle, workflow and control evidence |

# Data

This project uses three official German public-sector sources. Raw provider files are **not committed** to this repository; only their metadata (URL, reference date, size and SHA-256 checksum) is source-controlled, in [`source_manifest.json`](source_manifest.json) and [`../config/source_revisions_v1.json`](../config/source_revisions_v1.json).

## Sources and licenses

| Publisher | Dataset | License | Attribution |
|---|---|---|---|
| Kraftfahrt-Bundesamt (KBA) | Vehicle registration statistics, FZ 27.15 | [Datenlizenz Deutschland – Namensnennung – Version 2.0](https://www.kba.de/DE/Service/Hinweise/Datenlizenz/datenlizenz_node.html) (dl-de/by-2-0) | Use `Kraftfahrt-Bundesamt`, identify the FZ 27 dataset and source URI, link the license, and mark this project's transformations as changed/derived data. |
| Bundesnetzagentur (BNetzA) | Ladesäulenregister | [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) (CC BY 4.0) | Use the publisher's required credit `Bundesnetzagentur.de`, link the register page and CC BY 4.0, and identify changes made by this project. |
| Statistisches Bundesamt (Destatis) | GV-ISys administrative geography workbook | Product-specific notice: `© Statistisches Bundesamt (Destatis), 2026. Vervielfältigung und Verbreitung, auch auszugsweise, mit Quellennachweis gestattet.` | Cite `Statistisches Bundesamt (Destatis)`, the GV-ISys workbook/source page and reference date, and state that the project transformed the source. |

The three sources do not share one blanket license statement. KBA's dl-de/by-2-0 terms require a source note containing the provider, the license name/link and the dataset URI when supplied, plus a change notice for transformed data. BNetzA applies CC BY 4.0 to the charging-register data and explicitly requires `Bundesnetzagentur.de` as the attribution. The approved Destatis workbook carries its own source-specific reproduction notice; this project therefore preserves that notice instead of inferring that the workbook is licensed under the separate GENESIS-Online terms.

None of these terms is the [MIT license](../LICENSE) covering this repository's own code. The repository does not relicense provider data and does not redistribute the raw files.

## Source notes used by this project

- **KBA:** `Source: Kraftfahrt-Bundesamt, FZ 27.15, reference date 1 July 2026, processed by the project; Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0).` Include the [dataset page](https://www.kba.de/DE/Statistik/Produktkatalog/produkte/Fahrzeuge/fz27_b_uebersicht.html) and [license text](https://www.govdata.de/dl-de/by-2-0).
- **BNetzA:** `Source: Bundesnetzagentur.de, Ladesäulenregister, reference date 1 September 2026, processed by the project; CC BY 4.0.` Include the [register page](https://www.bundesnetzagentur.de/DE/Fachthemen/ElektrizitaetundGas/E-Mobilitaet/Ladesaeulenkarte/start.html) and [license text](https://creativecommons.org/licenses/by/4.0/).
- **Destatis:** `Source: © Statistisches Bundesamt (Destatis), GV-ISys, administrative status 30 June 2026, processed by the project. Reproduction and distribution, including excerpts, permitted with source attribution.` Include the [source page](https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis/Administrativ/Archiv/GVAuszugQ/AuszugGV2QAktuell.html).

## Obtaining the raw files

1. Use the `source_url` for each file in [`source_manifest.json`](source_manifest.json) to download it directly from the publisher.
2. Save it under `data/raw/<publisher>/<filename>` exactly as named in the manifest.
3. Verify the SHA-256 checksum matches the manifest entry before use:

   ```bash
   shasum -a 256 data/raw/bnetza/Ladesaeulenregister_BNetzA_2026-09-01.csv
   ```

4. Publishers periodically update these datasets. If a downloaded file's checksum does not match the manifest, you have retrieved a different revision; add it as a new entry in `config/source_revisions_v1.json` rather than overwriting the recorded one, following the project's immutable-revision rule (see [`docs/methodology.md`](../docs/methodology.md)).

## Why the raw files aren't committed

- KBA and Destatis files total roughly 40 MB and 4 MB respectively; the BNetzA register alone is about 54 MB. Committing them would bloat the repository without adding reproducibility value beyond what the manifest already provides.
- Each publisher already hosts the authoritative, current copy; linking to it avoids this repository silently going stale relative to the source.
- The gitignore rule (`data/raw/**/*.csv`, `data/raw/**/*.xlsx`) enforces this consistently, and CI rejects any accidental commit of a raw snapshot.

## Reproducible reference exports

The repository includes two compact, public reference exports under [`reference/`](reference/):

- [`regional_kpi_snapshot.csv`](reference/regional_kpi_snapshot.csv), containing the 400 governed analysis-region rows.
- [`dataset_quality.csv`](reference/dataset_quality.csv), containing the published snapshot quality record.

These files were reconstructed from the three exact checksum-verified Core V1 source revisions using the source-controlled geography, status, charging-point and nominal-power rules. The reconstruction independently reproduced the locked national controls before writing either file. They preserve a portable reference result after the Databricks workspace is retired; they are not substitutes for the official provider files or a live Unity Catalog export.

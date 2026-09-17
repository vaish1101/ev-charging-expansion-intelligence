# SQL validation templates

These files preserve the acceptance and analytical validation queries without embedding one workspace's identifiers.

Before submitting a request JSON, replace:

- `__WAREHOUSE_ID__` with the selected SQL Warehouse ID;
- `__CATALOG__` with the catalog supplied to the Bundle;
- `__DATE_SET_ID__` with the identifier derived from `config/date_set_manifest_core_v1.json` when the template contains it.

The production workflow does not depend on these request files. They are transparent, rerunnable validation templates for reviewers who want to inspect the exact controls.

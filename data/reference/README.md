# Governed Reference Data

Files in this directory contain small, reviewed mappings used by the pipeline.
Unlike `data/raw`, these files are maintained as part of the analytical model
and should be reviewed through source control.

## `cost_code_map.csv`

Maps the legacy ERP cost-code taxonomy to the estimating system's taxonomy.
The mapping is semantic rather than a punctuation-only transformation. For
example, ERP code `05-500` maps to estimating code `5200`.

`99-999` is retained with `mapping_status=unmapped` so unexpected ledger cost
is visible in data-quality reporting instead of being silently discarded.

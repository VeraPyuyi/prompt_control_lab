# Deterministic metric semantics

`format_error` retains its historical v1 definition: 1 for whitespace-only output, 0 for any nonempty output. Its UI name is **Empty output check** (lower is better). It never checked JSON or a schema. Existing experiment/v1 snapshots and saved scores are not migrated.

Use `json_valid@1` for JSON tasks: 1 for strict JSON, 0 for missing or invalid JSON, including NaN/Infinity. Use `json_schema@1` to validate JSON against the schema serialized in each task's `expected` string. Both are higher-is-better metrics. The schema subset supports type, required, properties, enum, items and boolean additionalProperties; unsupported keywords and invalid schemas are rejected, never silently ignored. No remote references or network lookups are supported.

New JSON experiment records retain output, metric_id, metric_version, direction and failure_reason. Reasons are stable codes: missing_output, invalid_json, or required/type/enum/additional_property followed by a field path. Offline replay uses the same versioned scorer without provider calls. Choosing a metric does not change the default exact_match scorer for existing configurations.

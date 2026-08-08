# 🕵️ Circular Dependency Audit Report  (PLACEHOLDER — format sample)

> This file is a sanitized **format sample**, not real output. Audits regenerate
> actual reports; real findings reference live `src2/...` paths and line numbers
> and are NOT shipped to end users. All values below are `{{placeholder}}`.

Scanned `{{scanned_files_count}}` files in `src2/{{sample_module}}`.

## 📂 `src2/{{module}}.py`

### ✅ Line `{{line}}`: `src2.{{a}} -> src2.{{b}} -> src2.{{a}}`
- **Verdict**: `FALSE_POSITIVE`
- **Severity**: `LOW`
- **Reasoning**: The import of `query_{{thing}}` from `.{{a}}` is performed inside
  a function body (lazy import), which prevents a circular dependency at
  module-level initialization time.

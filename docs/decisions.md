# Architecture Decisions

This log records key technical decisions, why they were made, and their consequences.

---

## 001 – BigQuery sandbox as the data warehouse

**Date:** 2026-11-17

**Context:** The degree project must use free tiers only. No billing account may be attached.

**Decision:** Use Google BigQuery in sandbox mode (no billing account) in the GCP project `aml-monitoring-christocar`.

**Consequences:**
- No cost risk.
- DML statements (`INSERT`, `UPDATE`, `DELETE`, `MERGE`) are not allowed.
- Tables expire automatically after 60 days, so the full pipeline must be re-runnable from source files.

---

## 002 – Data stored in the EU region

**Date:** 2026-11-17

**Context:** The data is synthetic but handled as if it were real bank data. Swedish banks are subject to GDPR and generally keep customer data within the EU.

**Decision:** All BigQuery datasets are created in the `EU` location.

**Consequences:** Mirrors realistic data residency requirements for a Swedish bank.

---

## 003 – IBM AML dataset, HI-Small variant

**Date:** 2026-11-17

**Context:** The IBM Transactions for Anti Money Laundering dataset comes in six variants (HI/LI × Small/Medium/Large, about 7.6 GB in total).

**Decision:** Use HI-Small (5,078,345 transactions, 518,581 accounts, 370 labelled laundering attempts).

**Consequences:**
- Enough known laundering cases to develop and demonstrate detection rules.
- Fits comfortably within sandbox storage limits and keeps development fast.
- LI-Small (lower, more realistic illicit ratio) is a possible extension for validating the rules.

---

## 004 – BigQuery load jobs instead of dlt for ingestion

**Date:** 2026-11-17

**Context:** dlt was planned as the ingestion tool. A connection test with three rows failed with `403 ... DML queries are not allowed in the free tier`. dlt writes to its internal state tables (`_dlt_version`, `_dlt_loads`, `_dlt_pipeline_state`) using `INSERT`, which the sandbox blocks.

**Decision:** Replace dlt with BigQuery load jobs via the `google-cloud-bigquery` Python library (`ingestion/load_raw.py`).

**Consequences:**
- Load jobs are free and allowed in the sandbox.
- dlt also uses load jobs internally, so the underlying loading mechanism is the same.
- Schema definition, re-runnability and row count validation are implemented explicitly in the script.

---

## 005 – Raw layer stored as STRING only (ELT)

**Date:** 2026-11-17

**Context:** The source data contains bank IDs with leading zeros (e.g. `010`), timestamps in a non-standard format (`2022/09/01 00:20`) and duplicate column names (`Account` twice).

**Decision:** Load all raw columns as `STRING` into the `aml_raw` dataset with explicit, renamed columns (`from_account`, `to_account`). Data types are applied in the dbt staging layer.

**Consequences:**
- The raw layer is an exact, auditable copy of the source.
- Loads cannot fail or silently lose data due to type conversion.
- Type casting and validation become testable in dbt.

---

## 006 – Idempotent full reloads with row count verification

**Date:** 2026-11-17

**Context:** Sandbox tables expire after 60 days, and the pipeline must be safe to re-run.

**Decision:** All raw tables use `WRITE_TRUNCATE`. After each load, the script compares the number of rows in BigQuery with the source file and fails if they differ. The patterns file is parsed strictly and fails on any unexpected format.

**Consequences:**
- The pipeline can be run any number of times with the same result.
- Data loss is detected immediately instead of silently.
- dbt models will use full rebuilds rather than incremental models (which require `MERGE`).

---

## 007 – Local authentication via Application Default Credentials

**Date:** 2026-11-17

**Context:** Local development needs access to BigQuery without risking leaked credentials.

**Decision:** Authenticate locally with `gcloud auth application-default login`. No key files are stored in the repository.

**Consequences:**
- No secrets in the repo.
- CI/CD and orchestration will use a dedicated service account, set up later with Terraform.


---

## 008 – dbt Core v1.12 instead of dbt v2

**Date:** 2026-11-17

**Context:** dbt v2 (Rust-based engine) reached general availability in September 2026 and is now the default for new installations. dbt Core v1 (Python-based) remains supported with security and compatibility patches.

**Decision:** Use dbt Core v1.12 with the `dbt-bigquery` adapter.

**Consequences:**
- Mature, well-documented tooling with broad community knowledge and integrations (e.g. Dagster), which reduces risk within the project timeline.
- Fully open source (Apache 2.0).
- The project is written without deprecation warnings so it can be upgraded to dbt v2 later. The upgrade is listed as a possible extension.
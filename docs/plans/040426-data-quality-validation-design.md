# Data Quality Validation — Design Doc

**Date:** 04/04/26
**Status:** Approved

## Goal

Automatically verify that `data/latest.json` has the correct structure after each daily collection run, with GitHub Actions failure emails as the alert mechanism.

## Approach

Add a `pytest tests/test_data_quality.py` step to `daily.yml` that runs immediately after data collection. Tests read the real `data/latest.json` and assert structural correctness. If any assertion fails, the job fails and GitHub emails the repo owner.

## What Gets Validated

**Top-level keys:** `updated_at`, `prices`, `sonia`, `news`, `boe`, `alerts`, `overall_status`

**prices:** All 4 bank keys present (`BARC.L`, `LLOY.L`, `NWG.L`, `HSBA.L`). Each bank has fields: `name`, `price`, `change_pct_1d`, `change_pct_5d`, `change_pct_30d`, `week_52_high`, `week_52_low`, `history_90d`, `status`.

**sonia:** Fields present: `rate`, `change_1d`, `history_90d`, `status`.

**boe:** Fields present: `ccyb_rate`, `next_fsr_date`, `next_ccyb_decision`, `recent_announcements`.

**news:** Is a list.

**overall_status:** One of `green`, `amber`, `red`.

## What Does NOT Get Validated

- Value correctness (e.g. price > 0) — out of scope, collectors already handle errors gracefully via `status: error`
- Freshness of `updated_at` — not needed; the test runs immediately after collection
- News item count — can legitimately be 0 on quiet days

## Files Changed

- Create: `tests/test_data_quality.py`
- Modify: `.github/workflows/daily.yml` (add one step after collection)

## Alert Mechanism

GitHub Actions built-in failure notification — no new infrastructure required.

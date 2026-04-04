# Data Quality Validation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a structural validation test for `data/latest.json` that runs automatically after every daily collection, failing the GitHub Actions job (and triggering a failure email) if the data is malformed.

**Architecture:** A single new test file `tests/test_data_quality.py` reads the real `data/latest.json` and asserts structural correctness. Unlike the existing unit tests (which use mocks), this test reads the actual file on disk. A new step in `daily.yml` runs these tests after data collection — if they fail, the job fails and GitHub emails the repo owner.

**Tech Stack:** Python 3.11, pytest, GitHub Actions

---

## Task 1: `tests/test_data_quality.py`

**Files:**
- Create: `tests/test_data_quality.py`

Note: These tests read the real `data/latest.json`. They will PASS immediately if the file exists and is well-formed (it does — the daily workflow has already run). Run them locally first to confirm, then they become the live gate in CI.

**Step 1: Create `tests/test_data_quality.py`**

```python
# tests/test_data_quality.py
import json
import os
import pytest

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "latest.json")

BANK_KEYS   = {"BARC.L", "LLOY.L", "NWG.L", "HSBA.L"}
BANK_FIELDS = {
    "name", "price", "change_pct_1d", "change_pct_5d", "change_pct_30d",
    "week_52_high", "week_52_low", "history_90d", "status",
}
SONIA_FIELDS = {"rate", "change_1d", "history_90d", "status"}
BOE_FIELDS   = {"ccyb_rate", "next_fsr_date", "next_ccyb_decision", "recent_announcements"}
TOP_KEYS     = {"updated_at", "prices", "sonia", "news", "boe", "alerts", "overall_status"}
VALID_STATUS = {"green", "amber", "red"}


@pytest.fixture(scope="module")
def data():
    with open(DATA_FILE) as f:
        return json.load(f)


def test_top_level_keys_present(data):
    missing = TOP_KEYS - data.keys()
    assert not missing, f"Missing top-level keys: {missing}"


def test_all_banks_present(data):
    missing = BANK_KEYS - data["prices"].keys()
    assert not missing, f"Missing bank entries: {missing}"


def test_each_bank_has_required_fields(data):
    for sym, bank in data["prices"].items():
        missing = BANK_FIELDS - bank.keys()
        assert not missing, f"{sym} missing fields: {missing}"


def test_sonia_has_required_fields(data):
    missing = SONIA_FIELDS - data["sonia"].keys()
    assert not missing, f"SONIA missing fields: {missing}"


def test_boe_has_required_fields(data):
    missing = BOE_FIELDS - data["boe"].keys()
    assert not missing, f"BoE missing fields: {missing}"


def test_news_is_list(data):
    assert isinstance(data["news"], list), "news must be a list"


def test_overall_status_is_valid(data):
    assert data["overall_status"] in VALID_STATUS, \
        f"overall_status '{data['overall_status']}' not in {VALID_STATUS}"
```

**Step 2: Run the tests locally**

```bash
.venv/bin/pytest tests/test_data_quality.py -v
```

Expected output: **7 passed** — confirms the tests work against the existing `data/latest.json`.

**Step 3: Commit**

```bash
git add tests/test_data_quality.py
git commit -m "feat: data quality structural validation tests"
```

---

## Task 2: Wire into `daily.yml`

**Files:**
- Modify: `.github/workflows/daily.yml`

**Step 1: Add the validation step**

In `.github/workflows/daily.yml`, after the `Run data collection` step, add:

```yaml
      - name: Validate collected data
        run: pytest tests/test_data_quality.py -v
```

The full `jobs.collect.steps` section should look like this:

```yaml
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run data collection
        env:
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          DASHBOARD_URL: ${{ secrets.DASHBOARD_URL }}
        run: python orchestrator.py

      - name: Validate collected data
        run: pytest tests/test_data_quality.py -v
```

**Step 2: Run full test suite to confirm nothing broken**

```bash
.venv/bin/pytest -v
```

Expected: **48 passed** (41 existing + 7 new).

**Step 3: Commit and push**

```bash
git add .github/workflows/daily.yml
git commit -m "feat: run data quality validation after daily collection"
git push
```

**Step 4: Verify in GitHub Actions**

Trigger the daily workflow manually (Actions → Daily data collection → Run workflow). Confirm the "Validate collected data" step appears and passes in the run log.

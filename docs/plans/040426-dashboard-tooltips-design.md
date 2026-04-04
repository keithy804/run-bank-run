# Dashboard Inline Explainers — Design Doc

**Date:** 04/04/26
**Status:** Approved

## Goal

Add inline ⓘ tooltips to the existing `index.html` dashboard so visitors unfamiliar with the data can understand what each metric means and where it comes from. No separate page — everything stays in one place.

## Audience

External visitors who may not have financial/banking background. Content must be accessible to a general audience.

## Approach

A small **ⓘ icon** next to each section heading. Click/tap toggles a compact popover. Clicking anywhere else closes it. CSS + ~20 lines of vanilla JS. No new dependencies.

## Tooltip Content

### Bank Status
- **What:** Current share price status for Barclays, Lloyds, NatWest, HSBC listed on the London Stock Exchange.
- **Colours:** 🟢 Green = normal. 🟡 Amber = approaching alert threshold. 🔴 Red = significant move (≥5% drop in a day or ≥15% over 5 days). ⚪ = data unavailable.
- **Source:** Yahoo Finance via the yfinance library, collected weekday mornings.

### Share Prices
- **What:** Up to 90 days of daily closing prices for each bank (in pence).
- **Controls:** 7d / 30d / 90d buttons adjust the chart window.
- **Source:** Yahoo Finance.

### SONIA Rate
- **What:** Sterling Overnight Index Average — the interest rate at which banks lend to each other overnight. It's the UK's benchmark rate, similar to SOFR in the US.
- **Why it matters:** A sudden move in SONIA can signal stress in short-term funding markets.
- **Source:** Bank of England IADB API (series IUDSOIA).

### Latest Headlines
- **What:** Recent news headlines related to UK banking.
- **How filtered:** Pulled from BBC Business, Reuters UK, and Bank of England RSS feeds, then filtered for keywords: bank, Barclays, Lloyds, NatWest, HSBC, banking, financial stability, Bank of England.
- **Source:** BBC Business, Reuters, Bank of England RSS feeds.

### Bank of England
- **CCyB (Countercyclical Capital Buffer):** Extra capital UK banks are required to hold as a buffer during periods of high credit growth. A higher rate means regulators are being more cautious.
- **FSR (Financial Stability Report):** Published by the Bank of England twice a year, assessing risks to the UK financial system.
- **Dates:** Manually updated in config when BoE announces changes.
- **Source:** Bank of England publications RSS feed.

## "About this data" link

A subtle link in the page header opens a modal with a condensed plain-English overview — for visitors who want the full picture rather than per-metric tooltips.

## Implementation

- **Tooltip trigger:** `<button class="info-btn">ⓘ</button>` next to each `<h2>`
- **Popover:** `<div class="tooltip-box">` absolutely positioned below the ⓘ, hidden by default
- **JS:** Single click handler on `document` — toggle active popover, close on outside click
- **Styling:** Matches card design (white background, border, border-radius, same font)
- **Mobile:** Click/tap (no hover dependency)
- **Changes to:** `index.html` only — no Python changes

## No tests required

Pure HTML/CSS/JS addition to a static file. Verify manually in browser.

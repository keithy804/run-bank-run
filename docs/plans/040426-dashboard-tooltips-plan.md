# Dashboard Inline Explainers — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ⓘ tooltip buttons to each dashboard section so visitors understand what each metric means and where the data comes from, plus an "About" section at the bottom of the page.

**Architecture:** Pure HTML/CSS/JS changes to `index.html` only. No Python changes. No new dependencies. Tooltip popover mechanism uses a `.tooltip-wrap` / `.tooltip-box` pattern toggled by a single JS click handler. "About this data" link in the header anchors to a new `#about` section at the bottom of the page.

**Tech Stack:** Vanilla HTML, CSS (custom properties already in file), vanilla JS

---

## Task 1: CSS + JS tooltip infrastructure

**Files:**
- Modify: `index.html` (CSS block, lines 8–54; JS block, lines 108 onward)

No visible change to the page yet — just adds the mechanism.

**Step 1: Add tooltip CSS**

Inside the `<style>` block, immediately before the closing `</style>` tag, add:

```css
  /* Tooltip infrastructure */
  .info-btn {
    background: none; border: 1px solid var(--border); border-radius: 50%;
    width: 20px; height: 20px; font-size: 11px; cursor: pointer;
    color: var(--muted); margin-left: 8px; vertical-align: middle;
    padding: 0; line-height: 1;
  }
  .info-btn:hover { background: #eee; color: var(--text); }
  .tooltip-wrap { position: relative; display: inline-block; }
  .tooltip-box {
    display: none; position: absolute; top: calc(100% + 8px); left: 0;
    z-index: 200; background: #fff; border: 1px solid var(--border);
    border-radius: 8px; padding: 14px 16px; width: 300px; font-size: 14px;
    line-height: 1.5; box-shadow: 0 4px 16px rgba(0,0,0,0.12); color: var(--text);
  }
  .tooltip-box.active { display: block; }
  .tooltip-box p { margin: 0 0 8px; }
  .tooltip-box p:last-child { margin: 0; }
  .tooltip-source { color: var(--muted); font-size: 12px; }
  /* About link in header */
  .about-link { color: rgba(255,255,255,0.7); font-size: 13px; text-decoration: none;
                margin-left: 12px; }
  .about-link:hover { color: #fff; }
  /* About section */
  #about h3 { font-size: 15px; margin: 16px 0 4px; }
  #about p  { font-size: 14px; color: var(--muted); margin: 0 0 8px; }
```

**Step 2: Add tooltip JS**

Inside the `<script>` block, after the final `});` of `loadData().catch(...)`, add:

```js
// Tooltip toggle — click ⓘ to open, click anywhere else to close
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.info-btn');
  const boxes = document.querySelectorAll('.tooltip-box');
  if (btn) {
    const box = btn.closest('.tooltip-wrap').querySelector('.tooltip-box');
    const wasActive = box.classList.contains('active');
    boxes.forEach(b => b.classList.remove('active'));
    if (!wasActive) { box.classList.add('active'); e.stopPropagation(); }
  } else {
    boxes.forEach(b => b.classList.remove('active'));
  }
});
```

**Step 3: Open `index.html` in a browser and confirm no errors in the JS console**

**Step 4: Commit**

```bash
git add index.html
git commit -m "feat: tooltip CSS and JS infrastructure"
```

---

## Task 2: Add ⓘ buttons to all five sections

**Files:**
- Modify: `index.html` (HTML body, lines 70–103)

Replace each bare `<h2>` with a version containing the tooltip wrap. The pattern for every section is:

```html
<h2>Section Title <span class="tooltip-wrap">
  <button class="info-btn" aria-label="About this data">ⓘ</button>
  <div class="tooltip-box">
    <p>...</p>
    <p class="tooltip-source">📡 Source: ...</p>
  </div>
</span></h2>
```

**Step 1: Replace the Bank Status heading (line 72)**

```html
  <section>
    <h2>Bank Status <span class="tooltip-wrap">
      <button class="info-btn" aria-label="About Bank Status">ⓘ</button>
      <div class="tooltip-box">
        <p>Shows the current share price and daily movement for Barclays, Lloyds, NatWest, and HSBC — the four largest UK retail banks.</p>
        <p>🟢 Green = normal &nbsp; 🟡 Amber = approaching alert levels &nbsp; 🔴 Red = significant drop (≥5% in a day or ≥15% over 5 days) &nbsp; ⚪ = data unavailable.</p>
        <p class="tooltip-source">📡 Yahoo Finance, collected weekday mornings.</p>
      </div>
    </span></h2>
    <div class="bank-grid" id="bank-cards">Loading...</div>
  </section>
```

**Step 2: Replace the Share Prices heading (line 78)**

```html
  <section>
    <h2>Share Prices <span class="tooltip-wrap">
      <button class="info-btn" aria-label="About Share Prices">ⓘ</button>
      <div class="tooltip-box">
        <p>Daily closing prices in pence (p) for each bank on the London Stock Exchange, over up to 90 trading days.</p>
        <p>Use the 7d / 30d / 90d buttons to change the chart window. Prices are not adjusted for dividends.</p>
        <p class="tooltip-source">📡 Yahoo Finance via yfinance.</p>
      </div>
    </span></h2>
    <div class="toggle-group">
      <button class="active" onclick="setRange('prices', 7, this)">7d</button>
      <button onclick="setRange('prices', 30, this)">30d</button>
      <button onclick="setRange('prices', 90, this)">90d</button>
    </div>
    <canvas id="prices-chart"></canvas>
  </section>
```

**Step 3: Replace the SONIA Rate heading (line 89)**

```html
  <section>
    <h2>SONIA Rate <span class="tooltip-wrap">
      <button class="info-btn" aria-label="About SONIA">ⓘ</button>
      <div class="tooltip-box">
        <p><strong>SONIA</strong> (Sterling Overnight Index Average) is the rate at which banks lend to each other overnight in sterling. It is the UK's main benchmark interest rate — similar to SOFR in the US.</p>
        <p>A sudden spike or drop in SONIA can signal stress in short-term bank funding markets. The chart shows the last 30 days.</p>
        <p class="tooltip-source">📡 Bank of England IADB API (series IUDSOIA).</p>
      </div>
    </span></h2>
    <canvas id="sonia-chart"></canvas>
  </section>
```

**Step 4: Replace the Latest Headlines heading (line 95)**

```html
  <section>
    <h2>Latest Headlines <span class="tooltip-wrap">
      <button class="info-btn" aria-label="About Headlines">ⓘ</button>
      <div class="tooltip-box">
        <p>Recent news headlines related to UK banking, filtered automatically for relevance.</p>
        <p>Keywords matched: <em>bank, Barclays, Lloyds, NatWest, HSBC, banking, financial stability, Bank of England</em>.</p>
        <p class="tooltip-source">📡 BBC Business, Reuters UK, and Bank of England RSS feeds.</p>
      </div>
    </span></h2>
    <ul class="headlines" id="headlines">Loading...</ul>
  </section>
```

**Step 5: Replace the Bank of England heading (line 101)**

```html
  <section>
    <h2>Bank of England <span class="tooltip-wrap">
      <button class="info-btn" aria-label="About Bank of England data">ⓘ</button>
      <div class="tooltip-box">
        <p><strong>CCyB</strong> (Countercyclical Capital Buffer) is extra capital UK banks must hold as a financial cushion. A higher rate means regulators are being more cautious about systemic risk.</p>
        <p><strong>FSR</strong> (Financial Stability Report) is published by the Bank of England twice a year, assessing risks to the UK financial system.</p>
        <p class="tooltip-source">📡 Bank of England RSS feed. CCyB rate and dates updated manually when BoE announces changes.</p>
      </div>
    </span></h2>
    <div class="boe-footer" id="boe-info">Loading...</div>
  </section>
```

**Step 6: Open in browser — click each ⓘ icon and verify the popover opens and closes correctly. Test on mobile viewport too.**

**Step 7: Commit**

```bash
git add index.html
git commit -m "feat: add tooltip explainers to all five dashboard sections"
```

---

## Task 3: "About this data" header link + explainer section

**Files:**
- Modify: `index.html`

**Step 1: Add "About this data" link to the header**

Replace the current header block (lines 58–61):

```html
<header>
  <h1>🏦 UK Bank Stability Monitor</h1>
  <p id="last-updated">Loading... &nbsp;·&nbsp; <a class="about-link" href="#about">About this data ↓</a></p>
</header>
```

**Step 2: Add `#about` section before `</main>`**

Replace the closing `</main>` tag (line 104) with:

```html
  <!-- About section -->
  <section id="about">
    <h2>About This Monitor</h2>
    <p style="font-size:14px;color:var(--muted);margin:0 0 16px;">
      A personal dashboard for tracking the financial stability of the four largest UK retail banks.
      Data is collected automatically on weekday mornings and the page updates within minutes.
      Alerts fire when movements exceed predefined thresholds — they are informational only and not financial advice.
    </p>

    <h3>What the indicators mean</h3>
    <p><strong>Share prices</strong> — Daily closing prices in pence from the London Stock Exchange. Status colours reflect day-on-day (≥5% = red) and 5-day (≥15% = red) moves.</p>
    <p><strong>SONIA</strong> — The Sterling Overnight Index Average: the rate UK banks charge each other for overnight loans. Sudden moves can indicate funding stress.</p>
    <p><strong>CCyB</strong> — Countercyclical Capital Buffer: the extra capital UK banks must hold as a rainy-day fund. Set by the Bank of England's Financial Policy Committee.</p>
    <p><strong>FSR</strong> — Financial Stability Report: published twice a year by the Bank of England, assessing risks to the UK financial system.</p>

    <h3>Where the data comes from</h3>
    <p><strong>Share prices &amp; 52-week highs/lows</strong> — Yahoo Finance (via the open-source yfinance library).</p>
    <p><strong>SONIA rate</strong> — Bank of England IADB API, series IUDSOIA.</p>
    <p><strong>News headlines</strong> — BBC Business, Reuters UK, and Bank of England RSS feeds, filtered for banking keywords.</p>
    <p><strong>BoE announcements, CCyB rate, FSR dates</strong> — Bank of England publications RSS feed; CCyB rate and dates are updated manually when the BoE announces changes.</p>

    <h3>Disclaimer</h3>
    <p>This monitor is for personal informational use only. It is not financial advice. Data may be delayed or inaccurate. Do not make investment decisions based on this dashboard.</p>
  </section>
</main>
```

**Step 3: Open in browser — click "About this data ↓" in the header and verify it scrolls to the About section.**

**Step 4: Run full visual check**
- All five ⓘ popovers open and close correctly
- "About" link scrolls to section
- Page looks correct on mobile viewport (320px wide)
- No JS console errors

**Step 5: Commit and push**

```bash
git add index.html
git commit -m "feat: About section and header link"
git push
```

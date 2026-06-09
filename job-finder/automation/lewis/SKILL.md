---
name: lewis
description: Lewis — the job finder. Sweeps Google "dork" searches via Chrome, extracts and scores new job postings against Andrew's profile, and writes them to tracker.xlsx + jobs/<id>/. Trigger on: "run Lewis", "run the job finder", "find new jobs", "do a job sweep". (Named for Lewis of Lewis & Clark — the scout who maps the territory ahead.)
---

# Lewis — Job Finder

Finds and records new job postings in **two places**: a row in `tracker.xlsx` and `jobs/<id>/` (with `posting.txt` + `meta.json`). Never applies.

Paths assume "Job Finding" is the working directory (`/sessions/<session>/mnt/Job Finding/`).

## Prerequisites
1. **Chrome connected:** `list_connected_browsers` → if `[]`, stop and tell Andrew to connect Chrome with the Claude extension, then re-run.
2. **Tracker ready:** `python3 automation/lewis/tracker.py init`
3. **Profile skimmed:** read `profile/` (resume, positioning, experience-bank, voice) — needed for scoring in Step 4.

## Step 0 — Session resume (every run, before anything else)
```bash
python3 automation/lewis/tracker.py session resume
# prints one of: started-fresh | resumed-same-day | resumed-new-day
```
- **resumed-same-day:** `--pending` (Step 1) will skip already-swept queries; `seen-urls` (Step 2) will skip already-opened postings. Pick up exactly where you left off.
- **resumed-new-day:** queries_done is reset but urls_seen carries over — you'll re-sweep all queries but won't re-open postings already extracted yesterday.
- **started-fresh:** clean slate.

## Run modes

**Sequential (default):** single worker, sweeps all pending queries, opens new postings.

**Parallel (faster):** one subagent per board running concurrently. Coordinator steps:
1. `python3 automation/lewis/queries.py --list-boards` — get active board keys.
2. Launch one subagent per board (Agent tool, all at once). Give each this brief, substituting `<BOARD>`:
   > Board worker `<BOARD>`. `tabs_create_mcp` → claim your own tab; pass that `tabId` on every browser call. Get your pending queries: `python3 automation/lewis/queries.py --urls --board <BOARD> --pending`. Run Steps 1–5 of the Lewis SKILL on them. After Step 3, score and write results. Report: new qualified, low-fit, dupes.
3. Wait for all subagents. Combine results and give Andrew the summary (Step 6).

Notes: each subagent must `tabs_create_mcp` its own tab and never act on another agent's tab. Pacing (~2–5s between requests) applies per worker.

## Step 1 — Sweep pending queries
```bash
python3 automation/lewis/queries.py --urls --pending
```
(`--pending` skips queries already marked done in this session's `session-state.json`.)

For each URL in the output:
- `navigate` → `get_page_text` / `read_page` → collect candidate posting links.
- Text view truncates URLs — use `find` to get real `href`s.
- CAPTCHA: ask Andrew to solve it in the browser; do not attempt to bypass.
- After sweeping: `python3 automation/lewis/tracker.py session mark-query <query-url>`
- Pace: ~2–5s random delay between queries.

## Step 2 — De-dupe candidates
Build the skip list before opening anything:
```bash
# All URLs already in tracker (cross-session)
python3 automation/lewis/tracker.py urls

# URLs opened in this session (same-day resume)
python3 automation/lewis/tracker.py session seen-urls
```
Skip any candidate whose URL appears in either list.

## Step 3 — Extract new postings (parallel)
You now have a list of new candidate URLs. Extract them in parallel to minimize wall-clock time.

**If ≤3 new URLs:** open them yourself, one at a time.

**If ≥4 new URLs:** split into batches of ~5. Spawn one extraction subagent per batch (all at once):
> Extraction worker. `tabs_create_mcp` → claim your tab. For each URL in your batch: `navigate` → `get_page_text` → extract the fields listed below. After each URL: `python3 automation/lewis/tracker.py session mark-url <url>`. Pace ~2–5s between navigations. Return a JSON array of raw job objects. Do NOT score — return raw data only.

Fields to extract per posting:
- `company`, `role`, `location`, `remote` (Remote / Hybrid / Onsite)
- `pay_range` (as posted; blank if absent — never invent)
- `industry` (Fintech, Legal Tech, Healthcare, SaaS, etc.)
- `ats` (ashbyhq→Ashby, greenhouse→Greenhouse, lever→Lever, myworkdayjobs→Workday, else "other")
- `posting` = full job description text
- `url`, `source_query`

Wait for all extraction subagents. Merge their JSON arrays into one pool.

## Step 4 — Score fit (coordinator)
Score each extracted job against the profile (already in context from Prerequisites):

| fit_rating | criteria |
|---|---|
| 5 | data/analytics/AE role, Python+SQL core, domain of interest, ~4 yrs ok, remote/Chicago |
| 4 | strong overlap, minor gap or seniority stretch |
| 3 | adjacent (PM / solutions / sales-eng where data + client story transfers) |
| 2 | tangential / hits the 5-yr minimum hard |
| 1 | off-profile or hard disqualifier (clearance, must-relocate city, etc.) |

Set `qualified`: Yes / Stretch / Maybe for jobs worth pursuing; No for the rest. Add one-line `fit_reason`. Be honest — low scores are useful signal.

**Qualification gate:** Yes / Stretch / Maybe or `fit_rating ≥ 3` → `jobs/<id>/` folder created. No / `fit_rating < 3` → thin tracker row only (still recorded so it won't be re-opened next run).

## Step 5 — Write results
```bash
python3 automation/lewis/tracker.py add - <<'JSON'
[
  {"company":"...","role":"...","location":"...","remote":"Remote","pay_range":"...",
   "industry":"...","ats":"Ashby","qualified":"Yes","fit_rating":4,"fit_reason":"...",
   "url":"https://...","source_query":"...","posting":"<full JD text>"}
]
JSON
```
`id` auto-slugged from company+role. `tracker.py` handles de-dup, folder creation, and file locking for concurrent writes.

## Step 6 — Report
Short summary to Andrew: new jobs found, count rated 4+, compact list of the best ones (company — role — rating — pay — link). Point him at `tracker.xlsx` to mark the `decision` column (Apply / Skip / Maybe). Do not start applying.

## Notes
- Never auto-apply, submit, or sign in anywhere. Find and record only.
- Never fabricate pay, location, or remote status — leave blank if the posting is silent.
- To change searches: edit `GROUPS` in `queries.py`. To change schema: edit `tracker.py`.
- Overnight unattended runs require Bright Data SERP (future upgrade path).

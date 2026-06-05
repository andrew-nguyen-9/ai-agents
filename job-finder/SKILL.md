---
name: job-finder
description: Sweep saved Google "dork" searches via Claude in Chrome, extract and fit-score new job postings against Andrew's profile, and write them to tracker.xlsx + a jobs/<id>/ folder. Trigger when Andrew says "run the job finder", "find new jobs", or "do a job sweep".
---

# Job Finder

Find new job postings, score them against Andrew's profile, and record each one in
**two places**: a row in `tracker.xlsx` and a folder `jobs/<id>/` (with `posting.txt`
+ `meta.json`). This skill **only finds and records** — it never applies.

Paths assume this folder ("Job Finding") is the working directory. In bash the mount
is `/sessions/<session>/mnt/Job Finding/`.

## Prerequisites (check first)
1. **Chrome must be connected.** Call `list_connected_browsers`. If it returns `[]`,
   stop and tell Andrew to open Chrome with the Claude extension and connect it, then
   re-run. Everything below needs a live, logged-in browser.
2. Make sure `tracker.xlsx` exists: `python3 automation/job-finder/tracker.py init`.
3. Read `automation/job-finder/queries.txt` for the active query list, and skim
   `profile/` (resume, positioning, experience-bank, voice) so scoring is grounded.

## Step 1 — Run each query in Chrome
For every active (non-`#`) line in `queries.txt`:
- Build the URL: `https://www.google.com/search?q=<url-encoded query before any &>` then
  append any `&tbs=...` flag verbatim. Example line
  `"Data Analyst" site:jobs.ashbyhq.com remote &tbs=qdr:d` →
  `https://www.google.com/search?q=%22Data%20Analyst%22%20site%3Ajobs.ashbyhq.com%20remote&tbs=qdr:d`
- `navigate` there, then `get_page_text` / `read_page` to collect the result links.
- If a CAPTCHA appears, ask Andrew to solve it in the browser, then continue. Do **not**
  try to bypass it.
- Collect candidate posting URLs (the actual ATS links, e.g. `jobs.ashbyhq.com/...`).

## Step 2 — De-dupe before opening
Load existing keys so you don't re-process known jobs:
`python3 -c "import openpyxl;ws=openpyxl.load_workbook('tracker.xlsx')['jobs'];print([(r[0],r[11]) for r in ws.iter_rows(min_row=2,values_only=True)])"`
Skip any candidate whose URL already appears. (`tracker.py add` also de-dupes by id and
url as a safety net, so it's fine to be approximate here.)

## Step 3 — Open each new posting and extract
Navigate to the posting and `get_page_text`. Pull:
- `company`, `role`, `location`, `remote` (Remote / Hybrid / Onsite)
- `pay_range` (as posted; blank if absent — never invent one)
- `industry` (infer: Fintech, Legal Tech, Healthcare, SaaS, etc.)
- `ats` from the URL host: ashbyhq→Ashby, greenhouse→Greenhouse, lever→Lever,
  myworkdayjobs→Workday, indeed→Indeed, else "other"
- `posting` = the full job-description text (this becomes `jobs/<id>/posting.txt`)
- `url`, and the `source_query` line that surfaced it

## Step 4 — Score fit against the profile
Set `qualified` (Yes / Stretch / No) and `fit_rating` (1–5) using the rubric in
`AGENT-GAME-PLAN.md`:
- 5 = data/analytics/AE role, Python+SQL core, domain he'd lean into, ~4 yrs fine, remote/Chicago
- 4 = strong overlap, minor gap or slight seniority stretch
- 3 = adjacent (PM / solutions / sales-eng where his data + client story transfers)
- 2 = tangential / hits the 5-yr-min wall hard
- 1 = off-profile or a hard disqualifier (clearance, must-relocate city, etc.)
Add a one-line `fit_reason`. Be honest — low scores are useful signal.

## Step 5 — Write results (Excel + folder, in one call)
Assemble a JSON array of the new jobs and pipe it to the helper, which appends de-duped
rows to `tracker.xlsx` and creates each `jobs/<id>/` with `posting.txt` + `meta.json`:

```bash
python3 automation/job-finder/tracker.py add - <<'JSON'
[
  {"company":"...","role":"...","location":"...","remote":"Remote","pay_range":"...",
   "industry":"...","ats":"Ashby","qualified":"Yes","fit_rating":4,
   "fit_reason":"...","url":"https://...","source_query":"...","posting":"<full JD>"}
]
JSON
```
`id` is auto-slugged from company+role and matches the folder name. New rows get
`status=Found` and a blank `decision` for Andrew to mark.

## Step 6 — Report
Give Andrew a short summary: how many new, how many rated 4+, and a compact list of the
best ones (company — role — rating — pay — link). Point him at `tracker.xlsx` to mark the
`decision` column (Apply / Skip / Maybe). Do not start applying.

## Notes
- Never auto-apply, submit, or sign in anywhere. Find and record only.
- Never fabricate pay, location, or remote status — leave blank if the posting is silent.
- To change what gets searched, edit `queries.txt`. To change the schema, edit `tracker.py`.
- Fully unattended overnight runs aren't possible with Chrome (needs your machine awake);
  the Bright Data SERP scraper is the upgrade path if you want that later.

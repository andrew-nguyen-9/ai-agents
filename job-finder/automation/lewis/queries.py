#!/usr/bin/env python3
"""
queries.py — the Job Finder's search list, as editable Python.

Why this exists: queries are now data in a dict, so you can toggle them in code.
  * Disable one search ......... comment out its term line with `#`
  * Disable a whole group ...... set "on": False (or comment the whole block)
  * Add a board ................ add to BOARDS, reference it by key
  * Change freshness/scope ..... edit the group's "freshness" / "suffix"

Preview what will run:
    python3 queries.py                  # table of ACTIVE queries
    python3 queries.py --urls           # just the Google URLs (what the finder sweeps)
    python3 queries.py --all            # include disabled groups/terms too
    python3 queries.py --board ashby    # only one board (repeatable; for parallel agents)
    python3 queries.py --list-boards    # distinct active boards (one per line)
    python3 queries.py --urls --pending # URLs not yet marked done in this session

The finder (see SKILL.md) consumes `python3 queries.py --urls`. In parallel mode each
subagent runs `--urls --board <key> --pending` so it sweeps only its own pending queries.
"""

import json
from pathlib import Path
from urllib.parse import quote

# --- Freshness filters (Google &tbs= values) -------------------------------
HOUR, DAY, WEEK, MONTH = "qdr:h", "qdr:d", "qdr:w", "qdr:m"
# Lesson from the first sweeps: qdr:d (past day) is very sparse — most queries
# returned 0. WEEK is the better default; keep a few DAY ones only if you sweep
# every day and want only the freshest.

# --- ATS job boards (Google site: operators) -------------------------------
BOARDS = {
    "ashby":           "site:jobs.ashbyhq.com",
    "greenhouse":      "site:boards.greenhouse.io",
    "greenhouse_new":  "site:job-boards.greenhouse.io",   # newer Greenhouse domain
    "lever":           "site:jobs.lever.co",
    "workable":        "site:apply.workable.com",
    "smartrecruiters": "site:jobs.smartrecruiters.com",
    "workday":         "site:myworkdayjobs.com",
}

# --- Query groups ----------------------------------------------------------
# Each group = one board + freshness + shared suffix, applied to many term lines.
# Final query string = <term>  <board>  <suffix>     (then &tbs=<freshness>)
#
# Notes baked in from the live sweeps:
#   * "Chicago" as a keyword returned 0 everywhere (JDs rarely contain the city).
#     Dropped it; rely on "remote" and filter location when reviewing.
#   * Lever "remote" is flooded by the "Jobgether" aggregator + offshore roles —
#     the lever group excludes it with `-jobgether`.
#   * The three keepers all came from Ashby/Greenhouse "Data Analyst ... remote".

GROUPS = [
    {
        "name": "Core — Ashby (remote, weekly)",
        "on": True, "board": "ashby", "freshness": WEEK, "suffix": "remote",
        "terms": [
            '"Data Analyst"',
            '"Analytics Engineer"',
            '"Data Scientist"',
            '"BI Analyst"',
            '"Data" "Manager"',
            '"Analytics" "Manager"',
            '"Data" "Manager"',
            '"Analytics"',
        ],
    },
    {
        "name": "Core — Greenhouse (remote, weekly)",
        "on": True, "board": "greenhouse", "freshness": WEEK, "suffix": "remote",
        "terms": [
            '"Data Analyst"',
            '"Analytics Engineer"',
            '"Data Scientist"',
            '"BI Analyst"',
            '"Data" "Manager"',
            '"Analytics" "Manager"',
            '"Data" "Manager"',
            '"Analytics"',
        ],
    },
    {
        "name": "Core — Greenhouse new domain (remote, weekly)",
        "on": True, "board": "greenhouse_new", "freshness": WEEK, "suffix": "remote",
        "terms": [
            '"Data Analyst"',
            '"Analytics Engineer"',
            '"Data Scientist"',
            '"BI Analyst"',
            '"Data" "Manager"',
            '"Analytics" "Manager"',
            '"Data" "Manager"',
            '"Analytics"',
        ],
    },
    {
        "name": "Lever — de-noised (exclude Jobgether aggregator)",
        "on": True, "board": "lever", "freshness": WEEK, "suffix": "remote -jobgether",
        "terms": [
            '"Data Analyst"',
            '"Analytics Engineer"',
            '"Data Scientist"',
            '"BI Analyst"',
            '"Data" "Manager"',
            '"Analytics" "Manager"',
            '"Data" "Manager"',
            '"Analytics"',
        ],
    },
    {
        "name": "Healthcare / EHR — his strongest edge",
        "on": True, "board": "greenhouse", "freshness": WEEK, "suffix": "remote",
        "terms": [
            '"Healthcare Data Analyst" OR "Clinical Data Analyst"',
            '"Epic" OR "Cerner" "data analyst"',
            '"health" "data analyst"',
        ],
    },
    {
        "name": "Forensic / fraud / financial crimes (litigation background)",
        "on": True, "board": "greenhouse", "freshness": WEEK, "suffix": "remote",
        "terms": [
            '"Fraud Analyst" OR "Financial Crimes" OR "AML" "SQL"',
            '"Investigations" "data" "analyst"',
            '"Relativity" OR "eDiscovery" "analyst"',
        ],
    },
    {
        "name": "Adjacent titles that fit his profile",
        "on": True, "board": "ashby", "freshness": WEEK, "suffix": "remote",
        "terms": [
            '"Insights Analyst" OR "Decision Scientist"',
            '"Strategy & Analytics" OR "Strategy and Analytics"',
            '"Data Engineer" "Python" "SQL"',
        ],
    },
    {
        # Flip "on" to True to test these once you trust the core set.
        "name": "Experimental boards (Workable / SmartRecruiters / Workday)",
        "on": False, "board": "workable", "freshness": WEEK, "suffix": "remote",
        "terms": [
            '"Data Analyst"',
            '"Analytics Engineer"',
            '"Data Scientist"',
            '"BI Analyst"',
            '"Data" "Manager"',
            '"Analytics" "Manager"',
            '"Data" "Manager"',
            '"Analytics"',
        ],
    },
]


def active_boards(include_disabled=False):
    """Distinct board keys used by active (or all) groups, in declared order."""
    seen = []
    for g in GROUPS:
        if not include_disabled and not g.get("on", True):
            continue
        if g["board"] not in seen:
            seen.append(g["board"])
    return seen


def build(include_disabled=False, boards=None):
    """Return [{board, group, query, url}] for active (or all) term lines.

    boards: optional iterable of board keys to restrict to (for parallel agents).
    """
    rows = []
    for g in GROUPS:
        if not include_disabled and not g.get("on", True):
            continue
        if boards and g["board"] not in boards:
            continue
        board = BOARDS[g["board"]]
        fresh = g.get("freshness", WEEK)
        suffix = g.get("suffix", "")
        for term in g["terms"]:
            q = " ".join(p for p in (term, board, suffix) if p)
            url = f"https://www.google.com/search?q={quote(q, safe='')}&tbs={fresh}"
            rows.append({"board": g["board"], "group": g["name"], "query": q, "url": url})
    return rows


if __name__ == "__main__":
    import sys
    argv = sys.argv[1:]
    include = "--all" in argv
    # collect --board values (repeatable)
    boards = []
    for i, a in enumerate(argv):
        if a == "--board" and i + 1 < len(argv):
            boards.append(argv[i + 1])
    boards = boards or None

    if "--list-boards" in argv:
        for b in active_boards(include_disabled=include):
            print(b)
        sys.exit(0)

    rows = build(include_disabled=include, boards=boards)

    if "--pending" in argv:
        session_file = Path(__file__).resolve().parents[2] / "session-state.json"
        done = set()
        if session_file.exists():
            import json as _json
            state = _json.loads(session_file.read_text())
            done = set(state.get("queries_done", []))
        rows = [r for r in rows if r["url"] not in done]

    if "--urls" in argv:
        for r in rows:
            print(r["url"])
    else:
        cur = None
        for r in rows:
            if r["group"] != cur:
                cur = r["group"]
                print(f"\n# {cur}")
            print("   " + r["query"])
        scope = " (including disabled)" if include else ""
        scope += f" (boards: {','.join(boards)})" if boards else ""
        print(f"\n{len(rows)} active queries{scope}")

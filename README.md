# AMIS Student Schedule Builder — CMSC 170 Project

A **Constraint Satisfaction Problem (CSP)** that builds a conflict-free weekly
class schedule for a UPLB student, using data scraped from AMIS.

**Four methods implemented and benchmarked:**

| # | Method | Type |
|---|---|---|
| 1 | Backtracking with MRV + LCV | Systematic search |
| 2 | Backtracking + Forward Checking (MRV + FC) | Systematic search |
| 3 | Min-Conflicts | Local search |
| 4 | Simulated Annealing | Local search |

---

## CSP Formulation

| Element | Description |
|---|---|
| **Variable** | A curriculum slot (e.g. `Y3FS-1 → CMSC 124`) |
| **Domain** | All LEC+LAB bundles for that course that are open and require no consent |
| **Constraint** | No two assigned bundles may have overlapping meeting times |

The solver targets **Year 2, First Semester, SP track** by default
(change `year` and `term` in `evaluate.py`).

---

## Repository layout

```
.
├── data/
│   ├── curriculum.csv               BS CS 2018 flowchart (SP + Thesis tracks)
│   ├── raw/term_1261/               Raw JSON pages from AMIS (read-only scrape)
│   └── datasets/term_1261/
│       ├── sections.csv             One row per class section (LEC or LAB)
│       ├── meetings.csv             One row per (section, day); times in minutes after midnight
│       ├── summary.json             Counts for the project page
│       ├── faculty/                 Dataset A — faculty load (not used for this project)
│       └── student/                 Dataset B — student scheduler
│           ├── bundles.csv          LEC+LAB bundles a student can enlist in
│           ├── coverage.csv         Which curriculum courses are offered this term
│           └── instances.json       One CSP instance per curriculum term
├── solver/
│   ├── csp.py                       CSP class: loads data, builds domains, checks constraints
│   ├── backtracking.py              Method 1 — MRV + LCV backtracking
│   ├── forward_checking.py          Method 2 — MRV + Forward Checking
│   ├── min_conflicts.py             Method 3 — Min-Conflicts local search
│   ├── simulated_annealing.py       Method 4 — Simulated Annealing
│   └── evaluate.py                  Runs all four methods and prints a comparison table
├── scrape.py                        READ-ONLY AMIS collector (Playwright + requests)
├── build_datasets.py                Turns raw JSON → CSV datasets (stdlib only)
├── auth.py                          Grabs a Bearer token from a live browser session
└── README.md
```

---

## Reproducing the results

### Prerequisites

```
Python 3.11+
numpy          (arrays only — required by the solver)
matplotlib     (plots — required if you generate figures)
```

The solver (`solver/`) uses **only** the Python standard library, NumPy, and
Matplotlib. `requests` and `playwright` are only needed to re-scrape AMIS data,
which you should not need to do — the processed CSVs are already in the repo.

Install the solver dependencies:

```bash
pip install numpy matplotlib
```

### Run the benchmark

```bash
cd solver
python evaluate.py
```

This prints a schedule for each method and a side-by-side comparison table:

```
  Method                              Nodes/Steps  BT/Restarts  Uphill    Time(s)  Solved
  Backtracking (MRV + LCV)                ...          ...        —         ...      YES
  Forward Checking (MRV + FC)             ...          ...        —         ...      YES
  Min-Conflicts (Local Search)            ...          ...        —         ...      YES
  Simulated Annealing                     ...          ...       ...        ...      YES
```

**Key parameters** (top of `evaluate.py`):

| Parameter | Default | Meaning |
|---|---|---|
| `year` | `3` | Curriculum year (1–4) |
| `term` | `"FS"` | First Semester (`FS`) or Second Semester (`SS`) |
| `track` | `"SP"` | `SP` (Special Problem) or `TH` (Thesis) |
| `require_open_slot` | `False` | `True` = only bundles with available seats |
| `allow_consent` | `False` | `True` = include sections requiring D/I consent |

---

## Data collection (optional — skip if CSVs are already in the repo)

The processed data is committed. You only need this section if you want to
re-scrape or collect additional subjects.

### Setup (Windows + WSL2)

**Step 1 — Confirm WSL 2 and display forwarding**

```bash
# In PowerShell:
wsl -l -v         # should show VERSION 2

# In Ubuntu:
echo $DISPLAY     # should print :0 or similar
```

If `$DISPLAY` is empty: run `wsl --update && wsl --shutdown` in PowerShell,
reopen Ubuntu, and check again.

**Step 2 — Work inside Linux, not `/mnt/c`**

```bash
mkdir -p ~/amis_project && cd ~/amis_project
cp /mnt/c/Users/<YOUR_WINDOWS_USERNAME>/Desktop/CMSC170/project/{auth.py,scrape.py,build_datasets.py} .
```

Or just `cd` into the cloned repo.

**Step 3 — Python environment**

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
python3 -m venv .venv && source .venv/bin/activate
pip install requests playwright
playwright install --with-deps chromium
```

Every new terminal needs `source .venv/bin/activate`.

**Step 4 — Scrape**

```bash
# Quick probe (~15 requests) — confirms the API works:
python scrape.py --probe

# CMSC only (267 sections, 6 pages):
python scrape.py --items 50

# All curriculum subjects (CMSC, MATH, STAT, HK, NSTP, GEs):
python scrape.py --set curriculum --items 50
```

Raw pages are saved to `data/raw/term_1261/<SUBJECT>/page_NNNN.json`.
Ctrl+C is safe — re-running skips already-saved pages.
The script waits 1–2 s between requests and **never** enlists or modifies data.

**Step 5 — Build datasets**

```bash
python build_datasets.py
```

Output goes to `data/datasets/term_1261/`. Requires stdlib only.

---

## Dataset summary (term 1261, CMSC only)

| Item | Count |
|---|---|
| Raw rows scraped | 267 |
| Total sections (incl. embedded LEC parents) | 294 |
| LEC / LAB | 179 / 115 |
| Sections with no meeting times (SP/thesis/practicum) | 130 |
| Schedulable sections | 164 |
| Instructors | 40 |
| Student bundles (total / usable) | 267 / 137 |
| Curriculum instances (year-term combinations) | 10 |

The 130 sections with no meetings are CMSC 190, 198, 200, 300, 400
(research/practicum). They have no fixed time and are excluded from the CSP.

---

## Libraries used and why

| Library | Where | Why |
|---|---|---|
| `requests`, `playwright` | `scrape.py`, `auth.py` | HTTP requests and browser login to AMIS (data collection only) |
| `csv`, `json`, `os`, `time`, `random`, `math` | everything else | Python stdlib — allowed by the project rules |
| `numpy` | solver (future plots) | Arrays and linear algebra — allowed |
| `matplotlib` | evaluation plots | Figures — allowed |

`pandas`, `scikit-learn`, `tensorflow`, `pytorch`, `keras`, and similar
ML/stats libraries are **not used anywhere** in the solver or preprocessing.

---

## Privacy

Instructor names and user IDs are removed in `scrape.py` before anything is
saved. Only the numeric `faculty_id` is kept in the data.

**Never commit** `amis_session*/`, any Bearer token, or personal enlistment
scripts. These are covered by `.gitignore`:

```
amis_session*/
main.py
__pycache__/
.venv/
*.token
```
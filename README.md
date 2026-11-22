# AMIS Student Schedule Builder — CMSC 170 Project

A **Constraint Satisfaction Problem (CSP)** solver that builds a conflict-free weekly
class schedule for a UPLB student, using data scraped from AMIS across **12 degree programs**.

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

The solver targets **Year 3, First Semester, SP track** by default
(change `--deg-prog`, `--year`, `--term`, and `--track` in `evaluate.py`).

---

## Degree Programs Supported

The solver covers **12 degree programs** from the UPLB BS curriculum (2018):

| Key | Program |
|---|---|
| `cmsc` | BS Computer Science |
| `stat` | BS Statistics |
| `math` | BS Mathematics |
| `amat` | BS Applied Mathematics |
| `ap` | BS Applied Physics |
| `chem` | BS Chemistry |
| `agch` | BS Agricultural Chemistry |
| `bio` | BS Biology |
| `coma` | BS Community Arts (Communication Arts) |
| `mst` | BS Management Science and Technology |
| `phlo` | BS Philosophy |
| `soc` | BS Sociology |

Each program maps to a `data/curriculum_<deg_prog>.csv` file describing the BS curriculum flowchart.

---

## Dataset Summary (Term 1261)

Drawn from `data/datasets/term_1261/summary.json`:

| Item | Count |
|---|---|
| Total sections (including embedded LEC parents) | 4,719 |
| LEC sections | 3,891 |
| LAB sections | 828 |
| Sections with no meeting times (SP/thesis/practicum) | 1,997 |
| Instructors | 771 |
| Student bundles (total / usable) | 4,466 / 2,475 |
| Curriculum instances (year-term combinations) | 10 |
| Subjects covered | 44 |

Courses without an offering this term (excluded from the CSP):
`CMSC 23`, `CMSC 57`, `CMSC 127`, `CMSC 128`, `CMSC 131`, `CMSC 137`,
`CMSC 173`, `CMSC 180`, `HK 13`

---

## Repository Layout

```
.
├── README.md
├── auth.py                          Grabs a Bearer token via a live browser session (Playwright)
├── scrape.py                        READ-ONLY AMIS collector (Playwright + requests)
├── build_datasets.py                Turns raw AMIS JSON → clean CSV/JSON datasets (stdlib only)
├── data/
│   ├── curriculum_<deg_prog>.csv    BS curriculum flowcharts for all 12 programs
│   ├── aggregate_results.csv        Shared benchmark results across all programs and years
│   ├── datasets/term_1261/
│   │   ├── sections.csv             One row per class section (LEC or LAB)
│   │   ├── meetings.csv             One row per (section, day); times in minutes after midnight
│   │   ├── summary.json             Dataset counts for the project page
│   │   ├── faculty/                 Dataset A — faculty load (reference only)
│   │   │   ├── assignments.csv
│   │   │   ├── instructors.csv
│   │   │   └── instance.json
│   │   └── student/                 Dataset B — student scheduler (used by the solver)
│   │       ├── bundles.csv          LEC+LAB bundles a student can enlist in
│   │       ├── coverage.csv         Which curriculum courses are offered this term
│   │       └── instances.json       One CSP instance per curriculum term
│   └── raw/term_1261/               Raw JSON pages from AMIS (read-only scrape)
├── solver/
│   ├── csp.py                       CSP class: loads data, builds domains, checks constraints
│   ├── backtracking.py              Method 1 — MRV + LCV backtracking
│   ├── forward_checking.py          Method 2 — MRV + Forward Checking
│   ├── min_conflicts.py             Method 3 — Min-Conflicts local search
│   ├── simulated_annealing.py       Method 4 — Simulated Annealing
│   ├── evaluate.py                  Runs all four methods and prints a comparison table
│   ├── plot_results.py              Generates per-program bar charts and saves a results CSV
│   ├── aggregate_results.py         Aggregates results across all programs into summary figures
│   ├── export_schedule.py           Runs all solvers and writes docs/schedules.json for the web viewer
│   └── check_curriculum.py          Audits curriculum CSVs for format errors and missing course coverage
├── docs/
│   ├── index.html                   GitHub Pages project page
│   ├── Schedule.html                Interactive schedule viewer
│   ├── schedules.json               Solver output for the web viewer (committed after export_schedule.py)
│   └── scheda/scheda.js             Schedule rendering library
├── figures/
│   ├── <deg_prog>/                  Per-program figures (fig1–fig5)
│   └── aggregate_figures/           Aggregate comparison figures across all programs
├── tasklog.md                       Member contribution log → [view →](tasklog.md)
└── tree.txt                         Full directory tree snapshot
```

---

## Reproducing the Results

### Prerequisites

```
Python 3.11+
numpy          (arrays — required by the solver)
matplotlib     (plots — required for figure generation)
```

The solver (`solver/`) uses **only** the Python standard library, NumPy, and Matplotlib.
`requests` and `playwright` are only needed to re-scrape AMIS data,
which you should not need to do — the processed CSVs are already in the repo.

Install solver dependencies:

```bash
pip install numpy matplotlib
```

---

### Run a Single Benchmark (one program, one year)

```bash
cd solver
python evaluate.py                                    # defaults: CMSC, Year 3, FS, SP
python evaluate.py --deg-prog stat --allow-consent
python evaluate.py --deg-prog math --year 2 --term SS --track TH --allow-consent
```

This prints the schedule found by each method and a side-by-side comparison table:

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
| `--deg-prog` | `cmsc` | Degree program key (see table above) |
| `--year` | `3` | Curriculum year (1–4) |
| `--term` | `FS` | First Semester (`FS`) or Second Semester (`SS`) |
| `--track` | `SP` | `SP` (Special Problem) or `TH` (Thesis) |
| `--allow-consent` | off | Include sections requiring D/I consent |

---

### Generate Per-Program Figures and Save Results

```bash
cd solver
python plot_results.py                              # CMSC, all years
python plot_results.py --deg-prog stat --allow-consent
```

Figures are saved to `figures/<deg_prog>/`. Results are appended to
`data/aggregate_results.csv` so you can run programs one at a time and accumulate results.

---

### Generate Aggregate Figures

After running `plot_results.py` for all programs:

```bash
cd solver
python aggregate_results.py
```

Output goes to `figures/aggregate_figures/`. This produces:

- `aggregate_01_nodes_explored.png` — mean nodes explored (exact methods)
- `aggregate_02_local_search_steps.png` — mean steps (local search)
- `aggregate_03_execution_time.png` — mean wall-clock time per method
- `aggregate_05_solution_success.png` — solution success rate
- `aggregate_07_overall_performance.png` — combined dual-axis overview
- `aggregate_08_pruning_intensity.png` — Forward Checking pruning per program
- `aggregate_pruning_summary.csv` — pruning summary table

---

### Update the Web Schedule Viewer

```bash
cd solver
python export_schedule.py                               # defaults: CMSC Y3 FS SP
python export_schedule.py --deg-prog stat --allow-consent
```

This writes `docs/schedules.json`. Commit that file to update the schedule on GitHub Pages.

---

### Audit Curriculum Files

```bash
cd solver
python check_curriculum.py
```

Checks all 12 `curriculum_<prog>.csv` files for format errors and reports which course codes
are not found in `sections.csv` (i.e., not offered this term or not yet scraped).

---

## Data Collection (Optional — Skip If CSVs Are Already in the Repo)

The processed dataset is committed. You only need this section to re-scrape or add subjects.

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

# All curriculum subjects for a specific program, e.g. BS CS:
python scrape.py --set cs --items 50

# All available subjects (large — confirm before running):
python scrape.py --set all_curricula --items 50
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

## Libraries Used and Why

| Library | Where | Why |
|---|---|---|
| `requests`, `playwright` | `scrape.py`, `auth.py` | HTTP requests and browser-based login to AMIS (data collection only) |
| `csv`, `json`, `os`, `time`, `random`, `math` | everything else | Python stdlib — allowed by project rules |
| `numpy` | solver, plotting | Arrays and linear algebra — allowed |
| `matplotlib` | `plot_results.py`, `aggregate_results.py` | Figures — allowed |

`pandas`, `scikit-learn`, `tensorflow`, `pytorch`, `keras`, and similar
ML/stats libraries are **not used anywhere** in the solver or preprocessing.

---

## Privacy

Instructor names and user IDs are removed in `scrape.py` before anything is saved to disk.
Only the numeric `faculty_id` is retained.

**Never commit** `amis_session*/`, any Bearer token, or personal enlistment scripts.
These are covered by `.gitignore`:

```
amis_session*/
main.py
__pycache__/
.venv/
*token*
```

---

## Task Log

A full record of each member's contributions per milestone is maintained in
**[tasklog.md](tasklog.md)**.

---

## Authors

| Name | Role |
|---|---|
| Hallare, Eu Dasein B. | Project Manager & Tech Lead |
| Gevaña, Maria Eliza P. | Research & QA Lead |
| Hernandez, John Denmark G. | Frontend & Web Lead |
| Tipan, Jiro Kristofer T. | Data Engineering & Analytics Lead |

---

## AI Tool Disclosure

Claude (Anthropic) was used during development as a debugging aid and to help generate boilerplate
code for `export_schedule.py`, `Schedule.html`, and portions of the project page. All core solver
logic — `csp.py`, `backtracking.py`, `forward_checking.py`, `min_conflicts.py`, and
`simulated_annealing.py` — was written by the group, with Claude occasionally consulted for
debugging assistance. Every line of code, whether written by the team or reviewed after generation,
was understood and verified by team members and can be explained during Q&A.
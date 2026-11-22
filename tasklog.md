# Task Log

**Project:** AMIS Student Schedule Builder — CMSC 170 Project  
**Description:** A Constraint Satisfaction Problem (CSP) solver that builds conflict-free weekly class schedules for UPLB students using data scraped from AMIS.

## Team & Roles

| Member | Role | Core Responsibilities |
| :--- | :--- | :--- |
| **Eu Hallare** | Project Manager & Tech Lead | System architecture, core CSP solver integration, evaluation and visualization pipelines, Git workflow, and project timeline |
| **Eliza Gevaña** | Research & QA Lead | Domain research, algorithm/logic design, edge-case testing, and validation |
| **John Denmark Hernandez** | Frontend & Web Lead | User interface (UI/UX), client-side logic, and web deployment |
| **Jiro Tipan** | Data Engineering & Analytics Lead | Data extraction/scraping, cleaning pipelines, benchmark evaluation, and results interpretation |

---

## Milestone 1

**Eu:**
- Brainstormed dataset and CSP methodology ideas
- Co-authored Milestone 1 documentation
- Initialized the GitHub repository
- Scraped Term 1261 course data (CMSC courses) from AMIS via API GET requests

**Eliza:**
- Brainstormed dataset and CSP methodology ideas
- Co-authored Milestone 1 documentation

**Denmark:**
- Brainstormed dataset and CSP methodology ideas
- Co-authored Milestone 1 documentation

**Jiro:**
- Brainstormed dataset and CSP methodology ideas
- Co-authored Milestone 1 documentation

---

## Milestone 2

**Eu:**
- Implemented and pushed `backtracking.py`, `csp.py`, and `evaluate.py`
- Updated `README.md` with setup instructions and usage guidelines
- Added the initial results code block

**Eliza:**
- Implemented and pushed `simulated_annealing.py`
- Initiated Milestone 2 documentation
- Documented the Current Methods and Data Loading & Preprocessing code

**Denmark:**
- Implemented and pushed `min_conflicts.py`
- Co-authored Milestone 2 documentation
- Wrote the train/test split and cross-validation plan explanation

**Jiro:**
- Implemented and pushed `forward_checking.py`
- Scraped course data for Terms 1252–1260 (partial dataset) as well as GE and HK courses
- Added the recommendation section to `evaluate.py`

---

## Milestone 3

**Eu:**
- Implemented and pushed `plot_results.py` and generated initial figures
- Co-authored the Milestone 3 report

**Eliza:**
- Led the writing of the Milestone 3 report
- Interpreted initial result figures for CMSC courses

**Denmark:**
- Co-authored the Milestone 3 report

**Jiro:**
- Scraped additional AMIS data for other degree programs (staged for Milestone 4)
- Co-authored the Milestone 3 report

---

## Milestone 4

**Eu:**
- Fixed formatting issues in `curriculum.csv` for AGCH, AMAT, AP, BIO, CHEM, MATH, and STAT
- Updated `csp.py`, `evaluate.py`, and `plot_results.py` to support the newly added degree programs
- Updated aggregate figures across all degree programs
- Helped in writing the content in Milestone 4
- Updated `aggregate_results.py` to match the guidelines properly
- Updated documentation of some files

**Eliza:**
- Generated result figures across all 11 degree programs (AGCH, AMAT, AP, BIO, CHEM, MATH, STAT, COMA, MST, PHLO, and SOC)
- Implemented and pushed `aggregate_results.py`
- Interpreted aggregate graphs and figures
- Co-created the final presentation slides
- Primarily wrote the content for Milestone 4

**Denmark:**
- Added `curriculum.csv` files for COMA, MST, PHLO, and SOC
- Wrote and pushed `check_curriculum.py` to audit remaining unscraped courses
- Developing the GitHub Pages site for the project
- Implemented `index.html` and `schedule.html`
- Helped in writing the content in Milestone 4

**Jiro:**
- Scraped course offerings for the newly added degree programs (COMA, MST, PHLO, and SOC)
- Interpreted aggregate graphs and figures
- Co-created the final presentation slides
- Primarily wrote the content for Milestone 4
- Updated documentation of some files
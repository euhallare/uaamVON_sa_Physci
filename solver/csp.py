"""
csp.py — AMIS Student Scheduler as a Constraint Satisfaction Problem

Terminology used throughout:
  slot     — a curriculum requirement (e.g. "Y3FS-1 → CMSC 124")
  bundle   — a (lec_class_id, lab_class_id) pair that satisfies a slot;
             standalone courses (no LAB) have lab_class_id = None
  meeting  — one timed block: (day, start_min, end_min)
  schedule — a dict {slot_name: bundle} representing a full or partial solution

Degree programs supported (--deg-prog / deg_prog parameter):
  cmsc, stat, math, amat, ap, chem, agch, bio
Each maps to data/curriculum_<deg_prog>.csv.

Soft constraints (optional, guide value ordering and score final schedules):
  - Time preference : penalise bundles that start too early or too late
  - Day preference  : penalise bundles that meet on avoided days, reward
                      bundles that meet on preferred days
  - Load balancing  : post-hoc metric only — measures how evenly class
                      minutes are spread across the week (not used to
                      guide search, only reported after solving)
"""

import csv
import os
import time
from typing import Optional


# Mapping from deg_prog key -> curriculum filename stem
DEG_PROG_MAP = {
    "cmsc":  "curriculum_cmsc.csv",
    "stat":  "curriculum_stat.csv",
    "math":  "curriculum_math.csv",
    "amat":  "curriculum_amat.csv",
    "ap":    "curriculum_ap.csv",
    "chem":  "curriculum_chem.csv",
    "agch":  "curriculum_agch.csv",
    "bio":   "curriculum_bio.csv",
    "mst":   "curriculum_mst.csv",
    "soc":   "curriculum_soc.csv",
    "phlo":  "curriculum_phlo.csv",
    "coma":  "curriculum_coma.csv",
}


def resolve_curriculum_path(deg_prog: str, data_dir: str) -> str:
    """
    Given a deg_prog key (e.g. 'cmsc') and the data/ directory,
    return the full path to the matching curriculum CSV.
    Raises ValueError for unknown keys.
    """
    key = deg_prog.strip().lower()
    if key not in DEG_PROG_MAP:
        raise ValueError(
            f"Unknown deg_prog '{deg_prog}'. "
            f"Choose one of: {', '.join(sorted(DEG_PROG_MAP))}"
        )
    return os.path.join(data_dir, DEG_PROG_MAP[key])


# ----------------------------------------------------------------- loaders

def load_sections(path: str) -> dict:
    """
    Returns {class_id (int): row_dict} for every row in sections.csv.
    Rows with type == 'embedded_parent' are LEC parents whose schedule
    appears only in meetings.csv under the same class_id.
    """
    sections = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = int(row["class_id"])
            row["class_id"] = cid
            row["parent_class_id"] = int(row["parent_class_id"]) if row["parent_class_id"] else None
            row["units"] = int(row["units"]) if row["units"] else 0
            row["max_size"] = int(row["max_size"]) if row["max_size"] else 0
            row["active_size"] = int(row["active_size"]) if row["active_size"] else 0
            sections[cid] = row
    return sections


def load_meetings(path: str) -> dict:
    """
    Returns {class_id (int): [(day, start_min, end_min), ...]}
    A class can have multiple meeting rows (e.g. TTh lectures).
    """
    meetings: dict = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = int(row["class_id"])
            block = (row["day"], int(row["start_min"]), int(row["end_min"]))
            meetings.setdefault(cid, []).append(block)
    return meetings


def load_curriculum(path: str) -> list:
    """
    Returns a list of curriculum row dicts, one per slot.
    """
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


# ----------------------------------------------------------------- bundle builder

def build_bundles(sections: dict, meetings: dict) -> dict:
    """
    Returns {course_code: [bundle, ...]} where each bundle is:
      {
        "lec_id":        int,
        "lab_id":        int | None,
        "lec_section":   str,
        "lab_section":   str | None,
        "meetings":      [(day, s, e), ...],   # combined LEC + LAB meeting blocks
        "lec_meetings":  [(day, s, e), ...],   # LEC-only blocks (for day penalty)
        "has_open_slot": bool,
        "consent":       str,                  # 'N', 'D', or 'I'
        "units":         int,
      }

    Strategy:
      - For courses with LEC+LAB: each LAB row is a bundle; its parent_class_id
        points to the LEC.  We merge meeting blocks from both.
      - For standalone courses (LEC only, SEM, SPR, etc.): the LEC itself is
        a bundle with lab_id = None.
    """
    # Index LAB rows by their parent (LEC) id
    labs_by_lec: dict = {}
    for cid, sec in sections.items():
        if sec["type"] in ("LAB", "RCT", "CPT"):
            pid = sec["parent_class_id"]
            labs_by_lec.setdefault(pid, []).append(sec)

    bundles: dict = {}

    for cid, sec in sections.items():
        if sec["source"] != "row":
            continue  # skip embedded_parent duplicates

        course = sec["course_code"]

        if sec["type"] in ("LAB", "RCT", "CPT"):
            # LAB-based bundle
            lec_id = sec["parent_class_id"]
            lec = sections.get(lec_id)
            if lec is None:
                continue

            lec_meetings = meetings.get(lec_id, [])
            lab_meetings = meetings.get(cid, [])
            combined = lec_meetings + lab_meetings

            lab_open = sec["active_size"] < sec["max_size"] if sec["max_size"] > 0 else False
            consent = sec["consent"] if sec["consent"] not in ("", "N") else lec["consent"]

            bundle = {
                "lec_id":        lec_id,
                "lab_id":        cid,
                "lec_section":   lec["section"],
                "lab_section":   sec["section"],
                "meetings":      combined,
                "lec_meetings":  lec_meetings,   # kept separate for day-preference scoring
                "has_open_slot": lab_open,
                "consent":       consent,
                "units":         sec["units"],
            }
            bundles.setdefault(course, []).append(bundle)

        elif sec["type"] not in ("LAB", "RCT", "CPT") and sec["parent_class_id"] is None:
            # Standalone bundle (LEC, SEM, etc.) — skip non-schedulable types
            if sec["type"] in ("THE", "SPR", "PRA", "DSR", "STO"):
                continue
            lec_meetings = meetings.get(cid, [])
            lec_open = sec["active_size"] < sec["max_size"] if sec["max_size"] > 0 else False
            consent = sec["consent"]

            bundle = {
                "lec_id":        cid,
                "lab_id":        None,
                "lec_section":   sec["section"],
                "lab_section":   None,
                "meetings":      lec_meetings,
                "lec_meetings":  lec_meetings,
                "has_open_slot": lec_open,
                "consent":       consent,
                "units":         sec["units"],
            }
            bundles.setdefault(course, []).append(bundle)

    return bundles


# ----------------------------------------------------------------- conflict checker

def meetings_overlap(m1: list, m2: list) -> bool:
    """
    Returns True if any meeting block in m1 overlaps with any in m2.
    Two blocks overlap if they share the same day AND their time ranges
    intersect (not just touch).
    """
    for (d1, s1, e1) in m1:
        for (d2, s2, e2) in m2:
            if d1 == d2 and s1 < e2 and s2 < e1:
                return True
    return False


# ----------------------------------------------------------------- CSP class

class SchedulerCSP:
    """
    Variables  : curriculum slot names for the target year/term/track
                 e.g. ["Y3FS-1", "Y3FS-2", ..., "Y3FS-6"]

    Domains    : for each variable, a list of valid bundles
                 (open, no consent, correct course code)

    Hard constraint : no two assigned bundles may have overlapping meetings

    Soft constraints (optional — guide value ordering, scored post-hoc):
      time  — penalise bundles whose LEC starts before time_prefer_after
               or starts at/after time_penalty_after (minutes after midnight)
      day   — penalise LEC meetings on avoid_days; reward meetings on
               preferred_days (LAB days are intentionally not penalised
               because students rarely control which lab section they enter)
      load  — post-hoc only: std-dev of per-day class minutes across the week;
               lower = more evenly spread schedule

    Parameters
    ----------
    sections_path      : path to datasets/term_XXXX/sections.csv
    meetings_path      : path to datasets/term_XXXX/meetings.csv
    curriculum_path    : explicit path to a curriculum CSV (overrides deg_prog)
    deg_prog           : degree program key, e.g. 'cmsc', 'stat', 'math'
    data_dir           : root data/ directory (used only with deg_prog)
    year / term / track: which curriculum slice to solve
    require_open_slot  : if True, only bundles with available seats
    allow_consent      : if True, include D/I consent sections

    Soft-constraint parameters (all optional — set to None to disable):
    time_prefer_after  : minutes after midnight; prefer classes that start
                         at or after this time (default 7*60 = 7 AM)
    time_penalty_after : minutes after midnight; penalise classes starting
                         at or after this time (default 17*60 = 5 PM)
    avoid_days         : set of day codes to penalise on LEC meetings
                         (default {"S"} — avoid Saturday)
    preferred_days     : set of day codes to reward on LEC meetings
                         (default None — no preference)
    soft_weights       : dict with keys "time" and "day" controlling penalty
                         magnitudes (default {"time": 1.0, "day": 1.0})
    """

    def __init__(
        self,
        sections_path: str,
        meetings_path: str,
        curriculum_path: Optional[str] = None,
        deg_prog: Optional[str] = None,
        data_dir: Optional[str] = None,
        year: int = 3,
        term: str = "FS",
        track: str = "SP",
        completed_courses: Optional[set] = None,
        require_open_slot: bool = True,
        allow_consent: bool = False,
        # --- soft constraint parameters ---
        time_prefer_after: Optional[int]  = 7 * 60,    # 7 AM
        time_penalty_after: Optional[int] = 17 * 60,   # 5 PM
        avoid_days: Optional[set]         = None,       # filled below
        preferred_days: Optional[set]     = None,
        soft_weights: Optional[dict]      = None,
    ):
        self.year  = year
        self.term  = term
        self.track = track
        self.completed    = completed_courses or set()
        self.require_open = require_open_slot
        self.allow_consent = allow_consent

        # non-CMSC programs require dept consent for their own core courses
        self.deg_prog = (deg_prog or "").lower()
        if not allow_consent and self.deg_prog not in ("cmsc", ""):
            allow_consent = True
            self.allow_consent = True

        # soft constraint config
        self.time_prefer_after  = time_prefer_after   # start >= this is good
        self.time_penalty_after = time_penalty_after  # start >= this is bad
        self.avoid_days     = avoid_days if avoid_days is not None else {"S"}
        self.preferred_days = preferred_days or set()
        self.soft_weights   = soft_weights or {"time": 1.0, "day": 1.0}

        # resolve curriculum path
        if curriculum_path is None:
            if deg_prog is None:
                raise ValueError("Provide either curriculum_path or deg_prog.")
            if data_dir is None:
                data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
            curriculum_path = resolve_curriculum_path(deg_prog, data_dir)

        self.curriculum_path = curriculum_path

        # load raw data
        sections   = load_sections(sections_path)
        meetings   = load_meetings(meetings_path)
        curriculum = load_curriculum(curriculum_path)
        all_bundles = build_bundles(sections, meetings)

        # build variables and domains
        self.variables: list   = []
        self.domains: dict     = {}   # slot_name -> [bundle, ...]
        self.slot_courses: dict = {}  # slot_name -> course_code (for display)

        for row in curriculum:
            if int(row["year"]) != year:
                continue
            if row["term"] != term:
                continue
            if row["track"] not in ("ALL", track):
                continue

            slot    = row["slot"]
            options = [o.strip() for o in row["options"].split("|")]

            if any(o in ("GE", "ELECTIVE", "NSTP") for o in options):
                continue
            if row["kind"] == "PE":
                continue

            valid_bundles = []
            for course_code in options:
                for b in all_bundles.get(course_code, []):
                    if not allow_consent and b["consent"] in ("D", "I"):
                        continue
                    if require_open_slot and not b["has_open_slot"]:
                        continue
                    valid_bundles.append(b)

            if valid_bundles:
                self.variables.append(slot)
                self.domains[slot]       = valid_bundles
                self.slot_courses[slot]  = "/".join(options)

        # pre-compute neighbors (fully connected)
        self.neighbors: dict = {
            v: [u for u in self.variables if u != v]
            for v in self.variables
        }

        self._curriculum_rows = curriculum

    # ----------------------------------------------------------------- hard constraint

    def is_consistent(self, slot: str, bundle: dict, assignment: dict) -> bool:
        """True if assigning bundle to slot doesn't conflict with any assigned bundle."""
        for other_slot, other_bundle in assignment.items():
            if other_slot == slot:
                continue
            if meetings_overlap(bundle["meetings"], other_bundle["meetings"]):
                return False
        return True

    def num_conflicts(self, slot: str, bundle: dict, assignment: dict) -> int:
        """Number of assigned bundles that conflict with bundle. Used by min-conflicts."""
        count = 0
        for other_slot, other_bundle in assignment.items():
            if other_slot == slot:
                continue
            if meetings_overlap(bundle["meetings"], other_bundle["meetings"]):
                count += 1
        return count

    #soft constraints

    def score_bundle(self, bundle: dict) -> float:
        """
        Soft penalty for a single bundle (lower = better, 0 = ideal).

        Applies time and day preferences to LEC meetings only.
        LAB meeting days are intentionally excluded because students
        generally cannot choose which lab section they get — penalising
        LAB days would unfairly disadvantage courses that have
        Tuesday/Thursday labs with no MWF alternative.

        Time penalty rules:
          - If time_prefer_after is set, every LEC meeting that starts
            before it adds a proportional penalty.
          - If time_penalty_after is set, every LEC meeting that starts
            at or after it adds a proportional penalty.

        Day penalty rules:
          - LEC meeting on an avoided day  → +2.0 * w["day"] per block
          - LEC meeting not on a preferred day (when preferred_days is set)
            → +0.5 * w["day"] per block
        """
        penalty = 0.0
        wt = self.soft_weights.get("time", 1.0)
        wd = self.soft_weights.get("day",  1.0)

        for day, start, _end in bundle.get("lec_meetings", bundle["meetings"]):
            #time preference
            if self.time_prefer_after is not None and start < self.time_prefer_after:
                #penalise by how many minutes too early (per hour)
                penalty += wt * (self.time_prefer_after - start) / 60.0

            if self.time_penalty_after is not None and start >= self.time_penalty_after:
                #penalise by how many minutes past the threshold (per hour)
                penalty += wt * (start - self.time_penalty_after) / 60.0

            #day preference
            if self.avoid_days and day in self.avoid_days:
                penalty += wd * 2.0

            if self.preferred_days and day not in self.preferred_days:
                penalty += wd * 0.5

        return penalty

    def score_assignment(self, assignment: dict) -> dict:
        """
        Score a complete assignment on all soft dimensions.
        Returns a dict so callers can report individual components.

        Keys returned:
          "time_day"    — sum of score_bundle() across all assigned slots
          "load_stddev" — std-dev of per-day class minutes (lower = more balanced)
          "total"       — time_day + load_stddev (normalised to same scale)

        Call this only on a complete (solved) assignment.
        Passing None raises ValueError so callers must guard.
        """
        if assignment is None:
            raise ValueError("score_assignment called with None assignment.")

        #time + day component
        time_day = sum(self.score_bundle(b) for b in assignment.values())

        #load balancing: std-dev of class minutes per day across the week
        day_minutes: dict = {}
        for bundle in assignment.values():
            for day, start, end in bundle["meetings"]:
                day_minutes[day] = day_minutes.get(day, 0) + (end - start)

        if day_minutes:
            vals  = list(day_minutes.values())
            mean  = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            load_stddev = variance ** 0.5 / 60.0   # convert to hours for readability
        else:
            load_stddev = 0.0

        return {
            "time_day":    round(time_day,    4),
            "load_stddev": round(load_stddev, 4),
            "total":       round(time_day + load_stddev, 4),
        }

    #diagnostics

    def summary(self):
        deg = f" ({self.deg_prog.upper()})" if self.deg_prog else ""
        print(f"\n{'='*60}")
        print(f"  AMIS Scheduler CSP{deg}  —  Year {self.year}, Term {self.term}, Track {self.track}")
        print(f"  allow_consent={self.allow_consent}")
        print(f"  Soft constraints:")
        print(f"    time_prefer_after  = {self.time_prefer_after} min  "
              f"({self.time_prefer_after//60}:{self.time_prefer_after%60:02d} AM/PM)"
              if self.time_prefer_after is not None else "    time_prefer_after  = disabled")
        print(f"    time_penalty_after = {self.time_penalty_after} min  "
              f"({self.time_penalty_after//60}:{self.time_penalty_after%60:02d} AM/PM)"
              if self.time_penalty_after is not None else "    time_penalty_after = disabled")
        print(f"    avoid_days         = {self.avoid_days or 'none'}")
        print(f"    preferred_days     = {self.preferred_days or 'none'}")
        print(f"    soft_weights       = {self.soft_weights}")
        print(f"{'='*60}")
        print(f"  Variables : {len(self.variables)}")
        for v in self.variables:
            d = self.domains[v]
            print(f"    {v:12s}  ({self.slot_courses[v]:20s})  {len(d):3d} bundles")

        #report slots that were silently dropped (no bundles found)
        dropped = []
        for row in self._curriculum_rows:
            if int(row["year"]) != self.year:
                continue
            if row["term"] != self.term:
                continue
            if row["track"] not in ("ALL", self.track):
                continue
            slot = row["slot"]
            if slot in self.variables:
                continue
            options = [o.strip() for o in row["options"].split("|")]
            if any(o in ("GE", "ELECTIVE", "NSTP") for o in options):
                continue
            if row["kind"] == "PE":
                continue
            dropped.append((slot, "/".join(options)))

        if dropped:
            print(f"\n  WARNING — {len(dropped)} slot(s) dropped (no bundles in dataset):")
            for s, c in dropped:
                print(f"    {s:12s}  {c}")
            print("  Fix: correct the course code in the curriculum CSV,")
            print("       or scrape + rebuild datasets for the missing subject.")

        print(f"{'='*60}\n")
"""
csp.py — AMIS Student Scheduler as a Constraint Satisfaction Problem

Terminology used throughout:
  slot     — a curriculum requirement (e.g. "Y3FS-1 → CMSC 124")
  bundle   — a (lec_class_id, lab_class_id) pair that satisfies a slot;
             standalone courses (no LAB) have lab_class_id = None
  meeting  — one timed block: (day, start_min, end_min)
  schedule — a dict {slot_name: bundle} representing a full or partial solution
"""

import csv
import time
from typing import Optional



#1.  Raw data loaders

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



#2.  Bundle builder
def build_bundles(sections: dict, meetings: dict) -> dict:
    """
    Returns {course_code: [bundle, ...]} where each bundle is:
      {
        "lec_id":   int,
        "lab_id":   int | None,
        "section":  str,          # e.g. "C" for LEC, "C-1L" for the LAB
        "meetings": [(day, s, e), ...],   # combined LEC + LAB meeting blocks
        "has_open_slot": bool,
        "consent":  str,          # 'N', 'D', or 'I'
      }

    Strategy:
      - For courses with LEC+LAB: each LAB row is a bundle; its parent_class_id
        points to the LEC.  We merge meeting blocks from both.
      - For standalone courses (LEC only, SEM, SPR, etc.): the LEC itself is
        a bundle with lab_id = None.
    """
    #Index LAB rows by their parent (LEC) id
    labs_by_lec: dict = {}
    for cid, sec in sections.items():
        if sec["type"] == "LAB":
            pid = sec["parent_class_id"]
            labs_by_lec.setdefault(pid, []).append(sec)

    bundles: dict = {}

    for cid, sec in sections.items():
        if sec["source"] != "row":
            continue  #skip embedded_parent duplicates

        course = sec["course_code"]

        if sec["type"] == "LAB":
            # --- LAB-based bundle ---
            lec_id = sec["parent_class_id"]
            lec = sections.get(lec_id)
            if lec is None:
                continue

            lec_meetings = meetings.get(lec_id, [])
            lab_meetings = meetings.get(cid, [])
            combined = lec_meetings + lab_meetings

            #Open slot: LAB must have room; LEC capacity is shared so we
            #just require the LAB to be not full (LEC over-enrollment is
            #the registrar's problem, not ours).
            lab_open = sec["active_size"] < sec["max_size"] if sec["max_size"] > 0 else False
            #consent: take the stricter of LEC vs LAB (usually same)
            consent = sec["consent"] if sec["consent"] not in ("", "N") else lec["consent"]

            bundle = {
                "lec_id":        lec_id,
                "lab_id":        cid,
                "lec_section":   lec["section"],
                "lab_section":   sec["section"],
                "meetings":      combined,
                "has_open_slot": lab_open,
                "consent":       consent,
                "units":         sec["units"],
            }
            bundles.setdefault(course, []).append(bundle)

        elif sec["type"] not in ("LAB",) and sec["parent_class_id"] is None:
            #Standalone bundle (LEC, SEM, SPR, THE, PRA) ---
            # Skip thesis/SPR/PRA — not schedulable in a timetable sense
            if sec["type"] in ("THE", "SPR", "PRA"):
                continue
            #Skip consent-required courses for the student scheduler
            #(they can't self-enlist anyway)
            lec_meetings = meetings.get(cid, [])
            lec_open = sec["active_size"] < sec["max_size"] if sec["max_size"] > 0 else False
            consent = sec["consent"]

            bundle = {
                "lec_id":        cid,
                "lab_id":        None,
                "lec_section":   sec["section"],
                "lab_section":   None,
                "meetings":      lec_meetings,
                "has_open_slot": lec_open,
                "consent":       consent,
                "units":         sec["units"],
            }
            bundles.setdefault(course, []).append(bundle)

    return bundles



#3.  Conflict checker
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


# 4.  CSP Problem class
class SchedulerCSP:
    """
    Variables  : curriculum slot names for the target year/term
                 e.g. ["Y3FS-1", "Y3FS-2", ..., "Y3FS-6"]

    Domains    : for each variable, a list of valid bundles
                 (open, no consent, correct course code)

    Constraints: binary — no two assigned bundles may have overlapping meetings
    """

    def __init__(
        self,
        sections_path: str,
        meetings_path: str,
        curriculum_path: str,
        year: int = 3,
        term: str = "FS",
        track: str = "SP",
        completed_courses: Optional[set] = None,
        require_open_slot: bool = True,
        allow_consent: bool = False,
    ):
        self.year = year
        self.term = term
        self.track = track
        self.completed = completed_courses or set()
        self.require_open = require_open_slot
        self.allow_consent = allow_consent

        #Load raw data
        sections = load_sections(sections_path)
        meetings = load_meetings(meetings_path)
        curriculum = load_curriculum(curriculum_path)
        all_bundles = build_bundles(sections, meetings)

        #Build variables and domains
        self.variables: list = []
        self.domains: dict = {}       # slot_name -> [bundle, ...]
        self.slot_courses: dict = {}  # slot_name -> course_code (for display)

        for row in curriculum:
            if int(row["year"]) != year:
                continue
            if row["term"] != term:
                continue
            if row["track"] not in ("ALL", track):
                continue

            slot = row["slot"]
            #options can be "CMSC 124" or "HK 12|HK 13" (pick any)
            options = [o.strip() for o in row["options"].split("|")]

            #Skip GE / ELECTIVE / NSTP / PE slots — not in CMSC data (CURRENTLY, LALAGYAN KO NA LANG)
            if any(o in ("GE", "ELECTIVE", "NSTP") for o in options):
                continue
            #PE: skip HK courses (not in dataset)
            if row["kind"] == "PE":
                continue

            #Gather all bundles for this slot across all option codes
            valid_bundles = []
            for course_code in options:
                for b in all_bundles.get(course_code, []):
                    #Filter: consent
                    if not allow_consent and b["consent"] in ("D", "I"):
                        continue
                    #Filter: open slot
                    if require_open_slot and not b["has_open_slot"]:
                        continue
                    valid_bundles.append(b)

            if valid_bundles:
                self.variables.append(slot)
                self.domains[slot] = valid_bundles
                self.slot_courses[slot] = "/".join(options)

        #Pre-compute neighbors (all pairs — fully connected graph since
        #any two courses can conflict in time)
        self.neighbors: dict = {
            v: [u for u in self.variables if u != v]
            for v in self.variables
        }

    def is_consistent(self, slot: str, bundle: dict, assignment: dict) -> bool:
        """
        Returns True if assigning `bundle` to `slot` doesn't conflict
        with any already-assigned bundle.
        """
        for other_slot, other_bundle in assignment.items():
            if other_slot == slot:
                continue
            if meetings_overlap(bundle["meetings"], other_bundle["meetings"]):
                return False
        return True

    def num_conflicts(self, slot: str, bundle: dict, assignment: dict) -> int:
        """
        Returns the number of currently assigned bundles that conflict
        with `bundle`.  Used by min-conflicts.
        """
        count = 0
        for other_slot, other_bundle in assignment.items():
            if other_slot == slot:
                continue
            if meetings_overlap(bundle["meetings"], other_bundle["meetings"]):
                count += 1
        return count

    def summary(self):
        print(f"\n{'='*55}")
        print(f"  AMIS Scheduler CSP  —  Year {self.year}, Term {self.term}, Track {self.track}")
        print(f"{'='*55}")
        print(f"  Variables : {len(self.variables)}")
        for v in self.variables:
            d = self.domains[v]
            print(f"    {v:12s}  ({self.slot_courses[v]:20s})  {len(d):3d} bundles")
        print(f"{'='*55}\n")
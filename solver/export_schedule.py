"""
export_schedule.py — Run all 4 solvers and write docs/schedules.json
                     for the GitHub Pages schedule viewer.

Run this whenever you want to update the schedule on your project page:
    python export_schedule.py
    python export_schedule.py --deg-prog stat --allow-consent

Output: docs/schedules.json  (commit this file to trigger a page update)
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from csp import SchedulerCSP, DEG_PROG_MAP
import backtracking
import forward_checking
import min_conflicts
import simulated_annealing

BASE     = os.path.join(os.path.dirname(__file__), "..", "data")
SECTIONS = os.path.join(BASE, "datasets", "term_1261", "sections.csv")
MEETINGS = os.path.join(BASE, "datasets", "term_1261", "meetings.csv")

# Map internal day codes -> scheda.js day codes
# scheda.js uses: M T W Th F S  (same as your CSP!)
DAY_MAP = {"M": "M", "T": "T", "W": "W", "Th": "Th", "F": "F", "S": "S"}

TERM_LABELS = {"FS": "1st Semester", "SS": "2nd Semester"}


def minutes_to_hhmm(m: int) -> str:
    return f"{m // 60}:{m % 60:02d}"


def bundle_to_scheda_entries(slot: str, bundle: dict, slot_courses: dict) -> list:
    """
    Convert one CSP bundle into a list of scheda.js course objects.
    scheda.js wants one entry per (day-group, time) block, not one per day.
    We group meetings that share the same time range into one entry with
    combined day string (e.g. "MWF").
    """
    course_code = slot_courses[slot].split("/")[0].strip()
    sec = bundle["lec_section"]
    if bundle.get("lab_section"):
        sec += f"+{bundle['lab_section']}"

    # Group by (start, end) -> list of days
    groups: dict = {}
    for day, s, e in bundle["meetings"]:
        key = (s, e)
        groups.setdefault(key, []).append(DAY_MAP.get(day, day))

    entries = []
    day_order = {"M": 0, "T": 1, "W": 2, "Th": 3, "F": 4, "S": 5}

    for (s, e), days in groups.items():
        sorted_days = sorted(days, key=lambda d: day_order.get(d, 9))
        time_str = f"{minutes_to_hhmm(s)}-{minutes_to_hhmm(e)}"

        # scheda.js needs one entry per day in the group
        for day in sorted_days:
            entries.append({
                "day":        day,
                "time":       time_str,
                "courseCode": course_code,
                "section":    sec,
                "room":       "",   # not in CSP data; leave blank
                "slot":       slot,
            })

    return entries


def solution_to_scheda(csp: SchedulerCSP, solution: dict) -> list:
    if solution is None:
        return []
    entries = []
    for slot in csp.variables:
        bundle = solution.get(slot)
        if bundle:
            entries.extend(bundle_to_scheda_entries(slot, bundle, csp.slot_courses))
    return entries


def run_all(csp: SchedulerCSP) -> list:
    solvers = [
        ("Backtracking (MRV + LCV)",    lambda: backtracking.solve(csp)),
        ("Forward Checking (MRV + FC)", lambda: forward_checking.solve(csp)),
        ("Min-Conflicts",               lambda: min_conflicts.solve(csp, max_steps=50_000, max_restarts=30)),
        ("Simulated Annealing",         lambda: simulated_annealing.solve(csp, max_steps=50_000, max_restarts=20)),
    ]

    results = []
    for name, fn in solvers:
        print(f"  Running {name} ...", end=" ", flush=True)
        r = fn()
        solved = r["solution"] is not None
        print("SOLVED" if solved else "NO SOLUTION", f"({r['time_seconds']:.4f}s)")
        results.append({
            "method":         name,
            "solved":         solved,
            "time_seconds":   round(r["time_seconds"], 4),
            "nodes_explored": r.get("nodes_explored", r.get("steps", None)),
            "backtracks":     r.get("backtracks",     r.get("restarts", None)),
            "accepted_worse": r.get("accepted_worse", None),
            "pruned_values":  r.get("pruned_values",  None),
            "entries":        solution_to_scheda(csp, r["solution"]),
        })
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deg-prog", default="cmsc", choices=list(DEG_PROG_MAP))
    ap.add_argument("--year",  type=int, default=3)
    ap.add_argument("--term",  default="FS", choices=["FS", "SS"])
    ap.add_argument("--track", default="SP")
    ap.add_argument("--allow-consent", action="store_true")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "docs", "schedules.json"))
    args = ap.parse_args()

    print(f"Building CSP — {args.deg_prog.upper()} Y{args.year} {args.term} {args.track} ...")
    csp = SchedulerCSP(
        sections_path     = SECTIONS,
        meetings_path     = MEETINGS,
        deg_prog          = args.deg_prog,
        data_dir          = BASE,
        year              = args.year,
        term              = args.term,
        track             = args.track,
        require_open_slot = False,
        allow_consent     = args.allow_consent,
    )
    csp.summary()

    if not csp.variables:
        print("No schedulable slots found.")
        return

    results = run_all(csp)

    payload = {
        "meta": {
            "deg_prog":   args.deg_prog.upper(),
            "year":       args.year,
            "term":       args.term,
            "term_label": TERM_LABELS.get(args.term, args.term),
            "track":      args.track,
            "n_vars":     len(csp.variables),
            "courses":    {slot: csp.slot_courses[slot] for slot in csp.variables},
        },
        "results": results,
    }

    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\nWritten to: {out_path}")
    print("Commit docs/schedules.json to update your GitHub Pages schedule viewer.")


if __name__ == "__main__":
    main()
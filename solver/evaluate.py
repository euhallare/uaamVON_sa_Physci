"""
evaluate.py — Run all 3 CSP methods on the same problem instance
              and print a comparison table.

Usage:
    cd amis_scheduler/solver
    python evaluate.py

Defaults to Year 3, First Sem, SP track — a typical 3rd-year student
who has completed all Y1 and Y2 requirements.
"""

import sys
import os
import time

#Allow running from any directory
sys.path.insert(0, os.path.dirname(__file__))

from csp import SchedulerCSP
import backtracking
import forward_checking
import min_conflicts
import simulated_annealing


#paths (relative to this file)
BASE        = os.path.join(os.path.dirname(__file__), "..", "data")
SECTIONS    = os.path.join(BASE, "datasets", "term_1261", "sections.csv")
MEETINGS    = os.path.join(BASE, "datasets", "term_1261", "meetings.csv")
CURRICULUM  = os.path.join(BASE, "curriculum.csv")



#pretty printers
DAY_ORDER = {"M": 0, "T": 1, "W": 2, "Th": 3, "F": 4, "S": 5}

def fmt_meetings(meetings: list) -> str:
    """Format meeting blocks as a compact string, e.g. 'MWF 10:00-13:00'."""
    if not meetings:
        return "TBA"
    #group by time range, collect days
    groups: dict = {}
    for day, s, e in meetings:
        key = (s, e)
        groups.setdefault(key, []).append(day)
    parts = []
    for (s, e), days in sorted(groups.items(), key=lambda x: x[0][0]):
        sorted_days = sorted(days, key=lambda d: DAY_ORDER.get(d, 9))
        day_str = "".join(sorted_days)
        parts.append(f"{day_str} {s//60:02d}:{s%60:02d}-{e//60:02d}:{e%60:02d}")
    return "  |  ".join(parts)


def print_solution(csp: SchedulerCSP, solution: dict):
    if solution is None:
        print("  *** No solution found ***")
        return
    total_units = 0
    print(f"\n  {'Slot':<12} {'Course':<22} {'Section':<10} {'Schedule'}")
    print(f"  {'-'*12} {'-'*22} {'-'*10} {'-'*35}")
    for slot in csp.variables:
        b = solution[slot]
        course = csp.slot_courses[slot]
        sec = f"{b['lec_section']}" + (f"+{b['lab_section']}" if b['lab_section'] else "")
        sched = fmt_meetings(b["meetings"])
        print(f"  {slot:<12} {course:<22} {sec:<10} {sched}")
        total_units += b["units"]
    print(f"\n  Total units scheduled: {total_units}")


def print_comparison(results: list):
    print(f"\n{'='*80}")
    print(f"  PERFORMANCE COMPARISON")
    print(f"{'='*80}")
    print(f"  {'Method':<35} {'Nodes/Steps':>11} {'BT/Restarts':>12} {'Uphill':>7} {'Time(s)':>9} {'Solved':>7}")
    print(f"  {'-'*35} {'-'*11} {'-'*12} {'-'*7} {'-'*9} {'-'*7}")
    for r in results:
        nodes  = r.get("nodes_explored", r.get("steps", "—"))
        backs  = r.get("backtracks",     r.get("restarts", "—"))
        uphill = r.get("accepted_worse", "—")
        t      = f"{r['time_seconds']:.4f}"
        solved = "YES" if r["solution"] is not None else "NO"
        print(f"  {r['method']:<35} {str(nodes):>11} {str(backs):>12} {str(uphill):>7} {t:>9} {solved:>7}")
    print(f"{'='*80}\n")



#Main
def main():
    # --- Problem instance ---
    # A 3rd-year student in their First Semester, SP track.
    # We allow sections that are full (require_open_slot=False) so the
    # solver has enough domain values to be interesting; in a real
    # deployment you'd set require_open_slot=True.
    print("Loading CSP problem...")
    csp = SchedulerCSP(
        sections_path   = SECTIONS,
        meetings_path   = MEETINGS,
        curriculum_path = CURRICULUM,
        year            = 2,
        term            = "FS",
        track           = "SP",
        require_open_slot = False,   #tignan note above
        allow_consent     = False,
    )
    csp.summary()

    if not csp.variables:
        print("No schedulable slots found. Check your data paths or filters.")
        return

    results = []

    # --- Method 1: Backtracking (MRV + LCV) ---
    print("Running Method 1: Backtracking (MRV + LCV)...")
    r1 = backtracking.solve(csp)
    results.append(r1)
    print(f"  Done in {r1['time_seconds']:.4f}s — "
          f"{'SOLVED' if r1['solution'] else 'NO SOLUTION'}")
    print_solution(csp, r1["solution"])

    # --- Method 2: Forward Checking ---
    print("\nRunning Method 2: Forward Checking (MRV + FC)...")
    r2 = forward_checking.solve(csp)
    results.append(r2)
    print(f"  Done in {r2['time_seconds']:.4f}s — "
          f"{'SOLVED' if r2['solution'] else 'NO SOLUTION'}")
    print_solution(csp, r2["solution"])

    # --- Method 3: Min-Conflicts ---
    print("\nRunning Method 3: Min-Conflicts (Local Search)...")
    r3 = min_conflicts.solve(csp, max_steps=50_000, max_restarts=30)
    results.append(r3)
    fc = r3.get("final_conflicts", 0)
    print(f"  Done in {r3['time_seconds']:.4f}s — "
          f"{'SOLVED' if r3['solution'] else f'NO SOLUTION ({fc} conflicts remain)'}")
    print_solution(csp, r3["solution"])

    # --- Method 4: Simulated Annealing ---
    print("\nRunning Method 4: Simulated Annealing...")
    r4 = simulated_annealing.solve(csp, max_steps=50_000, max_restarts=20)
    results.append(r4)
    fc = r4.get("final_conflicts", 0)
    print(f"  Done in {r4['time_seconds']:.4f}s — "
          f"{'SOLVED' if r4['solution'] else f'NO SOLUTION ({fc} conflicts remain)'}")
    print_solution(csp, r4["solution"])

    #comparison table
    print_comparison(results)


if __name__ == "__main__":
    main()
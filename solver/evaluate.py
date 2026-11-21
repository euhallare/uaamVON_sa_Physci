"""
DOCUMENTATION FOR evaluate.py

evaluate.py — Run all 4 CSP methods on the same problem instance
              and print a comparison table.

Usage:
    python evaluate.py #defaults: cmsc, year 3, FS, SP
    python evaluate.py --deg-prog stat --allow-consent
    python evaluate.py --deg-prog math --year 2 --term SS --track TH --allow-consent

Arguments:
    --deg-prog        Degree program: cmsc, stat, math, amat, ap, chem, agch, bio
                      (default: cmsc)
    --year            Curriculum year 1–4 (default: 3)
    --term            FS or SS (default: FS)
    --track           Track code, e.g. SP or TH (default: SP)
    --allow-consent   Include sections requiring D/I consent (needed for non-CMSC programs)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from csp import SchedulerCSP, DEG_PROG_MAP
import backtracking
import forward_checking
import min_conflicts
import simulated_annealing


#paths (relative to this file)
BASE     = os.path.join(os.path.dirname(__file__), "..", "data")
SECTIONS = os.path.join(BASE, "datasets", "term_1261", "sections.csv")
MEETINGS = os.path.join(BASE, "datasets", "term_1261", "meetings.csv")



DAY_ORDER = {"M": 0, "T": 1, "W": 2, "Th": 3, "F": 4, "S": 5}


def fmt_meetings(meetings: list) -> str:
    """Format meeting blocks as a compact string, e.g. 'MWF 10:00-13:00'."""
    if not meetings:
        return "TBA"
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

    #Recommendation
    print("  RECOMMENDATION")
    print(f"  {'-'*60}")

    def is_exact(r):
        return "nodes_explored" in r

    solved_runs = [r for r in results if r["solution"] is not None]
    if not solved_runs:
        print("  No method found a valid schedule.")
        print("  The problem may have no conflict-free solution.\n")
        return

    exact = [r for r in solved_runs if is_exact(r)]
    pool  = exact if exact else solved_runs
    best  = min(pool, key=lambda r: (r.get("nodes_explored", r.get("steps", 0)),
                                     r["time_seconds"]))

    print(f"  Best method : {best['method']}")
    if exact:
        print("  Reason      : exact (guaranteed to find a solution if one exists)")
        print("                and explored the fewest nodes among exact methods.")
    else:
        print("  Reason      : only local search solved it; fewest steps chosen.")

    local = [r for r in solved_runs if not is_exact(r)]
    if exact and local:
        fastest_local = min(local, key=lambda r: r.get("steps", 0))
        print(f"  Note        : {fastest_local['method']} also solved it in "
              f"{fastest_local.get('steps', '—')} steps, but local search")
        print("                has no guarantee of finding a solution on every run.")

    failed = [r["method"] for r in results if r["solution"] is None]
    if failed:
        print(f"  Failed      : {', '.join(failed)}")
    print(f"{'='*80}\n")


#main function

def main():
    #argparse setup
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    
    #arguments
    ap.add_argument("--deg-prog", default="cmsc",
                    choices=list(DEG_PROG_MAP),
                    help="Degree program (default: cmsc)")
    ap.add_argument("--year",  type=int, default=3,
                    help="Curriculum year 1–4 (default: 3)")
    ap.add_argument("--term",  default="FS", choices=["FS", "SS"],
                    help="Semester: FS or SS (default: FS)")
    ap.add_argument("--track", default="SP",
                    help="Track code e.g. SP or TH (default: SP)")
    ap.add_argument("--allow-consent", action="store_true",
                    help="Include sections requiring D/I consent "
                        "(auto-enabled for non-CMSC programs)")
    args = ap.parse_args()

    print(f"Loading CSP problem — deg_prog={args.deg_prog.upper()}, "
          f"year={args.year}, term={args.term}, track={args.track}, "
          f"allow_consent={args.allow_consent} ...")

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
        print("No schedulable slots found. Check your data paths or filters.")
        return

    results = []

    # Method 1: Backtracking (MRV + LCV)
    print("Running Method 1: Backtracking (MRV + LCV)...")
    r1 = backtracking.solve(csp)
    results.append(r1)
    print(f"  Done in {r1['time_seconds']:.4f}s — "
          f"{'SOLVED' if r1['solution'] else 'NO SOLUTION'}")
    print_solution(csp, r1["solution"])

    # Method 2: Forward Checking
    print("\nRunning Method 2: Forward Checking (MRV + FC)...")
    r2 = forward_checking.solve(csp)
    results.append(r2)
    print(f"  Done in {r2['time_seconds']:.4f}s — "
          f"{'SOLVED' if r2['solution'] else 'NO SOLUTION'}")
    print_solution(csp, r2["solution"])

    # Method 3: Min-Conflicts
    print("\nRunning Method 3: Min-Conflicts (Local Search)...")
    r3 = min_conflicts.solve(csp, max_steps=50_000, max_restarts=30)
    results.append(r3)
    fc = r3.get("final_conflicts", 0)
    print(f"  Done in {r3['time_seconds']:.4f}s — "
          f"{'SOLVED' if r3['solution'] else f'NO SOLUTION ({fc} conflicts remain)'}")
    print_solution(csp, r3["solution"])

    # Method 4: Simulated Annealing
    print("\nRunning Method 4: Simulated Annealing...")
    r4 = simulated_annealing.solve(csp, max_steps=50_000, max_restarts=20)
    results.append(r4)
    fc = r4.get("final_conflicts", 0)
    print(f"  Done in {r4['time_seconds']:.4f}s — "
          f"{'SOLVED' if r4['solution'] else f'NO SOLUTION ({fc} conflicts remain)'}")
    print_solution(csp, r4["solution"])

    print_comparison(results)


if __name__ == "__main__":
    main()
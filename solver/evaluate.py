"""
evaluate.py — Run all 4 CSP methods on the same problem instance
              and print a comparison table.

Usage:
    python evaluate.py                                           # defaults
    python evaluate.py --deg-prog stat --allow-consent
    python evaluate.py --deg-prog math --year 2 --term SS --track TH

Soft constraint flags (all optional):
    --time-prefer-after   HH:MM   prefer classes starting at or after this time (default 07:00)
    --time-penalty-after  HH:MM   penalise classes starting at or after this time (default 17:00)
    --avoid-saturday              penalise LEC meetings on Saturday (default: on)
    --no-avoid-saturday           disable Saturday penalty
    --prefer-mwf                  reward LEC meetings on Mon/Wed/Fri
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


#helpers

def parse_hhmm(s: str) -> int:
    #convert 'HH:MM' string to minutes after midnight
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        raise argparse.ArgumentTypeError(f"Time must be HH:MM, got '{s}'")


def fmt_meetings(meetings: list) -> str:
    #format meeting blocks as a compact string, like 'MWF 10:00-13:00'
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


def fmt_soft(soft: dict | None) -> str:
    #format soft score dict as a compact string for the comparison table
    if soft is None:
        return "N/A"
    return (f"td={soft['time_day']:.2f}  "
            f"lb={soft['load_stddev']:.2f}  "
            f"tot={soft['total']:.2f}")

#printers
def print_solution(csp: SchedulerCSP, solution: dict):
    if solution is None:
        print("  *** No solution found ***")
        return
    total_units = 0
    print(f"\n  {'Slot':<12} {'Course':<22} {'Section':<12} {'Schedule'}")
    print(f"  {'-'*12} {'-'*22} {'-'*12} {'-'*35}")
    for slot in csp.variables:
        b      = solution[slot]
        course = csp.slot_courses[slot]
        sec    = b["lec_section"] + (f"+{b['lab_section']}" if b["lab_section"] else "")
        sched  = fmt_meetings(b["meetings"])
        print(f"  {slot:<12} {course:<22} {sec:<12} {sched}")
        total_units += b["units"]
    print(f"\n  Total units scheduled: {total_units}")


def print_comparison(results: list, csp: SchedulerCSP):
    W = 100
    print(f"\n{'='*W}")
    print(f"  PERFORMANCE COMPARISON")
    print(f"{'='*W}")
    print(f"  {'Method':<35} {'Nodes/Steps':>11} {'BT/Rest':>8} "
          f"{'Uphill':>7} {'Time(s)':>9} {'Solved':>7}  {'Soft Score (td / lb / tot)':}")
    print(f"  {'-'*35} {'-'*11} {'-'*8} {'-'*7} {'-'*9} {'-'*7}  {'-'*35}")

    for r in results:
        nodes  = r.get("nodes_explored", r.get("steps", "—"))
        backs  = r.get("backtracks",     r.get("restarts", "—"))
        uphill = r.get("accepted_worse", "—")
        t      = f"{r['time_seconds']:.4f}"
        solved = "YES" if r["solution"] is not None else "NO"
        soft   = fmt_soft(r.get("soft_score"))
        print(f"  {r['method']:<35} {str(nodes):>11} {str(backs):>8} "
              f"{str(uphill):>7} {t:>9} {solved:>7}  {soft}")

    print(f"{'='*W}\n")

    #soft score explanation
    print("  SOFT SCORE KEY")
    print(f"  {'-'*60}")
    print("  td  = time+day penalty  (lower = better time/day preferences met)")
    print("  lb  = load balance stddev in hours  (lower = more evenly spread week)")
    print("  tot = td + lb  (overall soft quality; lower = better)")
    print()

    #best method recommendation
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
    best_efficiency = min(pool, key=lambda r: (
        r.get("nodes_explored", r.get("steps", 0)), r["time_seconds"]
    ))
    best_quality = min(
        solved_runs,
        key=lambda r: r["soft_score"]["total"] if r.get("soft_score") else float("inf")
    )

    print(f"  Most efficient : {best_efficiency['method']}")
    print(f"  Best soft score: {best_quality['method']}  "
          f"(tot={best_quality['soft_score']['total']:.2f})")

    if exact:
        print("  Note: exact methods (Backtracking, Forward Checking) guarantee")
        print("        a solution if one exists. Local search methods do not.")

    failed = [r["method"] for r in results if r["solution"] is None]
    if failed:
        print(f"  Failed: {', '.join(failed)}")

    print(f"{'='*W}\n")


#main function

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)

    ap.add_argument("--deg-prog", default="cmsc", choices=list(DEG_PROG_MAP))
    ap.add_argument("--year",  type=int, default=3)
    ap.add_argument("--term",  default="FS", choices=["FS", "SS"])
    ap.add_argument("--track", default="SP")
    ap.add_argument("--allow-consent", action="store_true")

    #soft constraint flags
    ap.add_argument("--time-prefer-after",  type=parse_hhmm, default=7*60,
                    metavar="HH:MM",
                    help="Prefer classes starting at or after this time (default 07:00)")
    ap.add_argument("--time-penalty-after", type=parse_hhmm, default=17*60,
                    metavar="HH:MM",
                    help="Penalise classes starting at or after this time (default 17:00)")
    ap.add_argument("--no-avoid-saturday", dest="avoid_saturday",
                    action="store_false", default=True,
                    help="Disable Saturday avoidance penalty")
    ap.add_argument("--prefer-mwf", action="store_true", default=False,
                    help="Reward LEC meetings on Mon/Wed/Fri")

    args = ap.parse_args()

    avoid_days     = {"S"} if args.avoid_saturday else set()
    preferred_days = {"M", "W", "F"} if args.prefer_mwf else set()

    print(f"Loading CSP — {args.deg_prog.upper()} Y{args.year} {args.term} {args.track}")
    print(f"  time_prefer_after  = {args.time_prefer_after//60:02d}:{args.time_prefer_after%60:02d}")
    print(f"  time_penalty_after = {args.time_penalty_after//60:02d}:{args.time_penalty_after%60:02d}")
    print(f"  avoid_days         = {avoid_days or 'none'}")
    print(f"  preferred_days     = {preferred_days or 'none'}")

    csp = SchedulerCSP(
        sections_path      = SECTIONS,
        meetings_path      = MEETINGS,
        deg_prog           = args.deg_prog,
        data_dir           = BASE,
        year               = args.year,
        term               = args.term,
        track              = args.track,
        require_open_slot  = False,
        allow_consent      = args.allow_consent,
        time_prefer_after  = args.time_prefer_after,
        time_penalty_after = args.time_penalty_after,
        avoid_days         = avoid_days,
        preferred_days     = preferred_days,
        soft_weights       = {"time": 1.0, "day": 1.0},
    )
    csp.summary()

    if not csp.variables:
        print("No schedulable slots found. Check your data paths or filters.")
        return

    results = []

    print("Running Method 1: Backtracking (MRV + LCV)...")
    r1 = backtracking.solve(csp)
    results.append(r1)
    print(f"  Done in {r1['time_seconds']:.4f}s — "
          f"{'SOLVED' if r1['solution'] else 'NO SOLUTION'}")
    print_solution(csp, r1["solution"])

    print("\nRunning Method 2: Forward Checking (MRV + FC)...")
    r2 = forward_checking.solve(csp)
    results.append(r2)
    print(f"  Done in {r2['time_seconds']:.4f}s — "
          f"{'SOLVED' if r2['solution'] else 'NO SOLUTION'}")
    print_solution(csp, r2["solution"])

    print("\nRunning Method 3: Min-Conflicts (Local Search)...")
    r3 = min_conflicts.solve(csp, max_steps=50_000, max_restarts=30)
    results.append(r3)
    fc = r3.get("final_conflicts", 0)
    print(f"  Done in {r3['time_seconds']:.4f}s — "
          f"{'SOLVED' if r3['solution'] else f'NO SOLUTION ({fc} conflicts remain)'}")
    print_solution(csp, r3["solution"])

    print("\nRunning Method 4: Simulated Annealing...")
    r4 = simulated_annealing.solve(csp, max_steps=50_000, max_restarts=20)
    results.append(r4)
    fc = r4.get("final_conflicts", 0)
    print(f"  Done in {r4['time_seconds']:.4f}s — "
          f"{'SOLVED' if r4['solution'] else f'NO SOLUTION ({fc} conflicts remain)'}")
    print_solution(csp, r4["solution"])

    print_comparison(results, csp)


if __name__ == "__main__":
    main()
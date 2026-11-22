"""
backtracking.py — Method 1: Backtracking Search with MRV + LCV

Algorithm:
  Standard recursive backtracking.
  Variable ordering : Minimum Remaining Values (MRV) — always pick the
                      unassigned slot with the fewest valid bundles remaining.
  Value ordering    : Least-Constraining Value (LCV) extended with soft
                      preference — prefer the bundle that (a) rules out the
                      fewest options for other unassigned slots, and (b) best
                      satisfies time and day preferences when hard costs tie.

Soft constraints:
  score_bundle() from the CSP is used as a tiebreaker inside the LCV
  ordering key.  Hard cost (eliminated neighbor options) always dominates;
  soft penalty only breaks ties so the solver still guarantees a valid schedule.

Metrics collected:
  - nodes_explored  : number of (slot, bundle) pairs tried
  - backtracks      : number of times we had to undo an assignment
  - time_seconds    : wall-clock time
"""

import time
from csp import SchedulerCSP


def select_unassigned_variable(csp: SchedulerCSP, assignment: dict) -> str:
    """MRV: pick the slot with the smallest remaining consistent domain."""
    unassigned = [v for v in csp.variables if v not in assignment]

    def remaining(v):
        return sum(
            1 for b in csp.domains[v]
            if csp.is_consistent(v, b, assignment)
        )

    return min(unassigned, key=remaining)


def order_domain_values(csp: SchedulerCSP, slot: str, assignment: dict) -> list:
    """
    LCV + soft preference ordering.

    Primary key  : hard LCV cost — how many neighbor domain values does
                   assigning this bundle eliminate?  (lower = less constraining)
    Secondary key: soft penalty from score_bundle() — time and day preferences.
                   (lower = better)

    Using a tuple (hard, soft) as the sort key means soft only breaks ties
    in hard cost, preserving the correctness guarantee of LCV.
    """
    def sort_key(bundle):
        # hard cost: count eliminated options across unassigned neighbors
        hard = 0
        for neighbor in csp.neighbors[slot]:
            if neighbor in assignment:
                continue
            for nb in csp.domains[neighbor]:
                if not csp.is_consistent(neighbor, nb, {**assignment, slot: bundle}):
                    hard += 1

        # soft cost: time + day penalty for this bundle's LEC meetings
        soft = csp.score_bundle(bundle)

        return (hard, soft)

    return sorted(csp.domains[slot], key=sort_key)


def backtrack(csp: SchedulerCSP, assignment: dict, stats: dict) -> dict | None:
    if len(assignment) == len(csp.variables):
        return assignment

    slot = select_unassigned_variable(csp, assignment)

    for bundle in order_domain_values(csp, slot, assignment):
        stats["nodes_explored"] += 1

        if csp.is_consistent(slot, bundle, assignment):
            assignment[slot] = bundle
            result = backtrack(csp, assignment, stats)
            if result is not None:
                return result
            del assignment[slot]
            stats["backtracks"] += 1

    return None


def solve(csp: SchedulerCSP) -> dict:
    
    #Returns a result dict:
    #  {
    #   "solution":       {slot: bundle} or None,
    #   "nodes_explored": int,
    #   "backtracks":     int,
    #   "time_seconds":   float,
    #   "method":         "Backtracking (MRV + LCV)",
    # }
    stats = {"nodes_explored": 0, "backtracks": 0}
    t0 = time.perf_counter()
    solution = backtrack(csp, {}, stats)
    elapsed = time.perf_counter() - t0

    soft = csp.score_assignment(solution) if solution is not None else None

    return {
        "solution":       solution,
        "nodes_explored": stats["nodes_explored"],
        "backtracks":     stats["backtracks"],
        "soft_score":     soft,
        "time_seconds":   elapsed,
        "method":         "Backtracking (MRV + LCV)",
    }
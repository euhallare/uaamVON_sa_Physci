"""
backtracking.py — Method 1: Backtracking Search with MRV heuristic

Algorithm:
  Standard recursive backtracking.
  Variable ordering: Minimum Remaining Values (MRV) — always pick the
  unassigned slot with the fewest valid bundles remaining.  Ties broken
  by degree (most constrained variable first).
  Value ordering: least-constraining value (LCV) — prefer the bundle that
  rules out the fewest options for other unassigned slots.

Metrics collected:
  - nodes_explored  : number of (slot, bundle) pairs tried
  - backtracks      : number of times we had to undo an assignment
  - time_seconds    : wall-clock time
"""

import time
from csp import SchedulerCSP


def select_unassigned_variable(csp: SchedulerCSP, assignment: dict) -> str:
    #MRV: pick the slot with the smallest remaining domain.
    unassigned = [v for v in csp.variables if v not in assignment]
    #count how many bundles are still consistent for each unassigned variable
    def remaining(v):
        return sum(
            1 for b in csp.domains[v]
            if csp.is_consistent(v, b, assignment)
        )
    return min(unassigned, key=remaining)


def order_domain_values(csp: SchedulerCSP, slot: str, assignment: dict) -> list:
    """
    LCV: order bundles by how many choices they eliminate for neighbors.
    Lower = less constraining = preferred.
    """
    def conflicts_caused(bundle):
        total = 0
        for neighbor in csp.neighbors[slot]:
            if neighbor in assignment:
                continue
            for nb in csp.domains[neighbor]:
                if not csp.is_consistent(neighbor, nb, {**assignment, slot: bundle}):
                    total += 1
        return total

    return sorted(csp.domains[slot], key=conflicts_caused)


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
            # backtrack
            del assignment[slot]
            stats["backtracks"] += 1

    return None


def solve(csp: SchedulerCSP) -> dict:
    """
    Returns a result dict:
      {
        "solution":       {slot: bundle} or None,
        "nodes_explored": int,
        "backtracks":     int,
        "time_seconds":   float,
        "method":         "Backtracking (MRV + LCV)",
      }
    """
    stats = {"nodes_explored": 0, "backtracks": 0}
    t0 = time.perf_counter()
    solution = backtrack(csp, {}, stats)
    elapsed = time.perf_counter() - t0

    return {
        "solution":       solution,
        "nodes_explored": stats["nodes_explored"],
        "backtracks":     stats["backtracks"],
        "time_seconds":   elapsed,
        "method":         "Backtracking (MRV + LCV)",
    }
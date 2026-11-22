"""
forward_checking.py — Method 2: Backtracking + Forward Checking

Extends plain backtracking by maintaining *reduced domains*:
after each assignment, prune every bundle from neighboring (unassigned)
slots that would immediately conflict with the newly assigned bundle.
If any domain is wiped out, backtrack immediately without going deeper.

This is strictly stronger than Method 1: it detects dead-ends earlier.

Soft constraints:
  Within each slot's (pruned) domain, bundles are sorted by score_bundle()
  before the solver tries them.  This means Forward Checking tries
  time/day-preferred bundles first, so the first valid solution found
  tends to be a higher-quality one — without any extra backtracking cost.

Metrics collected:
  - nodes_explored  : (slot, bundle) pairs tried
  - backtracks      : failed assignments
  - pruned_values   : total bundle-domain entries eliminated by FC
  - time_seconds    : wall-clock time
"""

import time
from csp import SchedulerCSP


def select_unassigned_variable(csp: SchedulerCSP, assignment: dict,
                                current_domains: dict) -> str:
    """MRV on the *current* (pruned) domains, not the original ones."""
    unassigned = [v for v in csp.variables if v not in assignment]
    return min(unassigned, key=lambda v: len(current_domains[v]))


def _prune_domains(bundle: dict, neighbor_domain: list) -> list:
    """Remove bundles from neighbor_domain that conflict with bundle."""
    from csp import meetings_overlap
    return [nb for nb in neighbor_domain
            if not meetings_overlap(nb["meetings"], bundle["meetings"])]


def fc_backtrack(csp: SchedulerCSP, assignment: dict,
                 current_domains: dict, stats: dict) -> dict | None:

    if len(assignment) == len(csp.variables):
        return assignment

    slot = select_unassigned_variable(csp, assignment, current_domains)

    # Sort current domain by soft preference before trying bundles.
    # score_bundle() uses LEC meetings only, so this never disadvantages
    # courses that have forced Tuesday/Thursday lab days.
    ordered = sorted(current_domains[slot], key=lambda b: csp.score_bundle(b))

    for bundle in ordered:
        stats["nodes_explored"] += 1

        if not csp.is_consistent(slot, bundle, assignment):
            continue

        # Forward check: build pruned domains for all unassigned neighbors
        new_domains = {
            v: (list(current_domains[v]) if v != slot else [bundle])
            for v in csp.variables
        }
        domain_wiped = False

        for neighbor in csp.neighbors[slot]:
            if neighbor in assignment:
                continue
            pruned = _prune_domains(bundle, new_domains[neighbor])
            stats["pruned_values"] += len(new_domains[neighbor]) - len(pruned)
            new_domains[neighbor] = pruned
            if len(pruned) == 0:
                domain_wiped = True
                break

        if domain_wiped:
            stats["backtracks"] += 1
            continue

        assignment[slot] = bundle
        result = fc_backtrack(csp, assignment, new_domains, stats)
        if result is not None:
            return result

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
        "pruned_values":  int,
        "soft_score":     dict  (time_day, load_stddev, total) or None,
        "time_seconds":   float,
        "method":         str,
      }
    """
    stats = {"nodes_explored": 0, "backtracks": 0, "pruned_values": 0}
    current_domains = {v: list(csp.domains[v]) for v in csp.variables}

    t0 = time.perf_counter()
    solution = fc_backtrack(csp, {}, current_domains, stats)
    elapsed = time.perf_counter() - t0

    soft = csp.score_assignment(solution) if solution is not None else None

    return {
        "solution":       solution,
        "nodes_explored": stats["nodes_explored"],
        "backtracks":     stats["backtracks"],
        "pruned_values":  stats["pruned_values"],
        "soft_score":     soft,
        "time_seconds":   elapsed,
        "method":         "Forward Checking (MRV + FC)",
    }
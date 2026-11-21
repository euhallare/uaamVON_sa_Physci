"""
forward_checking.py — Method 2: Backtracking + Forward Checking

Extends plain backtracking by maintaining *reduced domains*:
after each assignment, prune every bundle from neighboring (unassigned)
slots that would immediately conflict with the newly assigned bundle.
If any domain is wiped out, backtrack immediately without going deeper.

This is strictly stronger than Method 1: it detects dead-ends earlier.

Metrics collected:
  - nodes_explored  : (slot, bundle) pairs tried
  - backtracks      : failed assignments
  - pruned_values   : total bundle-domain entries eliminated by FC
  - time_seconds    : wall-clock time
"""

import time
import copy
from csp import SchedulerCSP


def select_unassigned_variable(csp: SchedulerCSP, assignment: dict,
                                current_domains: dict) -> str:
    #MRV on the *current* (pruned) domains, not the original ones.
    unassigned = [v for v in csp.variables if v not in assignment]
    return min(unassigned, key=lambda v: len(current_domains[v]))


def forward_check(csp: SchedulerCSP, slot: str, bundle: dict,
                  assignment: dict, current_domains: dict) -> tuple[bool, dict]:
    """
    For every unassigned neighbor of `slot`, remove any bundle that
    conflicts with the just-assigned bundle.

    Returns (consistent: bool, new_domains: dict).
    If consistent is False, one neighbor's domain was wiped — backtrack.
    """
    new_domains = copy.deepcopy(current_domains)
    pruned = 0

    for neighbor in csp.neighbors[slot]:
        if neighbor in assignment:
            continue
        new_domains[neighbor] = [
            nb for nb in new_domains[neighbor]
            if not (
                #would this neighbor bundle conflict with the new assignment?
                any(True for _ in [None]
                    if __import__("csp").meetings_overlap(nb["meetings"], bundle["meetings"]))
            )
        ]
        pruned += len(current_domains[neighbor]) - len(new_domains[neighbor])

        if len(new_domains[neighbor]) == 0:
            return False, new_domains, pruned

    return True, new_domains, pruned


#cleaner version without the ugly import trick
def _prune_domains(bundle: dict, neighbor_domain: list) -> list:
    from csp import meetings_overlap
    return [nb for nb in neighbor_domain
            if not meetings_overlap(nb["meetings"], bundle["meetings"])]


def fc_backtrack(csp: SchedulerCSP, assignment: dict,
                 current_domains: dict, stats: dict) -> dict | None:

    if len(assignment) == len(csp.variables):
        return assignment

    slot = select_unassigned_variable(csp, assignment, current_domains)

    for bundle in current_domains[slot]:
        stats["nodes_explored"] += 1

        if not csp.is_consistent(slot, bundle, assignment):
            continue

        #Forward check: build pruned domains
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
    #Returns a result dict with solution and metrics.
    stats = {"nodes_explored": 0, "backtracks": 0, "pruned_values": 0}
    #Start with full original domains
    current_domains = {v: list(csp.domains[v]) for v in csp.variables}

    t0 = time.perf_counter()
    solution = fc_backtrack(csp, {}, current_domains, stats)
    elapsed = time.perf_counter() - t0

    return {
        "solution":       solution,
        "nodes_explored": stats["nodes_explored"],
        "backtracks":     stats["backtracks"],
        "pruned_values":  stats["pruned_values"],
        "time_seconds":   elapsed,
        "method":         "Forward Checking (MRV + FC)",
    }
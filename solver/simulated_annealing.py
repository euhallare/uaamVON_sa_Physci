"""
simulated_annealing.py — Method 4: Simulated Annealing
Local search method that starts with a random complete assignment and iteratively improves it.

Cooling schedule: geometric  →  T = T_start * alpha^step
  T_start = 1.0  (initial temperature)
  alpha   = 0.9995 (cooling rate; close to 1 = slow cooling)
  T_min   = 0.001  (stop cooling, freeze)

Objective function: number of conflicting pairs in the assignment.
Goal: drive this to 0.

Metrics collected:
  - steps           : total iterations
  - restarts        : times we reset to a new random start
  - accepted_worse  : how many uphill moves were accepted
  - final_conflicts : remaining conflict pairs (0 = solved)
  - time_seconds    : wall-clock time
"""

import math
import random
import time
from csp import SchedulerCSP, meetings_overlap



#helpers
def total_conflicts(assignment: dict) -> int:
    """Count the number of conflicting (slot_a, slot_b) pairs."""
    slots = list(assignment.keys())
    count = 0
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            if meetings_overlap(assignment[slots[i]]["meetings"],
                                assignment[slots[j]]["meetings"]):
                count += 1
    return count


def conflicts_for_slot(slot: str, bundle: dict, assignment: dict) -> int:
    #Count how many other slots conflict with this (slot, bundle) pair.
    count = 0
    for other_slot, other_bundle in assignment.items():
        if other_slot == slot:
            continue
        if meetings_overlap(bundle["meetings"], other_bundle["meetings"]):
            count += 1
    return count


#core SA solver

def sa_run(csp: SchedulerCSP, rng: random.Random,
           T_start: float, alpha: float, T_min: float,
           max_steps: int, stats: dict) -> dict | None:
    """
    One SA run from a fresh random start.
    Returns the assignment if solved (0 conflicts), else None.
    """
    #random complete initial assignment
    assignment = {v: rng.choice(csp.domains[v]) for v in csp.variables}
    current_cost = total_conflicts(assignment)

    T = T_start

    for step in range(max_steps):
        stats["steps"] += 1

        if current_cost == 0:
            return assignment  # solved

        #cool down
        if T > T_min:
            T *= alpha

        #pick a random slot and a random new bundle for it
        slot = rng.choice(csp.variables)
        new_bundle = rng.choice(csp.domains[slot])

        #compute change in cost if we make this move
        old_conflicts = conflicts_for_slot(slot, assignment[slot], assignment)
        new_conflicts = conflicts_for_slot(slot, new_bundle, assignment)
        delta = new_conflicts - old_conflicts  # negative = improvement

        #accept if better, or probabilistically if worse
        if delta <= 0:
            assignment[slot] = new_bundle
            current_cost += delta
        else:
            #accept worse move with probability exp(-delta / T)
            if T > 0 and rng.random() < math.exp(-delta / T):
                assignment[slot] = new_bundle
                current_cost += delta
                stats["accepted_worse"] += 1

    return None  # did not converge in this run



#public interface
def solve(csp: SchedulerCSP,
          T_start: float  = 1.0,
          alpha: float    = 0.9995,
          T_min: float    = 0.001,
          max_steps: int  = 50_000,
          max_restarts: int = 20,
          seed: int       = 99) -> dict:
    """
    Returns a result dict with solution and metrics.
    """
    rng = random.Random(seed)
    stats = {"steps": 0, "restarts": 0,
             "accepted_worse": 0, "final_conflicts": 0}
    t0 = time.perf_counter()

    for restart in range(max_restarts):
        if restart > 0:
            stats["restarts"] += 1

        solution = sa_run(csp, rng, T_start, alpha, T_min, max_steps, stats)

        if solution is not None:
            elapsed = time.perf_counter() - t0
            return {
                "solution":        solution,
                "steps":           stats["steps"],
                "restarts":        stats["restarts"],
                "accepted_worse":  stats["accepted_worse"],
                "final_conflicts": 0,
                "time_seconds":    elapsed,
                "method":          "Simulated Annealing",
            }

    #all restarts exhausted
    elapsed = time.perf_counter() - t0
    #return best assignment from last run for diagnostics
    assignment = {v: rng.choice(csp.domains[v]) for v in csp.variables}
    remaining = total_conflicts(assignment)
    stats["final_conflicts"] = remaining
    return {
        "solution":        None,
        "steps":           stats["steps"],
        "restarts":        stats["restarts"],
        "accepted_worse":  stats["accepted_worse"],
        "final_conflicts": remaining,
        "time_seconds":    elapsed,
        "method":          "Simulated Annealing",
    }
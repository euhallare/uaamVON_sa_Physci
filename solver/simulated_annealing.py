"""
simulated_annealing.py — Method 4: Simulated Annealing

Local search that starts with a random complete assignment and iteratively
improves it by accepting both improving and (sometimes) worsening moves.

Cooling schedule: geometric  →  T = T_start * alpha^step
  T_start = 1.0    (initial temperature)
  alpha   = 0.9995 (cooling rate; close to 1 = slow cooling)
  T_min   = 0.001  (freeze threshold)

Cost function (what SA minimises):
  total_cost = hard_cost * HARD_WEIGHT + soft_cost

  hard_cost  — number of conflicting bundle pairs (must reach 0 to solve)
  soft_cost  — sum of score_bundle() across all slots (time + day preference)
  HARD_WEIGHT — large constant (100) so SA always prioritises feasibility
                over soft quality; soft only guides moves once hard = 0

Soft constraints:
  SA naturally handles the soft/hard trade-off through the cost function.
  Unlike backtracking, it can escape local minima via uphill moves, so it
  tends to find better soft scores than greedy exact methods — at the cost
  of no completeness guarantee.

Metrics collected:
  - steps           : total iterations
  - restarts        : times we reset to a new random start
  - accepted_worse  : uphill moves accepted (shows SA exploration)
  - final_conflicts : remaining conflict pairs (0 = solved)
  - time_seconds    : wall-clock time
"""

import math
import random
import time
from csp import SchedulerCSP, meetings_overlap

# Hard conflicts are weighted much higher than soft so SA still treats
# feasibility as the primary objective.
HARD_WEIGHT = 100.0


# ----------------------------------------------------------------- helpers

def total_hard_conflicts(assignment: dict) -> int:
    """Count the number of conflicting (slot_a, slot_b) pairs."""
    slots = list(assignment.keys())
    count = 0
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            if meetings_overlap(assignment[slots[i]]["meetings"],
                                assignment[slots[j]]["meetings"]):
                count += 1
    return count


def total_cost(csp: SchedulerCSP, assignment: dict) -> float:
    """
    Combined hard + soft cost for the full assignment.
    SA minimises this value.
    """
    hard = total_hard_conflicts(assignment)
    soft = sum(csp.score_bundle(b) for b in assignment.values())
    return hard * HARD_WEIGHT + soft


def slot_cost(csp: SchedulerCSP, slot: str, bundle: dict,
              assignment: dict) -> float:
    """
    Marginal cost contribution of one (slot, bundle) pair.
    Used to compute delta efficiently without re-scoring everything.

    hard component: how many other slots conflict with this bundle?
    soft component: score_bundle() for this bundle's LEC meetings
    """
    hard = sum(
        1 for other_slot, other_bundle in assignment.items()
        if other_slot != slot
        and meetings_overlap(bundle["meetings"], other_bundle["meetings"])
    )
    soft = csp.score_bundle(bundle)
    return hard * HARD_WEIGHT + soft


# ----------------------------------------------------------------- core SA run

def sa_run(csp: SchedulerCSP, rng: random.Random,
           T_start: float, alpha: float, T_min: float,
           max_steps: int, stats: dict) -> dict | None:
    """
    One SA run from a fresh random start.
    Returns the assignment dict if solved (0 hard conflicts), else None.
    """
    # Random complete initial assignment
    assignment    = {v: rng.choice(csp.domains[v]) for v in csp.variables}
    current_cost  = total_cost(csp, assignment)
    T             = T_start

    for _step in range(max_steps):
        stats["steps"] += 1

        if total_hard_conflicts(assignment) == 0:
            return assignment  # solved

        # Cool down
        if T > T_min:
            T *= alpha

        # Propose a move: pick a random slot and a random new bundle
        slot       = rng.choice(csp.variables)
        new_bundle = rng.choice(csp.domains[slot])

        # Delta cost: difference in this slot's marginal cost
        old_c = slot_cost(csp, slot, assignment[slot], assignment)
        new_c = slot_cost(csp, slot, new_bundle,       assignment)
        delta = new_c - old_c   # negative = improvement

        # Accept if better, or probabilistically if worse
        if delta <= 0:
            assignment[slot] = new_bundle
            current_cost    += delta
        elif T > 0 and rng.random() < math.exp(-delta / T):
            assignment[slot] = new_bundle
            current_cost    += delta
            stats["accepted_worse"] += 1

    return None  # did not converge in this run


# ----------------------------------------------------------------- public interface

def solve(csp: SchedulerCSP,
          T_start: float    = 1.0,
          alpha: float      = 0.9995,
          T_min: float      = 0.001,
          max_steps: int    = 50_000,
          max_restarts: int = 20,
          seed: int         = 99) -> dict:
    """
    Returns a result dict:
      {
        "solution":        {slot: bundle} or None,
        "steps":           int,
        "restarts":        int,
        "accepted_worse":  int,
        "final_conflicts": int,
        "soft_score":      dict  (time_day, load_stddev, total) or None,
        "time_seconds":    float,
        "method":          str,
      }
    """
    rng   = random.Random(seed)
    stats = {"steps": 0, "restarts": 0, "accepted_worse": 0, "final_conflicts": 0}
    t0    = time.perf_counter()

    for restart in range(max_restarts):
        if restart > 0:
            stats["restarts"] += 1

        solution = sa_run(csp, rng, T_start, alpha, T_min, max_steps, stats)

        if solution is not None:
            elapsed = time.perf_counter() - t0
            soft    = csp.score_assignment(solution)
            return {
                "solution":        solution,
                "steps":           stats["steps"],
                "restarts":        stats["restarts"],
                "accepted_worse":  stats["accepted_worse"],
                "final_conflicts": 0,
                "soft_score":      soft,
                "time_seconds":    elapsed,
                "method":          "Simulated Annealing",
            }

    # All restarts exhausted — return diagnostics
    elapsed      = time.perf_counter() - t0
    # build a fresh assignment just for the conflict count
    assignment   = {v: rng.choice(csp.domains[v]) for v in csp.variables}
    remaining    = total_hard_conflicts(assignment)
    stats["final_conflicts"] = remaining
    return {
        "solution":        None,
        "steps":           stats["steps"],
        "restarts":        stats["restarts"],
        "accepted_worse":  stats["accepted_worse"],
        "final_conflicts": remaining,
        "soft_score":      None,
        "time_seconds":    elapsed,
        "method":          "Simulated Annealing",
    }
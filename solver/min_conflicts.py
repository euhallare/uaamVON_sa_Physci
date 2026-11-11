"""
min_conflicts.py — Method 3: Min-Conflicts Local Search

Completely different approach from backtracking:
  1. Start with a random complete assignment (every slot gets a random bundle).
  2. Repeat until no conflicts remain or max_steps is reached:
     a. Pick a conflicted slot at random.
     b. Assign it the bundle that minimises its number of conflicts
        (break ties randomly).

This is a local search method — it never explicitly backtracks.
It is typically very fast on highly satisfiable instances but can
get stuck in local minima on tightly constrained ones.

Metrics collected:
  - steps           : number of re-assignment iterations
  - restarts        : number of times we reset to a new random start
  - time_seconds    : wall-clock time
  - final_conflicts : remaining conflicts (0 = solved)
"""

import random
import time
from csp import SchedulerCSP


def count_total_conflicts(csp: SchedulerCSP, assignment: dict) -> int:
    #count total conflict pairs in the current assignment.
    from csp import meetings_overlap
    total = 0
    slots = list(assignment.keys())
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            s1, s2 = slots[i], slots[j]
            if meetings_overlap(assignment[s1]["meetings"],
                                assignment[s2]["meetings"]):
                total += 1
    return total


def conflicted_slots(csp: SchedulerCSP, assignment: dict) -> list:
    #Return all slots involved in at least one conflict.
    from csp import meetings_overlap
    bad = set()
    slots = list(assignment.keys())
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            s1, s2 = slots[i], slots[j]
            if meetings_overlap(assignment[s1]["meetings"],
                                assignment[s2]["meetings"]):
                bad.add(s1)
                bad.add(s2)
    return list(bad)


def solve(csp: SchedulerCSP,
          max_steps: int = 10_000,
          max_restarts: int = 20,
          seed: int = 42) -> dict:
    #Returns a result dict with solution and metrics.
    rng = random.Random(seed)
    stats = {"steps": 0, "restarts": 0, "final_conflicts": 0}
    t0 = time.perf_counter()

    for restart in range(max_restarts):
        if restart > 0:
            stats["restarts"] += 1

        #Random initial complete assignment
        assignment = {
            v: rng.choice(csp.domains[v])
            for v in csp.variables
            if csp.domains[v]   #skip variables with empty domains
        }

        for _ in range(max_steps):
            stats["steps"] += 1
            bad = conflicted_slots(csp, assignment)

            if not bad:
                # Solved
                elapsed = time.perf_counter() - t0
                stats["final_conflicts"] = 0
                return {
                    "solution":        assignment,
                    "steps":           stats["steps"],
                    "restarts":        stats["restarts"],
                    "final_conflicts": 0,
                    "time_seconds":    elapsed,
                    "method":          "Min-Conflicts (Local Search)",
                }

            #Pick a random conflicted slot
            slot = rng.choice(bad)

            #Choose the bundle with the fewest conflicts
            min_c = float("inf")
            best = []
            for bundle in csp.domains[slot]:
                c = csp.num_conflicts(slot, bundle, assignment)
                if c < min_c:
                    min_c = c
                    best = [bundle]
                elif c == min_c:
                    best.append(bundle)

            assignment[slot] = rng.choice(best)

    #Failed — return the best partial we have
    elapsed = time.perf_counter() - t0
    remaining = count_total_conflicts(csp, assignment)
    stats["final_conflicts"] = remaining
    return {
        "solution":        assignment if remaining == 0 else None,
        "steps":           stats["steps"],
        "restarts":        stats["restarts"],
        "final_conflicts": remaining,
        "time_seconds":    elapsed,
        "method":          "Min-Conflicts (Local Search)",
    }
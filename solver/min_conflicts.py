"""
min_conflicts.py — Method 3: Min-Conflicts Local Search

Completely different approach from backtracking:
  1. Start with a random complete assignment (every slot gets a random bundle).
  2. Repeat until no conflicts remain or max_steps is reached:
     a. Pick a conflicted slot at random.
     b. Among bundles with the fewest hard conflicts, pick the one with
        the best (lowest) soft preference score.
        If there is still a tie after soft scoring, break randomly.

Soft constraints:
  Hard conflicts (time overlaps) are always minimised first.
  score_bundle() is used only as a tiebreaker among bundles that are
  equally good on the hard constraint.  This preserves the core
  min-conflicts behaviour while steering toward preferred schedules
  when multiple bundles are equally conflict-free.

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
    """Count total conflict pairs in the current assignment."""
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
    """Return all slots involved in at least one hard conflict."""
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
    """
    Returns a result dict:
      {
        "solution":        {slot: bundle} or None,
        "steps":           int,
        "restarts":        int,
        "final_conflicts": int,
        "soft_score":      dict  (time_day, load_stddev, total) or None,
        "time_seconds":    float,
        "method":          str,
      }
    """
    rng   = random.Random(seed)
    stats = {"steps": 0, "restarts": 0, "final_conflicts": 0}
    t0    = time.perf_counter()

    for restart in range(max_restarts):
        if restart > 0:
            stats["restarts"] += 1

        # Random initial complete assignment
        assignment = {
            v: rng.choice(csp.domains[v])
            for v in csp.variables
            if csp.domains[v]
        }

        for _ in range(max_steps):
            stats["steps"] += 1
            bad = conflicted_slots(csp, assignment)

            if not bad:
                # Solved
                elapsed = time.perf_counter() - t0
                soft    = csp.score_assignment(assignment)
                return {
                    "solution":        assignment,
                    "steps":           stats["steps"],
                    "restarts":        stats["restarts"],
                    "final_conflicts": 0,
                    "soft_score":      soft,
                    "time_seconds":    elapsed,
                    "method":          "Min-Conflicts (Local Search)",
                }

            # Pick a random conflicted slot
            slot = rng.choice(bad)

            # --- two-stage selection ---
            # Stage 1: find minimum hard-conflict count across all bundles
            min_hard = min(
                csp.num_conflicts(slot, b, assignment)
                for b in csp.domains[slot]
            )

            # Stage 2: among bundles tied on hard conflicts, pick lowest soft penalty
            candidates = [
                b for b in csp.domains[slot]
                if csp.num_conflicts(slot, b, assignment) == min_hard
            ]

            if len(candidates) == 1:
                assignment[slot] = candidates[0]
            else:
                # sort by soft score; take all that share the minimum
                min_soft = min(csp.score_bundle(b) for b in candidates)
                soft_best = [b for b in candidates
                             if csp.score_bundle(b) == min_soft]
                # break any remaining tie randomly (preserves exploration)
                assignment[slot] = rng.choice(soft_best)

    # All restarts exhausted
    elapsed   = time.perf_counter() - t0
    remaining = count_total_conflicts(csp, assignment)
    stats["final_conflicts"] = remaining
    return {
        "solution":        assignment if remaining == 0 else None,
        "steps":           stats["steps"],
        "restarts":        stats["restarts"],
        "final_conflicts": remaining,
        "soft_score":      csp.score_assignment(assignment) if remaining == 0 else None,
        "time_seconds":    elapsed,
        "method":          "Min-Conflicts (Local Search)",
    }
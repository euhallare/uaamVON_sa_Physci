"""
plot_results.py — Generate comparison graphs for the AMIS Scheduler CSP project.

Runs all 4 methods across multiple problem instances (Year 1, 2, 3 — FS, SP track)
and saves bar charts comparing:
  - nodes explored / steps taken
  - time (seconds)
  - backtracks / restarts

Usage:
    cd amis_project/solver
    python plot_results.py

Output: saves PNG figures to ../figures/ (created if it doesn't exist).
"""

import os
import sys
import matplotlib
matplotlib.use("Agg")  #i use Agg so it works without a display (WSL-friendly)
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from csp import SchedulerCSP
import backtracking
import forward_checking
import min_conflicts
import simulated_annealing


#paths
BASE       = os.path.join(os.path.dirname(__file__), "..", "data")
SECTIONS   = os.path.join(BASE, "datasets", "term_1261", "sections.csv")
MEETINGS   = os.path.join(BASE, "datasets", "term_1261", "meetings.csv")
CURRICULUM = os.path.join(BASE, "curriculum.csv")

FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "figures")

#i make sure the output folder exists
if not os.path.exists(FIGURES_DIR):
    os.makedirs(FIGURES_DIR)

# which instances to test 
#i vary year so we get different numbers of variables and domain sizes
INSTANCES = [
    {"year": 1, "term": "FS", "track": "SP", "label": "Y1 FS SP"},
    {"year": 2, "term": "FS", "track": "SP", "label": "Y2 FS SP"},
    {"year": 3, "term": "FS", "track": "SP", "label": "Y3 FS SP"},
]

METHOD_NAMES = [
    "Backtracking\n(MRV+LCV)",
    "Forward\nChecking",
    "Min-Conflicts",
    "Simulated\nAnnealing",
]

COLORS = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]


def run_instance(cfg: dict) -> list:
    #Run all 4 methods on one problem instance.
    #Returns a list of result dicts, one per method.
    print(f"\n  Loading: {cfg['label']}")
    csp = SchedulerCSP(
        sections_path     = SECTIONS,
        meetings_path     = MEETINGS,
        curriculum_path   = CURRICULUM,
        year              = cfg["year"],
        term              = cfg["term"],
        track             = cfg["track"],
        require_open_slot = False,
        allow_consent     = False,
    )

    n_vars = len(csp.variables)
    if n_vars == 0:
        print(f"    No schedulable variables — skipping.")
        return []

    domain_sizes = [len(csp.domains[v]) for v in csp.variables]
    avg_domain   = sum(domain_sizes) / len(domain_sizes) if domain_sizes else 0
    print(f"    Variables: {n_vars}, avg domain size: {avg_domain:.1f}")

    results = []

    print("    Running Backtracking...")
    r1 = backtracking.solve(csp)
    r1["instance"] = cfg["label"]
    r1["n_vars"]   = n_vars
    results.append(r1)
    print(f"      {'SOLVED' if r1['solution'] else 'NO SOLUTION'} — {r1['time_seconds']:.4f}s")

    print("    Running Forward Checking...")
    r2 = forward_checking.solve(csp)
    r2["instance"] = cfg["label"]
    r2["n_vars"]   = n_vars
    results.append(r2)
    print(f"      {'SOLVED' if r2['solution'] else 'NO SOLUTION'} — {r2['time_seconds']:.4f}s")

    print("    Running Min-Conflicts...")
    r3 = min_conflicts.solve(csp, max_steps=50_000, max_restarts=30)
    r3["instance"] = cfg["label"]
    r3["n_vars"]   = n_vars
    results.append(r3)
    print(f"      {'SOLVED' if r3['solution'] else 'NO SOLUTION'} — {r3['time_seconds']:.4f}s")

    print("    Running Simulated Annealing...")
    r4 = simulated_annealing.solve(csp, max_steps=50_000, max_restarts=20)
    r4["instance"] = cfg["label"]
    r4["n_vars"]   = n_vars
    results.append(r4)
    print(f"      {'SOLVED' if r4['solution'] else 'NO SOLUTION'} — {r4['time_seconds']:.4f}s")

    return results


def collect_metric(all_results: list, metric: str, fallback=0):
    #all_results is a list of [r1, r2, r3, r4] per instance.
    #Returns a dict: {method_index: [value_per_instance, ...]}
    data = {i: [] for i in range(4)}
    for instance_results in all_results:
        if not instance_results:
            for i in range(4):
                data[i].append(0)
            continue
        for i, r in enumerate(instance_results):
            # i handle the different key names across methods
            val = r.get(metric, fallback)
            if val == "—" or val is None:
                val = fallback
            data[i].append(float(val))
    return data


def bar_chart(all_results: list, instance_labels: list,
              metric: str, title: str, ylabel: str,
              filename: str, fallback=0, log_scale=False):

    #i draw a grouped bar chart: one group per instance, one bar per method.
    data = collect_metric(all_results, metric, fallback)

    n_instances = len(instance_labels)
    n_methods   = 4
    x           = np.arange(n_instances)
    width       = 0.18  # #i keep bars narrow so they fit without overlapping
    offsets     = np.linspace(-(n_methods - 1) / 2, (n_methods - 1) / 2, n_methods) * width

    fig, ax = plt.subplots(figsize=(max(7, 2.5 * n_instances), 5))

    for i in range(n_methods):
        values = data[i]
        bars = ax.bar(
            x + offsets[i],
            values,
            width,
            label=METHOD_NAMES[i],
            color=COLORS[i],
            edgecolor="white",
            linewidth=0.5,
        )
        #add the value label on top of each bar
        for bar, v in zip(bars, values):
            if v > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.02,
                    f"{v:.4f}" if v < 1 else f"{int(v)}",
                    ha="center", va="bottom", fontsize=7.5,
                )

    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(instance_labels, fontsize=10)
    ax.legend(fontsize=9, loc="upper right")
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if log_scale:
        ax.set_yscale("log")

    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, filename)
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")


def solved_heatmap(all_results: list, instance_labels: list, filename: str):
    #draw a simple grid showing SOLVED/NO for each (instance, method) pair.
    n_instances = len(instance_labels)
    n_methods   = 4

    #i build a 2D array: 1 = solved, 0 = not solved
    grid = np.zeros((n_methods, n_instances))
    for col, instance_results in enumerate(all_results):
        if not instance_results:
            continue
        for row, r in enumerate(instance_results):
            grid[row][col] = 1 if r.get("solution") is not None else 0

    fig, ax = plt.subplots(figsize=(max(5, 1.8 * n_instances), 3.5))
    cmap = matplotlib.colors.ListedColormap(["#e74c3c", "#2ecc71"])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    #label each cell
    for row in range(n_methods):
        for col in range(n_instances):
            text = "YES" if grid[row][col] == 1 else "NO"
            ax.text(col, row, text, ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="white")

    ax.set_xticks(range(n_instances))
    ax.set_xticklabels(instance_labels, fontsize=10)
    ax.set_yticks(range(n_methods))
    ax.set_yticklabels([m.replace("\n", " ") for m in METHOD_NAMES], fontsize=9)
    ax.set_title("Solution Found per Instance & Method", fontsize=13,
                 fontweight="bold", pad=10)

    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, filename)
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")


def main():
    print("=" * 55)
    print("  plot_results.py — AMIS Scheduler CSP")
    print("=" * 55)

    #run all instances and collect results
    all_results    = []
    instance_labels = []

    for cfg in INSTANCES:
        results = run_instance(cfg)
        #only add the instance if it had variables to schedule
        if results:
            all_results.append(results)
            instance_labels.append(cfg["label"])

    if not all_results:
        print("\nNo valid instances found. Check your data paths.")
        return

    print(f"\nGenerating figures into: {os.path.abspath(FIGURES_DIR)}")

    # --- Figure 1: Nodes Explored / Steps ---
    # i use "nodes_explored" for exact methods, "steps" for local search
    # collect_metric handles whichever key is present
    bar_chart(
        all_results, instance_labels,
        metric   = "nodes_explored",
        title    = "Nodes Explored / Steps per Method",
        ylabel   = "Nodes / Steps",
        filename = "fig1_nodes_explored.png",
        fallback = 0,
    )
    # local search methods store steps, not nodes_explored — i patch after
    # (simpler: just re-collect with "steps" and overlay)
    bar_chart(
        all_results, instance_labels,
        metric   = "steps",
        title    = "Steps Taken (Local Search Methods)",
        ylabel   = "Steps",
        filename = "fig1b_steps.png",
        fallback = 0,
    )

    # --- Figure 2: Time (seconds) ---
    bar_chart(
        all_results, instance_labels,
        metric   = "time_seconds",
        title    = "Wall-Clock Time per Method",
        ylabel   = "Time (seconds)",
        filename = "fig2_time.png",
        fallback = 0,
    )

    # --- Figure 3: Pruned Values (Forward Checking) ---
    bar_chart(
        all_results, instance_labels,
        metric   = "pruned_values",
        title    = "Domain Values Pruned by Forward Checking",
        ylabel   = "Pruned Values",
        filename = "fig3_pruned_values.png",
        fallback = 0,
    )

    # --- Figure 4: Solved or not ---
    solved_heatmap(all_results, instance_labels, "fig4_solved.png")

    # --- Figure 5: Combined overview (nodes + time side by side) ---
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("AMIS Scheduler CSP — Method Comparison Overview",
                 fontsize=14, fontweight="bold")

    metrics = [
        ("nodes_explored", "Nodes Explored", axes[0]),
        ("time_seconds",   "Time (seconds)", axes[1]),
    ]

    for metric, ylabel, ax in metrics:
        data = collect_metric(all_results, metric, fallback=0)
        n_instances = len(instance_labels)
        x           = np.arange(n_instances)
        width       = 0.18
        offsets     = np.linspace(-(3) / 2, 3 / 2, 4) * width

        for i in range(4):
            values = data[i]
            ax.bar(
                x + offsets[i],
                values,
                width,
                label=METHOD_NAMES[i],
                color=COLORS[i],
                edgecolor="white",
                linewidth=0.5,
            )

        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(instance_labels, fontsize=10)
        ax.legend(fontsize=8)
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, linestyle="--", alpha=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    plt.tight_layout()
    out = os.path.join(FIGURES_DIR, "fig5_overview.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")

    print("\nDone! All figures saved.")
    print("  fig1_nodes_explored.png  — exact methods: nodes tried")
    print("  fig1b_steps.png          — local search: steps taken")
    print("  fig2_time.png            — wall-clock time per method")
    print("  fig3_backtracks.png      — backtracks / restarts")
    print("  fig4_solved.png          — solved/not grid")
    print("  fig5_overview.png        — combined overview (nodes + time)")


if __name__ == "__main__":
    main()
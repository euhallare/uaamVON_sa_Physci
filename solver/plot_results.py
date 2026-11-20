"""
plot_results.py — Generate comparison graphs for the AMIS Scheduler CSP project.

Runs all 4 methods across multiple problem instances (Year 1, 2, 3 — FS)
and saves bar charts comparing nodes explored, time, pruned values, and
whether each method found a solution.

Usage:
    python plot_results.py                    # defaults: cmsc, FS, SP
    python plot_results.py --deg-prog stat --allow-consent
    python plot_results.py --deg-prog math --term SS --track TH --allow-consent

Arguments:
    --deg-prog        Degree program: cmsc, stat, math, amat, ap, chem, agch, bio
                      (default: cmsc)
    --term            FS or SS (default: FS)
    --track           Track code, e.g. SP or TH (default: SP)
    --allow-consent   Include sections requiring D/I consent (needed for non-CMSC programs)

Output: saves PNG figures to ../figures/<deg_prog>/ (created if needed).
"""

import argparse
import os
import sys
import matplotlib
matplotlib.use("Agg")  # WSL-friendly, no display needed
import matplotlib.pyplot as plt
import numpy as np

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

METHOD_NAMES = [
    "Backtracking\n(MRV+LCV)",
    "Forward\nChecking",
    "Min-Conflicts",
    "Simulated\nAnnealing",
]

COLORS = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]


# ----------------------------------------------------------------- runners

def run_instance(cfg: dict, deg_prog: str, allow_consent: bool = False) -> list:
    """Run all 4 methods on one problem instance. Returns list of result dicts."""
    print(f"\n  Loading: {cfg['label']}")
    csp = SchedulerCSP(
        sections_path     = SECTIONS,
        meetings_path     = MEETINGS,
        deg_prog          = deg_prog,
        data_dir          = BASE,
        year              = cfg["year"],
        term              = cfg["term"],
        track             = cfg["track"],
        require_open_slot = False,
        allow_consent     = allow_consent,
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


# ----------------------------------------------------------------- chart helpers

def collect_metric(all_results: list, metric: str, fallback=0):
    data = {i: [] for i in range(4)}
    for instance_results in all_results:
        if not instance_results:
            for i in range(4):
                data[i].append(0)
            continue
        for i, r in enumerate(instance_results):
            val = r.get(metric, fallback)
            if val == "—" or val is None:
                val = fallback
            data[i].append(float(val))
    return data


def bar_chart(all_results: list, instance_labels: list,
              metric: str, title: str, ylabel: str,
              filename: str, figures_dir: str,
              fallback=0, log_scale=False):

    data = collect_metric(all_results, metric, fallback)
    n_instances = len(instance_labels)
    n_methods   = 4
    x           = np.arange(n_instances)
    width       = 0.18
    offsets     = np.linspace(-(n_methods - 1) / 2, (n_methods - 1) / 2, n_methods) * width

    fig, ax = plt.subplots(figsize=(max(7, 2.5 * n_instances), 5))

    for i in range(n_methods):
        values = data[i]
        bars = ax.bar(x + offsets[i], values, width,
                      label=METHOD_NAMES[i], color=COLORS[i],
                      edgecolor="white", linewidth=0.5)
        for bar, v in zip(bars, values):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() * 1.02,
                        f"{v:.4f}" if v < 1 else f"{int(v)}",
                        ha="center", va="bottom", fontsize=7.5)

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
    out = os.path.join(figures_dir, filename)
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")


def solved_heatmap(all_results: list, instance_labels: list,
                   filename: str, figures_dir: str):
    n_instances = len(instance_labels)
    n_methods   = 4
    grid        = np.zeros((n_methods, n_instances))

    for col, instance_results in enumerate(all_results):
        if not instance_results:
            continue
        for row, r in enumerate(instance_results):
            grid[row][col] = 1 if r.get("solution") is not None else 0

    fig, ax = plt.subplots(figsize=(max(5, 1.8 * n_instances), 3.5))
    cmap = matplotlib.colors.ListedColormap(["#e74c3c", "#2ecc71"])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    for row in range(n_methods):
        for col in range(n_instances):
            text = "YES" if grid[row][col] == 1 else "NO"
            ax.text(col, row, text, ha="center", va="center",
                    fontsize=11, fontweight="bold", color="white")

    ax.set_xticks(range(n_instances))
    ax.set_xticklabels(instance_labels, fontsize=10)
    ax.set_yticks(range(n_methods))
    ax.set_yticklabels([m.replace("\n", " ") for m in METHOD_NAMES], fontsize=9)
    ax.set_title("Solution Found per Instance & Method", fontsize=13,
                 fontweight="bold", pad=10)

    plt.tight_layout()
    out = os.path.join(figures_dir, filename)
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deg-prog", default="cmsc",
                    choices=list(DEG_PROG_MAP),
                    help="Degree program (default: cmsc)")
    ap.add_argument("--term",  default="FS", choices=["FS", "SS"],
                    help="Semester: FS or SS (default: FS)")
    ap.add_argument("--track", default="SP",
                    help="Track code e.g. SP or TH (default: SP)")
    ap.add_argument("--allow-consent", action="store_true",
                    help="Include sections requiring D/I consent "
                        "(auto-enabled for non-CMSC programs)")
    args = ap.parse_args()

    deg = args.deg_prog.upper()
    print("=" * 55)
    print(f"  plot_results.py — AMIS Scheduler CSP ({deg})")
    print(f"  allow_consent={args.allow_consent}")
    print("=" * 55)

    # figures go into figures/<deg_prog>/
    figures_dir = os.path.join(os.path.dirname(__file__), "..", "figures", args.deg_prog)
    os.makedirs(figures_dir, exist_ok=True)

    # instances to test: vary year across the same term/track
    instances = [
        {"year": 1, "term": args.term, "track": args.track,
         "label": f"Y1 {args.term} {args.track}"},
        {"year": 2, "term": args.term, "track": args.track,
         "label": f"Y2 {args.term} {args.track}"},
        {"year": 3, "term": args.term, "track": args.track,
         "label": f"Y3 {args.term} {args.track}"},
    ]

    all_results     = []
    instance_labels = []

    for cfg in instances:
        results = run_instance(cfg, args.deg_prog, allow_consent=args.allow_consent)
        if results:
            all_results.append(results)
            instance_labels.append(cfg["label"])

    if not all_results:
        print("\nNo valid instances found. Check your data paths.")
        return

    print(f"\nGenerating figures into: {os.path.abspath(figures_dir)}")

    bar_chart(all_results, instance_labels,
              metric="nodes_explored",
              title=f"Nodes Explored / Steps per Method ({deg})",
              ylabel="Nodes / Steps",
              filename="fig1_nodes_explored.png",
              figures_dir=figures_dir)

    bar_chart(all_results, instance_labels,
              metric="steps",
              title=f"Steps Taken — Local Search ({deg})",
              ylabel="Steps",
              filename="fig1b_steps.png",
              figures_dir=figures_dir)

    bar_chart(all_results, instance_labels,
              metric="time_seconds",
              title=f"Wall-Clock Time per Method ({deg})",
              ylabel="Time (seconds)",
              filename="fig2_time.png",
              figures_dir=figures_dir)

    bar_chart(all_results, instance_labels,
              metric="pruned_values",
              title=f"Domain Values Pruned by Forward Checking ({deg})",
              ylabel="Pruned Values",
              filename="fig3_pruned_values.png",
              figures_dir=figures_dir)

    solved_heatmap(all_results, instance_labels,
                   filename="fig4_solved.png",
                   figures_dir=figures_dir)

    # Combined overview
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f"AMIS Scheduler CSP — Method Comparison ({deg})",
                 fontsize=14, fontweight="bold")

    for metric, ylabel, ax in [
        ("nodes_explored", "Nodes Explored", axes[0]),
        ("time_seconds",   "Time (seconds)", axes[1]),
    ]:
        data        = collect_metric(all_results, metric, fallback=0)
        n_instances = len(instance_labels)
        x           = np.arange(n_instances)
        width       = 0.18
        offsets     = np.linspace(-1.5, 1.5, 4) * width

        for i in range(4):
            ax.bar(x + offsets[i], data[i], width,
                   label=METHOD_NAMES[i], color=COLORS[i],
                   edgecolor="white", linewidth=0.5)

        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(instance_labels, fontsize=10)
        ax.legend(fontsize=8)
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, linestyle="--", alpha=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    plt.tight_layout()
    out = os.path.join(figures_dir, "fig5_overview.png")
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")

    print("\nDone! All figures saved.")
    print("  fig1_nodes_explored.png  — exact methods: nodes tried")
    print("  fig1b_steps.png          — local search: steps taken")
    print("  fig2_time.png            — wall-clock time per method")
    print("  fig3_pruned_values.png   — domain values pruned by FC")
    print("  fig4_solved.png          — solved/not grid")
    print("  fig5_overview.png        — combined overview (nodes + time)")


if __name__ == "__main__":
    main()
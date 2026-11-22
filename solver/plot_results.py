"""
plot_results.py — Generate comparison graphs for the AMIS Scheduler CSP project.

Runs all 4 methods across multiple problem instances (Year 1, 2, 3 — FS)
and saves bar charts comparing nodes explored, time, pruned values, soft scores,
and whether each method found a solution.

Usage:
    python plot_results.py                    # defaults: cmsc, FS, SP
    python plot_results.py --deg-prog stat --allow-consent
    python plot_results.py --deg-prog math --term SS --track TH --allow-consent

Soft constraint flags (same defaults as evaluate.py):
    --time-prefer-after   HH:MM   (default 07:00)
    --time-penalty-after  HH:MM   (default 17:00)
    --no-avoid-saturday           disable Saturday penalty
    --prefer-mwf                  reward Mon/Wed/Fri LEC meetings

Output: PNG figures in ../figures/<deg_prog>/
"""

import argparse
import csv
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from csp import SchedulerCSP, DEG_PROG_MAP
import backtracking
import forward_checking
import min_conflicts
import simulated_annealing

BASE     = os.path.join(os.path.dirname(__file__), "..", "data")
SECTIONS = os.path.join(BASE, "datasets", "term_1261", "sections.csv")
MEETINGS = os.path.join(BASE, "datasets", "term_1261", "meetings.csv")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_CSV  = os.path.join(PROJECT_ROOT, "data", "aggregate_results.csv")

METHOD_NAMES = [
    "Backtracking\n(MRV+LCV)",
    "Forward\nChecking",
    "Min-Conflicts",
    "Simulated\nAnnealing",
]
COLORS = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]


def parse_hhmm(s: str) -> int:
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        raise argparse.ArgumentTypeError(f"Time must be HH:MM, got '{s}'")


def run_instance(cfg: dict, deg_prog: str,
                 time_prefer_after: int, time_penalty_after: int,
                 avoid_days: set, preferred_days: set,
                 allow_consent: bool = False) -> list:
    """Run all 4 methods on one problem instance. Returns list of result dicts."""
    print(f"\n  Loading: {cfg['label']}")
    csp = SchedulerCSP(
        sections_path      = SECTIONS,
        meetings_path      = MEETINGS,
        deg_prog           = deg_prog,
        data_dir           = BASE,
        year               = cfg["year"],
        term               = cfg["term"],
        track              = cfg["track"],
        require_open_slot  = False,
        allow_consent      = allow_consent,
        time_prefer_after  = time_prefer_after,
        time_penalty_after = time_penalty_after,
        avoid_days         = avoid_days,
        preferred_days     = preferred_days,
        soft_weights       = {"time": 1.0, "day": 1.0},
    )

    n_vars = len(csp.variables)
    if n_vars == 0:
        print("    No schedulable variables — skipping.")
        return []

    original_domain_values = sum(len(csp.domains[v]) for v in csp.variables)
    domain_sizes = [len(csp.domains[v]) for v in csp.variables]
    avg_domain   = sum(domain_sizes) / len(domain_sizes) if domain_sizes else 0
    print(f"    Variables: {n_vars}, avg domain size: {avg_domain:.1f}")
    print(f"    Original domain values: {original_domain_values}")

    results = []

    print("    Running Backtracking...")
    r1 = backtracking.solve(csp)
    r1["instance"] = cfg["label"]
    r1["n_vars"]   = n_vars
    r1["original_domain_values"] = original_domain_values
    results.append(r1)
    print(f"      {'SOLVED' if r1['solution'] else 'NO SOLUTION'} — {r1['time_seconds']:.4f}s")

    print("    Running Forward Checking...")
    r2 = forward_checking.solve(csp)
    r2["instance"] = cfg["label"]
    r2["n_vars"]   = n_vars
    r2["original_domain_values"] = original_domain_values
    results.append(r2)
    print(f"      {'SOLVED' if r2['solution'] else 'NO SOLUTION'} — {r2['time_seconds']:.4f}s")

    print("    Running Min-Conflicts...")
    r3 = min_conflicts.solve(csp, max_steps=50_000, max_restarts=30)
    r3["instance"] = cfg["label"]
    r3["n_vars"]   = n_vars
    r3["original_domain_values"] = original_domain_values
    results.append(r3)
    print(f"      {'SOLVED' if r3['solution'] else 'NO SOLUTION'} — {r3['time_seconds']:.4f}s")

    print("    Running Simulated Annealing...")
    r4 = simulated_annealing.solve(csp, max_steps=50_000, max_restarts=20)
    r4["instance"] = cfg["label"]
    r4["n_vars"]   = n_vars
    r4["original_domain_values"] = original_domain_values
    results.append(r4)
    print(f"      {'SOLVED' if r4['solution'] else 'NO SOLUTION'} — {r4['time_seconds']:.4f}s")

    return results


# ----------------------------------------------------------------- chart helpers

def collect_metric(all_results, metric, fallback=0):
    data = {i: [] for i in range(4)}
    for instance_results in all_results:
        if not instance_results:
            for i in range(4):
                data[i].append(0)
            continue
        for i, r in enumerate(instance_results):
            val = r.get(metric, fallback)
            if val in ("—", None):
                val = fallback
            data[i].append(float(val))
    return data


def collect_soft_metric(all_results, key, fallback=0.0):
    """Extract one key from each result's soft_score dict."""
    data = {i: [] for i in range(4)}
    for instance_results in all_results:
        if not instance_results:
            for i in range(4):
                data[i].append(fallback)
            continue
        for i, r in enumerate(instance_results):
            ss  = r.get("soft_score")
            val = ss[key] if ss is not None else fallback
            data[i].append(float(val))
    return data


def bar_chart(all_results, instance_labels, metric, title, ylabel,
              filename, figures_dir, fallback=0, log_scale=False,
              soft_key=None):
    """Generic grouped bar chart. Pass soft_key to pull from soft_score dict."""
    if soft_key:
        data = collect_soft_metric(all_results, soft_key, fallback)
    else:
        data = collect_metric(all_results, metric, fallback)

    n_instances = len(instance_labels)
    x       = np.arange(n_instances)
    width   = 0.18
    offsets = np.linspace(-(4-1)/2, (4-1)/2, 4) * width

    fig, ax = plt.subplots(figsize=(max(7, 2.5 * n_instances), 5))
    for i in range(4):
        values = data[i]
        bars = ax.bar(x + offsets[i], values, width,
                      label=METHOD_NAMES[i], color=COLORS[i],
                      edgecolor="white", linewidth=0.5)
        for bar, v in zip(bars, values):
            if v > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() * 1.02,
                        f"{v:.4f}" if v < 1 else f"{v:.2f}" if v < 100 else f"{int(v)}",
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


def solved_heatmap(all_results, instance_labels, filename, figures_dir):
    n_instances = len(instance_labels)
    grid = np.zeros((4, n_instances))
    for col, instance_results in enumerate(all_results):
        if not instance_results:
            continue
        for row, r in enumerate(instance_results):
            grid[row][col] = 1 if r.get("solution") is not None else 0

    fig, ax = plt.subplots(figsize=(max(5, 1.8 * n_instances), 3.5))
    cmap = matplotlib.colors.ListedColormap(["#e74c3c", "#2ecc71"])
    ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for row in range(4):
        for col in range(n_instances):
            ax.text(col, row, "YES" if grid[row][col] == 1 else "NO",
                    ha="center", va="center", fontsize=11,
                    fontweight="bold", color="white")
    ax.set_xticks(range(n_instances))
    ax.set_xticklabels(instance_labels, fontsize=10)
    ax.set_yticks(range(4))
    ax.set_yticklabels([m.replace("\n", " ") for m in METHOD_NAMES], fontsize=9)
    ax.set_title("Solution Found per Instance & Method", fontsize=13,
                 fontweight="bold", pad=10)
    plt.tight_layout()
    out = os.path.join(figures_dir, filename)
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved: {out}")


# ----------------------------------------------------------------- CSV helper

def save_results_csv(all_results, instances, deg_prog, term, track):
    fieldnames = [
        "degree_program", "year", "term", "track", "method", "instance",
        "n_vars", "original_domain_values",
        "nodes_explored", "steps", "time_seconds", "pruned_values",
        "solution_found",
        "soft_time_day", "soft_load_stddev", "soft_total",
    ]
    method_names = ["Backtracking", "Forward Checking",
                    "Min-Conflicts", "Simulated Annealing"]

    existing_rows = {}
    if os.path.exists(RESULTS_CSV):
        with open(RESULTS_CSV, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["degree_program"], row["year"],
                       row["term"], row["track"], row["method"])
                existing_rows[key] = row

    for instance_results, cfg in zip(all_results, instances):
        for i, result in enumerate(instance_results):
            ss = result.get("soft_score") or {}
            row = {
                "degree_program":         deg_prog,
                "year":                   cfg["year"],
                "term":                   term,
                "track":                  track,
                "method":                 method_names[i],
                "instance":               cfg["label"],
                "n_vars":                 result.get("n_vars", ""),
                "original_domain_values": result.get("original_domain_values", ""),
                "nodes_explored":         result.get("nodes_explored", ""),
                "steps":                  result.get("steps", ""),
                "time_seconds":           result.get("time_seconds", ""),
                "pruned_values":          result.get("pruned_values", ""),
                "solution_found":         result.get("solution") is not None,
                "soft_time_day":          ss.get("time_day", ""),
                "soft_load_stddev":       ss.get("load_stddev", ""),
                "soft_total":             ss.get("total", ""),
            }
            key = (deg_prog, str(cfg["year"]), term, track, method_names[i])
            existing_rows[key] = row

    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows.values())

    print(f"\nResults saved to: {RESULTS_CSV}")


# ----------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deg-prog", default="cmsc", choices=list(DEG_PROG_MAP))
    ap.add_argument("--term",  default="FS", choices=["FS", "SS"])
    ap.add_argument("--track", default="SP")
    ap.add_argument("--allow-consent", action="store_true")
    ap.add_argument("--time-prefer-after",  type=parse_hhmm, default=7*60,  metavar="HH:MM")
    ap.add_argument("--time-penalty-after", type=parse_hhmm, default=17*60, metavar="HH:MM")
    ap.add_argument("--no-avoid-saturday", dest="avoid_saturday",
                    action="store_false", default=True)
    ap.add_argument("--prefer-mwf", action="store_true", default=False)
    args = ap.parse_args()

    avoid_days     = {"S"} if args.avoid_saturday else set()
    preferred_days = {"M", "W", "F"} if args.prefer_mwf else set()
    deg = args.deg_prog.upper()

    print("=" * 60)
    print(f"  plot_results.py — AMIS Scheduler CSP ({deg})")
    print(f"  time_prefer_after={args.time_prefer_after//60}:{args.time_prefer_after%60:02d}  "
          f"time_penalty_after={args.time_penalty_after//60}:{args.time_penalty_after%60:02d}")
    print(f"  avoid_days={avoid_days or 'none'}  preferred_days={preferred_days or 'none'}")
    print("=" * 60)

    figures_dir = os.path.join(os.path.dirname(__file__), "..", "figures", args.deg_prog)
    os.makedirs(figures_dir, exist_ok=True)

    instances = [
        {"year": 1, "term": args.term, "track": args.track,
         "label": f"Y1 {args.term} {args.track}"},
        {"year": 2, "term": args.term, "track": args.track,
         "label": f"Y2 {args.term} {args.track}"},
        {"year": 3, "term": args.term, "track": args.track,
         "label": f"Y3 {args.term} {args.track}"},
    ]

    all_results, instance_labels, valid_instances = [], [], []
    for cfg in instances:
        results = run_instance(
            cfg, args.deg_prog,
            args.time_prefer_after, args.time_penalty_after,
            avoid_days, preferred_days,
            allow_consent=args.allow_consent,
        )
        if results:
            all_results.append(results)
            instance_labels.append(cfg["label"])
            valid_instances.append(cfg)

    save_results_csv(all_results, valid_instances, args.deg_prog, args.term, args.track)

    if not all_results:
        print("\nNo valid instances found.")
        return

    print(f"\nGenerating figures into: {os.path.abspath(figures_dir)}")

    bar_chart(all_results, instance_labels,
              metric="nodes_explored",
              title=f"Nodes Explored — Exact Methods ({deg})",
              ylabel="Nodes explored",
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
              ylabel="Pruned values",
              filename="fig3_pruned_values.png",
              figures_dir=figures_dir)

    solved_heatmap(all_results, instance_labels,
                   filename="fig4_solved.png",
                   figures_dir=figures_dir)

    # Soft score figures
    bar_chart(all_results, instance_labels,
              metric=None, soft_key="time_day",
              title=f"Soft Score — Time+Day Penalty ({deg})  [lower = better]",
              ylabel="Penalty (arbitrary units)",
              filename="fig6_soft_time_day.png",
              figures_dir=figures_dir)

    bar_chart(all_results, instance_labels,
              metric=None, soft_key="load_stddev",
              title=f"Load Balance — Std-dev of Daily Minutes ({deg})  [lower = better]",
              ylabel="Std-dev (hours)",
              filename="fig7_soft_load_stddev.png",
              figures_dir=figures_dir)

    bar_chart(all_results, instance_labels,
              metric=None, soft_key="total",
              title=f"Overall Soft Score (time+day+load) ({deg})  [lower = better]",
              ylabel="Total soft penalty",
              filename="fig8_soft_total.png",
              figures_dir=figures_dir)

    # Combined overview (efficiency + quality side by side)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"AMIS Scheduler CSP — Method Comparison ({deg})",
                 fontsize=14, fontweight="bold")

    for (metric, soft_key, ylabel, ax) in [
        ("time_seconds", None,    "Time (seconds)",       axes[0]),
        (None,           "total", "Total soft score",     axes[1]),
    ]:
        if soft_key:
            data = collect_soft_metric(all_results, soft_key)
        else:
            data = collect_metric(all_results, metric, fallback=0)

        n_instances = len(instance_labels)
        x       = np.arange(n_instances)
        width   = 0.18
        offsets = np.linspace(-1.5, 1.5, 4) * width
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
    print("  fig5_overview.png        — combined overview (time + soft score)")
    print("  fig6_soft_time_day.png   — time+day preference penalty")
    print("  fig7_soft_load_stddev.png— load balance stddev")
    print("  fig8_soft_total.png      — overall soft quality score")


if __name__ == "__main__":
    main()
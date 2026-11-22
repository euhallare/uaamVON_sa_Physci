"""
aggregate_results.py
Aggregate the existing per-degree-program CSP figures' measurements.

Expected input: aggregate_data.csv.
One row = one degree program + one year-level instance.

Expected output: Figures of overall results

Libraries used: csv, math (stdlib), numpy (arrays), matplotlib (plots).
pandas is NOT used anywhere in this file.
"""

import argparse
import csv
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PROGRAM_ORDER = [
    "agch", "amat", "ap", "bio", "chem", "cmsc", "coma", "math", "mst", "phlo", "soc", "stat"
]
YEAR_ORDER = ["Y1", "Y2", "Y3"]

METHODS = {
    "Backtracking (MRV+LCV)": {
        "nodes": "nodes_backtracking",
        "time":  "time_backtracking",
        "solved":"solved_backtracking",
    },
    "Forward Checking": {
        "nodes": "nodes_forward_checking",
        "time":  "time_forward_checking",
        "solved":"solved_forward_checking",
    },
    "Min-Conflicts": {
        "steps": "steps_min_conflicts",
        "time":  "time_min_conflicts",
        "solved":"solved_min_conflicts",
    },
    "Simulated Annealing": {
        "steps": "steps_simulated_annealing",
        "time":  "time_simulated_annealing",
        "solved":"solved_simulated_annealing",
    },
}

METHOD_COLORS = {
    "Backtracking (MRV+LCV)": "#4C72B0",
    "Forward Checking":        "#55A868",
    "Min-Conflicts":           "#C44E52",
    "Simulated Annealing":     "#8172B2",
}

NUMERIC_COLUMNS = [
    "nodes_backtracking", "nodes_forward_checking",
    "steps_min_conflicts", "steps_simulated_annealing",
    "time_backtracking", "time_forward_checking",
    "time_min_conflicts", "time_simulated_annealing",
    "pruned_values_forward_checking",
]
SOLVED_COLUMNS = [
    "solved_backtracking", "solved_forward_checking",
    "solved_min_conflicts", "solved_simulated_annealing",
]


#helpers

def _to_float(value):
    #convert a string to float; return None on failure.
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def _parse_bool(value):
    #'<value>'/'true'/'1' -> 1.0, 'no'/'false'/'0' -> 0.0, else None.
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {"yes", "y", "true", "1"}:
        return 1.0
    if s in {"no", "n", "false", "0"}:
        return 0.0
    raise ValueError(f"Unrecognized solved value: {value!r}")


def _col_mean(rows, col):
    #Mean of a named column, skipping None/NaN.
    vals = [r[col] for r in rows if r.get(col) is not None and not _isnan(r[col])]
    return sum(vals) / len(vals) if vals else float("nan")


def _isnan(v):
    try:
        return math.isnan(v)
    except TypeError:
        return False


def _col_sum(rows, col):
    vals = [r[col] for r in rows if r.get(col) is not None and not _isnan(r[col])]
    return sum(vals)


def _nunique(rows, col):
    return len({r[col] for r in rows if r.get(col) is not None})


#loader

def load_data(path):
    #read the long-format aggregate CSV and return a list of wide-format
    #dicts — one dict per (degree_program, year_level) instance.
    required = [
        "degree_program", "year", "term", "track", "method",
        "n_vars", "original_domain_values",
        "nodes_explored", "steps", "time_seconds",
        "pruned_values", "solution_found",
    ]

    #read raw CSV
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file appears to be empty.")
        missing_cols = [c for c in required if c not in reader.fieldnames]
        if missing_cols:
            raise ValueError("Missing CSV columns: " + ", ".join(missing_cols))
        raw_rows = list(reader)

    #normalise & filter
    long_rows = []
    for row in raw_rows:
        prog = row["degree_program"].strip().lower()
        method = row["method"].strip()
        year_raw = row["year"].strip().replace(".0", "")
        year_level = "Y" + year_raw

        if prog not in PROGRAM_ORDER:
            continue
        if year_level not in YEAR_ORDER:
            continue

        orig = _to_float(row.get("original_domain_values"))

        long_rows.append({
            "degree_program":        prog,
            "year_level":            year_level,
            "method":                method,
            "term":                  row["term"].strip(),
            "track":                 row["track"].strip(),
            "original_domain_values": orig,
            "nodes_explored":        _to_float(row.get("nodes_explored")),
            "steps":                 _to_float(row.get("steps")),
            "time_seconds":          _to_float(row.get("time_seconds")),
            "pruned_values":         _to_float(row.get("pruned_values")),
            "solution_found":        row.get("solution_found", "").strip(),
        })

    #duplicate check
    seen = {}
    for r in long_rows:
        key = (r["degree_program"], r["year_level"], r["method"])
        if key in seen:
            raise ValueError(
                f"Duplicate program/year/method record: {key} "
                f"(terms {seen[key]['term']} and {r['term']})"
            )
        seen[key] = r

    #original domain value consistency
    from collections import defaultdict
    orig_by_instance = defaultdict(set)
    for r in long_rows:
        v = r["original_domain_values"]
        if v is not None and not _isnan(v):
            orig_by_instance[(r["degree_program"], r["year_level"])].add(v)
    inconsistent = {k: v for k, v in orig_by_instance.items() if len(v) > 1}
    if inconsistent:
        raise ValueError(
            "Inconsistent original domain values between methods:\n"
            + "\n".join(f"  {k}: {v}" for k, v in inconsistent.items())
        )

    #missing original domain values
    bad = [
        (r["degree_program"], r["year_level"], r["method"])
        for r in long_rows
        if r["original_domain_values"] is None
        or _isnan(r["original_domain_values"])
        or r["original_domain_values"] <= 0
    ]
    if bad:
        raise ValueError(
            "Missing or invalid original_domain_values. "
            "Rerun these instances using the updated plot_results.py:\n"
            + str(bad)
        )

    #pivot to wide format (one dict per instance)
    #collect all (prog, year_level) pairs in insertion order
    instance_keys = []
    seen_keys = set()
    for r in long_rows:
        k = (r["degree_program"], r["year_level"])
        if k not in seen_keys:
            instance_keys.append(k)
            seen_keys.add(k)

    #method-name -> column-name mapping
    column_mapping = {
        "Backtracking": {
            "nodes_explored": "nodes_backtracking",
            "time_seconds":   "time_backtracking",
            "solution_found": "solved_backtracking",
        },
        "Forward Checking": {
            "nodes_explored":  "nodes_forward_checking",
            "time_seconds":    "time_forward_checking",
            "pruned_values":   "pruned_values_forward_checking",
            "solution_found":  "solved_forward_checking",
        },
        "Min-Conflicts": {
            "steps":          "steps_min_conflicts",
            "time_seconds":   "time_min_conflicts",
            "solution_found": "solved_min_conflicts",
        },
        "Simulated Annealing": {
            "steps":          "steps_simulated_annealing",
            "time_seconds":   "time_simulated_annealing",
            "solution_found": "solved_simulated_annealing",
        },
    }

    #index long rows by (prog, year_level, method)
    long_index = {
        (r["degree_program"], r["year_level"], r["method"]): r
        for r in long_rows
    }

    wide_rows = []
    for prog, yl in instance_keys:
        # original domain value: take from any method row for this instance
        orig = next(
            r["original_domain_values"]
            for r in long_rows
            if r["degree_program"] == prog and r["year_level"] == yl
        )
        wide = {
            "degree_program":         prog,
            "year_level":             yl,
            "original_domain_values": orig,
        }

        for method_name, mappings in column_mapping.items():
            src = long_index.get((prog, yl, method_name))
            for src_col, dst_col in mappings.items():
                raw = src[src_col] if src else None
                if dst_col in SOLVED_COLUMNS:
                    wide[dst_col] = _parse_bool(raw)
                else:
                    wide[dst_col] = _to_float(raw) if isinstance(raw, str) else raw

        # pruning intensity for this instance
        pv = wide.get("pruned_values_forward_checking")
        orig_v = wide["original_domain_values"]
        if pv is not None and not _isnan(pv) and orig_v and orig_v > 0:
            wide["pruning_intensity_pct"] = (pv / orig_v) * 100
        else:
            wide["pruning_intensity_pct"] = float("nan")

        wide_rows.append(wide)

    return wide_rows


#aggregation helpers

def overall_mean(rows, col):
    #Mean of `col` across all wide rows, skipping None/NaN.
    return _col_mean(rows, col)


def create_pruning_summary(rows):
    #return a list of dicts, one per degree program in PROGRAM_ORDER,
    #with pruning totals and intensity.
    from collections import defaultdict
    by_prog = defaultdict(list)
    for r in rows:
        by_prog[r["degree_program"]].append(r)

    summary = []
    for prog in PROGRAM_ORDER:
        prog_rows = by_prog.get(prog, [])
        n_instances = _nunique(prog_rows, "year_level")
        total_orig   = _col_sum(prog_rows, "original_domain_values")
        total_pruned = _col_sum(prog_rows, "pruned_values_forward_checking")
        avg_intensity = _col_mean(prog_rows, "pruning_intensity_pct")
        overall_pct  = (total_pruned / total_orig * 100) if total_orig > 0 else float("nan")
        summary.append({
            "degree_program":                prog,
            "instances":                     n_instances,
            "total_original_domain_values":  total_orig,
            "total_pruned_values":           total_pruned,
            "average_pruning_intensity_pct": avg_intensity,
            "overall_pruning_intensity_pct": overall_pct,
        })
    return summary


#figures

def save_figures(rows, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({"figure.dpi": 140, "savefig.dpi": 200})

    def add_labels(ax, bars, percentage=False):
        for bar in bars:
            height = bar.get_height()
            if math.isfinite(height):
                label = f"{height:.4f}%" if percentage else f"{height:.4f}"
                ax.annotate(
                    label,
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9,
                )

    def format_chart(ax):
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, linestyle="--", alpha=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.margins(y=0.15)

    # ===== Figure 1 — Nodes explored =====
    methods_fig1 = [
        ("Backtracking (MRV+LCV)", "nodes_backtracking"),
        ("Forward Checking",        "nodes_forward_checking"),
    ]
    values = [overall_mean(rows, col) for _, col in methods_fig1]
    labels = [lbl for lbl, _ in methods_fig1]
    colors = [METHOD_COLORS[lbl] for lbl in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="white")
    add_labels(ax, bars)
    ax.set_ylabel("Mean nodes explored")
    ax.set_title("Overall Mean Nodes Explored Across All Instances")
    format_chart(ax)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_01_nodes_explored.png")
    plt.close(fig)

    # ===== Figure 2 — Local-search steps =====
    methods_fig2 = [
        ("Min-Conflicts",       "steps_min_conflicts"),
        ("Simulated Annealing", "steps_simulated_annealing"),
    ]
    values = [overall_mean(rows, col) for _, col in methods_fig2]
    labels = [lbl for lbl, _ in methods_fig2]
    colors = [METHOD_COLORS[lbl] for lbl in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="white")
    add_labels(ax, bars)
    ax.set_ylabel("Mean steps taken")
    ax.set_title("Overall Mean Local-Search Steps Across All Instances")
    format_chart(ax)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_02_local_search_steps.png")
    plt.close(fig)

    # ===== Figure 3 — Execution time =====
    labels = list(METHODS.keys())
    values = [overall_mean(rows, info["time"]) for info in METHODS.values()]
    colors = [METHOD_COLORS[lbl] for lbl in labels]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="white")
    add_labels(ax, bars)
    ax.set_ylabel("Mean execution time (seconds)")
    ax.set_title("Overall Mean Execution Time Across All Instances")
    ax.tick_params(axis="x", labelrotation=12)
    format_chart(ax)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_03_execution_time.png")
    plt.close(fig)

    # ===== Figure 4 — Solution success rate =====
    labels = list(METHODS.keys())
    values = [overall_mean(rows, info["solved"]) * 100 for info in METHODS.values()]
    colors = [METHOD_COLORS[lbl] for lbl in labels]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="white")
    add_labels(ax, bars, percentage=True)
    ax.set_ylabel("Solution success rate (%)")
    ax.set_ylim(0, 115)
    ax.set_title("Overall Solution Success Rate Across All Instances")
    ax.tick_params(axis="x", labelrotation=12)
    format_chart(ax)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_05_solution_success.png")
    plt.close(fig)

    # ===== Figure 5 — Overall CSP Performance (dual axis) =====
    search_columns = [
        "nodes_backtracking", "nodes_forward_checking",
        "steps_min_conflicts", "steps_simulated_annealing",
    ]
    time_columns = [
        "time_backtracking", "time_forward_checking",
        "time_min_conflicts", "time_simulated_annealing",
    ]
    algo_labels = [
        "Backtracking (MRV+LCV)", "Forward Checking",
        "Min-Conflicts", "Simulated Annealing",
    ]

    search_values = [overall_mean(rows, c) for c in search_columns]
    time_values   = [overall_mean(rows, c) for c in time_columns]
    x     = np.arange(len(algo_labels))
    width = 0.3

    def add_overall_labels(ax, bars, offset=5):
        for bar in bars:
            h = bar.get_height()
            if math.isfinite(h) and h > 0:
                ax.annotate(
                    f"{h:.4f}",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, offset), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9,
                )

    fig, ax1 = plt.subplots(figsize=(12, 8))
    ax2 = ax1.twinx()

    search_bars = ax1.bar(x - width / 2, search_values, width,
                          label="Search Effort", color="#55A868")
    add_overall_labels(ax1, search_bars)

    time_bars = ax2.bar(x + width / 2, time_values, width,
                        label="Execution Time", color="#4C72B0")
    add_overall_labels(ax2, time_bars)

    ax1.set_ylabel("Average Search Effort (Nodes / Steps)", labelpad=15)
    ax2.set_ylabel("Average Execution Time (Seconds)", labelpad=15)
    ax1.set_xticks(x)
    ax1.set_xticklabels(algo_labels)
    ax1.set_title("Overall Search Effort and Execution Time")
    format_chart(ax1)

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper right")

    fig.suptitle("AMIS Student Schedule Builder - Overall CSP Performance",
                 fontsize=16, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(output_dir / "aggregate_07_overall_performance.png")
    plt.close(fig)

    # ===== Figure 6 — Forward Checking Pruning Summary =====
    pruning_summary = create_pruning_summary(rows)

    programs       = [s["degree_program"]               for s in pruning_summary]
    original_vals  = [s["total_original_domain_values"]  for s in pruning_summary]
    pruned_vals    = [s["total_pruned_values"]            for s in pruning_summary]

    total_original = sum(original_vals)
    total_pruned   = sum(pruned_vals)
    overall_pct    = (total_pruned / total_original * 100) if total_original > 0 else 0

    fig, ax = plt.subplots(figsize=(14, 7))
    orig_bars   = ax.bar(programs, original_vals, color="#DDEEDC",
                         edgecolor="white", label="Original Domain Values")
    pruned_bars = ax.bar(programs, pruned_vals,   color="#55A868",
                         edgecolor="white", label="Cumulative Pruned Values")
    ax.bar_label(orig_bars,   fmt="%.0f", padding=3, fontsize=8)
    ax.bar_label(pruned_bars, fmt="%.0f", padding=3, fontsize=8)
    ax.set_xlabel("Degree Program")
    ax.set_ylabel("Number of Domain Values")
    ax.set_title("Forward Checking: Original Domain Values vs. Cumulative Pruned Values",
                 fontsize=16, fontweight="bold")
    ax.text(0.98, 0.95, f"Overall Pruning Intensity: {overall_pct:.2f}%",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=11, fontweight="bold")
    ax.legend()
    format_chart(ax)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_08_pruning_intensity.png")
    plt.close(fig)


#CSV writer

def save_pruning_csv(summary, path):
    fieldnames = [
        "degree_program", "instances",
        "total_original_domain_values", "total_pruned_values",
        "average_pruning_intensity_pct", "overall_pruning_intensity_pct",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(summary)


#main

def main():
    parser = argparse.ArgumentParser(
        description="Create aggregate CSP comparison figures. "
                    "Uses csv + numpy + matplotlib only (no pandas)."
    )
    parser.add_argument("--input",  default="../data/aggregate_results.csv",
                        help="CSV containing one row per degree-program/year-level instance.")
    parser.add_argument("--output", default="../figures/aggregate_figures",
                        help="Folder where aggregate PNG figures will be saved.")
    args = parser.parse_args()

    rows = load_data(args.input)
    if not rows:
        raise SystemExit("No valid rows found in the input CSV.")

    expected = sum(1 if p == "mst" else 3 for p in PROGRAM_ORDER)
    print(f"Loaded {len(rows)} curriculum instances (expected up to {expected}).")

    #print counts per degree program
    from collections import Counter
    counts = Counter(r["degree_program"] for r in rows)
    print("Instances per degree program:")
    for prog in PROGRAM_ORDER:
        print(f"  {prog}: {counts.get(prog, 0)}")

    output_dir = Path(args.output)
    save_figures(rows, output_dir)

    pruning_summary = create_pruning_summary(rows)

    summary_path = output_dir / "aggregate_pruning_summary.csv"
    save_pruning_csv(pruning_summary, summary_path)

    print("\nFORWARD CHECKING PRUNING SUMMARY")
    print("=" * 90)
    header = ["degree_program", "instances",
              "total_original_domain_values", "total_pruned_values",
              "average_pruning_intensity_pct", "overall_pruning_intensity_pct"]
    col_w = [20, 10, 30, 22, 30, 30]
    print("  ".join(h.ljust(w) for h, w in zip(header, col_w)))
    print("-" * 90)
    for s in pruning_summary:
        row_str = "  ".join([
            str(s["degree_program"]).ljust(col_w[0]),
            str(s["instances"]).ljust(col_w[1]),
            f"{s['total_original_domain_values']:.0f}".ljust(col_w[2]),
            f"{s['total_pruned_values']:.0f}".ljust(col_w[3]),
            f"{s['average_pruning_intensity_pct']:.2f}%".ljust(col_w[4]),
            f"{s['overall_pruning_intensity_pct']:.2f}%".ljust(col_w[5]),
        ])
        print(row_str)

    print(f"\nPruning summary saved to: {summary_path}")
    print(f"Created aggregate figures in: {output_dir}")


if __name__ == "__main__":
    main()
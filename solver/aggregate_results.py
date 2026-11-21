"""
aggregate_results.py
Aggregate the existing per-degree-program CSP figures' measurements.

Expected input: aggregate_data.csv.
One row = one degree program + one year-level instance.

Expected output: six figures of overall results
"""

from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROGRAM_ORDER = [
    "cmsc", "stat", "math", "amat", "ap", "chem",
    "agch", "bio", "mst", "soc", "phlo", "coma"
]
YEAR_ORDER = ["Y1", "Y2", "Y3"]

METHODS = {
    "Backtracking (MRV+LCV)": {
        "nodes": "nodes_backtracking",
        "time": "time_backtracking",
        "solved": "solved_backtracking",
    },
    "Forward Checking": {
        "nodes": "nodes_forward_checking",
        "time": "time_forward_checking",
        "solved": "solved_forward_checking",
    },
    "Min-Conflicts": {
        "steps": "steps_min_conflicts",
        "time": "time_min_conflicts",
        "solved": "solved_min_conflicts",
    },
    "Simulated Annealing": {
        "steps": "steps_simulated_annealing",
        "time": "time_simulated_annealing",
        "solved": "solved_simulated_annealing",
    },
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

def load_data(path):
    df = pd.read_csv(path)
    required = ["degree_program", "year_level"] + NUMERIC_COLUMNS + SOLVED_COLUMNS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Missing CSV columns: " + ", ".join(missing))

    df["degree_program"] = df["degree_program"].astype(str).str.strip().str.lower()
    df["year_level"] = df["year_level"].astype(str).str.strip().str.upper()
    df = df[df["degree_program"].isin(PROGRAM_ORDER)]
    df = df[df["year_level"].isin(YEAR_ORDER)]

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    def parse_bool(value):
        if pd.isna(value) or str(value).strip() == "":
            return np.nan
        value = str(value).strip().lower()
        if value in {"yes", "y", "true", "1"}:
            return 1
        if value in {"no", "n", "false", "0"}:
            return 0
        raise ValueError(f"Unrecognized solved value: {value!r}; use YES/NO.")
    for col in SOLVED_COLUMNS:
        df[col] = df[col].map(parse_bool)

    # Reject duplicate program/year records
    dup = df.duplicated(["degree_program", "year_level"], keep=False)
    if dup.any():
        pairs = df.loc[dup, ["degree_program", "year_level"]].to_dict("records")
        raise ValueError(f"Duplicate program/year rows: {pairs}")

    return df

def mean_by_program(df, column):
    return (df.groupby("degree_program")[column]
              .mean()
              .reindex(PROGRAM_ORDER))

def save_figures(df, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 140, "savefig.dpi": 200})

    # ===================== Figure 1 — complete search methods: nodes explored =====================
    fig, ax = plt.subplots(figsize=(13, 6))
    x = np.arange(len(PROGRAM_ORDER))
    width = 0.36
    for i, (label, col) in enumerate([
        ("Backtracking (MRV+LCV)", "nodes_backtracking"),
        ("Forward Checking", "nodes_forward_checking"),
    ]):
        vals = mean_by_program(df, col)
        ax.bar(x + (i - 0.5) * width, vals, width, label=label)
    ax.set_xticks(x, [p.upper() for p in PROGRAM_ORDER])
    ax.set_ylabel("Mean nodes explored")
    ax.set_title("Nodes Explored by Degree Program (Mean Across Available Year Levels)")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=.35)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_01_nodes_explored.png")
    plt.close(fig)

    # ===================== Figure 2 — local-search methods: steps taken =====================
    fig, ax = plt.subplots(figsize=(13, 6))
    for i, (label, col) in enumerate([
        ("Min-Conflicts", "steps_min_conflicts"),
        ("Simulated Annealing", "steps_simulated_annealing"),
    ]):
        vals = mean_by_program(df, col)
        ax.bar(x + (i - 0.5) * width, vals, width, label=label)
    ax.set_xticks(x, [p.upper() for p in PROGRAM_ORDER])
    ax.set_ylabel("Mean steps taken")
    ax.set_title("Local-Search Steps by Degree Program (Mean Across Available Year Levels)")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=.35)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_02_local_search_steps.png")
    plt.close(fig)

    # ===================== Figure 3 — execution time for all methods =====================
    fig, ax = plt.subplots(figsize=(14, 6))
    width4 = 0.19
    for i, (label, info) in enumerate(METHODS.items()):
        vals = mean_by_program(df, info["time"])
        ax.bar(x + (i - 1.5) * width4, vals, width4, label=label)
    ax.set_xticks(x, [p.upper() for p in PROGRAM_ORDER])
    ax.set_ylabel("Mean wall-clock time (seconds)")
    ax.set_title("Execution Time by Degree Program (Mean Across Available Year Levels)")
    ax.legend(ncol=2)
    ax.grid(axis="y", linestyle="--", alpha=.35)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_03_execution_time.png")
    plt.close(fig)

    # ===================== Figure 4 — Forward Checking's pruned domain values =====================
    fig, ax = plt.subplots(figsize=(13, 6))
    vals = mean_by_program(df, "pruned_values_forward_checking")
    ax.bar(x, vals)
    ax.set_xticks(x, [p.upper() for p in PROGRAM_ORDER])
    ax.set_ylabel("Mean domain values pruned")
    ax.set_title("Domain Values Pruned by Forward Checking (Mean Across Available Year Levels)")
    ax.grid(axis="y", linestyle="--", alpha=.35)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_04_pruned_values.png")
    plt.close(fig)

    # ===================== Figure 5 — success rate heatmap; annotations show solved/available counts =====================
    success_cols = [info["solved"] for info in METHODS.values()]
    rate = pd.DataFrame(index=PROGRAM_ORDER, columns=list(METHODS), dtype=float)
    counts = pd.DataFrame(index=PROGRAM_ORDER, columns=list(METHODS), dtype=object)
    for program in PROGRAM_ORDER:
        subset = df[df["degree_program"] == program]
        for method, col in zip(METHODS, success_cols):
            values = subset[col].dropna()
            rate.loc[program, method] = values.mean() * 100 if len(values) else np.nan
            counts.loc[program, method] = (
                f"{int(values.sum())}/{len(values)}" if len(values) else "N/A"
            )
    fig, ax = plt.subplots(figsize=(11, 7))
    masked = rate.astype(float)
    im = ax.imshow(masked, aspect="auto", vmin=0, vmax=100, cmap="YlGn")
    ax.set_xticks(np.arange(len(METHODS)), list(METHODS), rotation=18, ha="right")
    ax.set_yticks(np.arange(len(PROGRAM_ORDER)), [p.upper() for p in PROGRAM_ORDER])
    for r, program in enumerate(PROGRAM_ORDER):
        for c, method in enumerate(METHODS):
            value = rate.loc[program, method]
            label = counts.loc[program, method]
            ax.text(c, r, label if pd.isna(value) else f"{value:.0f}%\n({label})",
                    ha="center", va="center", fontsize=8)
    ax.set_title("Solution Success Rate by Degree Program and Method\n(Cell = success percentage; count = solved / available year levels)")
    fig.colorbar(im, ax=ax, label="Success rate (%)")
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_05_solution_success.png")
    plt.close(fig)

    # ===================== Figure 6 — combined overview =====================
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    series = [
        ("Backtracking nodes", "nodes_backtracking"),
        ("Forward Checking nodes", "nodes_forward_checking"),
        ("Min-Conflicts steps", "steps_min_conflicts"),
        ("Simulated Annealing steps", "steps_simulated_annealing"),
    ]
    for label, col in series:
        ax1.plot(x, mean_by_program(df, col), marker="o", linewidth=1.8, label=label)
    ax1.set_ylabel("Mean nodes / steps")
    ax1.set_title("Search Effort")
    ax1.legend(ncol=2)
    ax1.grid(axis="y", linestyle="--", alpha=.35)

    for label, info in METHODS.items():
        ax2.plot(x, mean_by_program(df, info["time"]), marker="o", linewidth=1.8, label=label)
    ax2.set_ylabel("Mean time (seconds)")
    ax2.set_title("Wall-Clock Time")
    ax2.set_xticks(x, [p.upper() for p in PROGRAM_ORDER])
    ax2.legend(ncol=2)
    ax2.grid(axis="y", linestyle="--", alpha=.35)
    fig.suptitle("AMIS Scheduler CSP — Aggregate Method Overview", fontsize=15)
    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_06_combined_overview.png")
    plt.close(fig)

def main():
    parser = argparse.ArgumentParser(description="Create six aggregate CSP comparison figures.")
    parser.add_argument("--input", default="aggregate_data.csv",
                        help="CSV containing one row per degree-program/year-level instance.")
    parser.add_argument("--output", default="aggregate_figures",
                        help="Folder where aggregate PNG figures will be saved.")
    args = parser.parse_args()

    df = load_data(args.input)
    if df.empty:
        raise SystemExit("No valid rows found in the input CSV.")

    expected = sum(1 if p == "mst" else 3 for p in PROGRAM_ORDER)
    present = len(df)
    print(f"Loaded {present} curriculum instances (expected up to {expected}).")
    print("Instances per degree program:")
    print(df.groupby("degree_program").size().reindex(PROGRAM_ORDER).fillna(0).astype(int).to_string())

    save_figures(df, Path(args.output))
    print(f"\nCreated six aggregate figures in: {args.output}")

if __name__ == "__main__":
    main()

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
    "agch", "amat", "ap", "bio", "chem", "cmsc", "coma", "math", "mst", "phlo", "soc", "stat"
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

METHOD_COLORS = {
    "Backtracking (MRV+LCV)": "#4C72B0",
    "Forward Checking": "#55A868",
    "Min-Conflicts": "#C44E52",
    "Simulated Annealing": "#8172B2",
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

    # Check whether the CSV has the expected columns
    required = [
        "degree_program", "year", "term", "track", "method",
        "nodes_explored", "steps", "time_seconds",
        "pruned_values", "solution_found"
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError("Missing CSV columns: " + ", ".join(missing))

    # Standardize degree program and method names
    df["degree_program"] = df["degree_program"].astype(str).str.strip().str.lower()
    df["method"] = df["method"].astype(str).str.strip()

    # Convert the numerical year into Y1, Y2, or Y3
    df["year_level"] = "Y" + df["year"].astype(str).str.replace(".0", "", regex=False)

    # Keep only the degree programs and year levels we need
    df = df[df["degree_program"].isin(PROGRAM_ORDER)]
    df = df[df["year_level"].isin(YEAR_ORDER)]

    # Check for duplicate records for the same program, year, and method
    dup = df.duplicated(
        ["degree_program", "year_level", "method"],
        keep=False
    )

    if dup.any():
        duplicates = df.loc[
            dup, ["degree_program", "year_level", "method", "term", "track"]
        ].to_dict("records")

        raise ValueError(f"Duplicate program/year/method records: {duplicates}")

    # Create one row per degree program and year level
    wide_df = df[["degree_program", "year_level"]].drop_duplicates()

    wide_df = wide_df.set_index(["degree_program", "year_level"])

    # Map the long-format CSV columns into the columns
    column_mapping = {
        "Backtracking": {
            "nodes_explored": "nodes_backtracking",
            "time_seconds": "time_backtracking",
            "solution_found": "solved_backtracking",
        },
        "Forward Checking": {
            "nodes_explored": "nodes_forward_checking",
            "time_seconds": "time_forward_checking",
            "pruned_values": "pruned_values_forward_checking",
            "solution_found": "solved_forward_checking",
        },
        "Min-Conflicts": {
            "steps": "steps_min_conflicts",
            "time_seconds": "time_min_conflicts",
            "solution_found": "solved_min_conflicts",
        },
        "Simulated Annealing": {
            "steps": "steps_simulated_annealing",
            "time_seconds": "time_simulated_annealing",
            "solution_found": "solved_simulated_annealing",
        },
    }

    # Transfer each method's measurements into its corresponding columns
    for method, mappings in column_mapping.items():

        method_df = df[df["method"] == method]

        method_df = method_df.set_index(["degree_program", "year_level"])

        for source_column, target_column in mappings.items():
            wide_df[target_column] = method_df[source_column]

    # Convert numerical measurements into numeric values
    for col in NUMERIC_COLUMNS:
        wide_df[col] = pd.to_numeric(wide_df[col], errors="coerce")

    # Convert solution - results into 1 (solved) and 0 (not solved)
    def parse_bool(value):
        if pd.isna(value):
            return np.nan

        value = str(value).strip().lower()

        if value in {"yes", "y", "true", "1"}:
            return 1

        if value in {"no", "n", "false", "0"}:
            return 0

        raise ValueError(f"Unrecognized solved value: {value!r}")

    for col in SOLVED_COLUMNS:
        wide_df[col] = wide_df[col].map(parse_bool)

    return wide_df.reset_index()


def mean_by_program(df, column):
    return (df.groupby("degree_program")[column]
              .mean()
              .reindex(PROGRAM_ORDER))


def save_figures(df, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({
        "figure.dpi": 140,
        "savefig.dpi": 200
    })

    # Calculate the mean of each metric across all available instances
    def overall_mean(column):
        return df[column].dropna().mean()

    # Add numerical labels above the bars
    def add_labels(ax, bars, percentage=False):
        for bar in bars:
            height = bar.get_height()

            if np.isfinite(height):
                if percentage:
                    label = f"{height:.4f}%"
                else:
                    label = f"{height:.4f}"

                ax.annotate(
                    label,
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=9
                )

    # Common chart formatting
    def format_chart(ax):
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, linestyle="--", alpha=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.margins(y=0.15)

    # ===================== Figure 1 — Nodes explored =====================

    methods = [
        ("Backtracking (MRV+LCV)", "nodes_backtracking"),
        ("Forward Checking", "nodes_forward_checking"),
    ]

    values = [overall_mean(column) for label, column in methods]
    labels = [label for label, column in methods]
    colors = [METHOD_COLORS[label] for label in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="white")

    add_labels(ax, bars)
    ax.set_ylabel("Mean nodes explored")
    ax.set_title("Overall Mean Nodes Explored Across All Instances")
    format_chart(ax)

    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_01_nodes_explored.png")
    plt.close(fig)

    # ===================== Figure 2 — Local-search steps =====================

    methods = [
        ("Min-Conflicts", "steps_min_conflicts"),
        ("Simulated Annealing", "steps_simulated_annealing"),
    ]

    values = [overall_mean(column) for label, column in methods]
    labels = [label for label, column in methods]
    colors = [METHOD_COLORS[label] for label in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="white")

    add_labels(ax, bars)
    ax.set_ylabel("Mean steps taken")
    ax.set_title("Overall Mean Local-Search Steps Across All Instances")
    format_chart(ax)

    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_02_local_search_steps.png")
    plt.close(fig)

    # ===================== Figure 3 — Execution time =====================

    labels = list(METHODS.keys())
    columns = [info["time"] for info in METHODS.values()]

    values = [overall_mean(column) for column in columns]
    colors = [METHOD_COLORS[label] for label in labels]

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

    # ===================== Figure 4 — Pruned values =====================

    fig, ax = plt.subplots(figsize=(14, 7))

    programs = sorted(df["degree_program"].unique())
    year_levels = ["Y1", "Y2", "Y3"]

    x = np.arange(len(programs))
    width = 0.25

    year_colors = {
        "Y1": "#A5D6A7",
        "Y2": "#55A868",
        "Y3": "#276749",
    }

    for i, year in enumerate(year_levels):

        # Get the pruned-values results for this year level
        year_data = (
            df[df["year_level"] == year]
            .set_index("degree_program")["pruned_values_forward_checking"]
            .reindex(programs)
        )

        # Position each year's bars beside one another
        positions = x + (i - 1) * width

        bars = ax.bar(
            positions,
            year_data,
            width,
            label=year,
            color=year_colors[year]
        )

        # Display values above each bar with alternating vertical offsets
        for j, bar in enumerate(bars):
            height = bar.get_height()

            if np.isfinite(height):
                ax.annotate(
                    f"{height:.4f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 5 + (i * 12)),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8
                )

    # Calculate and display the overall mean
    overall_mean = df["pruned_values_forward_checking"].dropna().mean()

    ax.axhline(
        y=overall_mean,
        color="black",
        linestyle="--",
        linewidth=1.5,
        label=f"Overall Mean: {overall_mean:.4f}"
    )

    ax.set_title("Pruned Values by Degree Program and Year Level")
    ax.set_xlabel("Degree Program")
    ax.set_ylabel("Pruned Values")
    ax.set_xticks(x)
    ax.set_xticklabels(programs)

    format_chart(ax)
    ax.legend(title="Year Level")

    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_04_pruned_values.png")
    plt.close(fig)

    # ===================== Figure 5 — Solution success rate =====================

    labels = list(METHODS.keys())
    columns = [info["solved"] for info in METHODS.values()]

    # Calculate the percentage of successful instances for each method
    values = [
        df[column].dropna().mean() * 100
        for column in columns
    ]

    colors = [METHOD_COLORS[label] for label in labels]

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

    # ===================== Figure 6 — Overview =====================
    fig, axes = plt.subplots(2, 1, figsize=(16, 12))

    # Calculate the average result per degree program.
    program_means = (
        df.groupby("degree_program")
        .mean(numeric_only=True)
        .sort_index()
    )

    programs = program_means.index.tolist()
    x = np.arange(len(programs))

    # PANEL 1: SEARCH EFFORT
    ax = axes[0]

    search_columns = [
        "nodes_backtracking",
        "nodes_forward_checking",
        "steps_min_conflicts",
        "steps_simulated_annealing"
    ]

    search_labels = [
        "Backtracking (MRV+LCV)",
        "Forward Checking",
        "Min-Conflicts",
        "Simulated Annealing"
    ]

    width = 0.2

    for i, (column, label) in enumerate(zip(search_columns, search_labels)):

        values = program_means[column].reindex(programs)

        positions = x + (i - 1.5) * width

        ax.bar(
            positions,
            values,
            width,
            label=label,
            color=METHOD_COLORS[label]
        )

    ax.set_title("Search Effort")
    ax.set_ylabel("Average Count")
    ax.set_xticks(x)
    ax.set_xticklabels(programs, rotation=35, ha="right")

    format_chart(ax)
    ax.legend(ncol=2)

    # PANEL 2: EXECUTION TIME
    ax = axes[1]

    time_columns = [
        "time_backtracking",
        "time_forward_checking",
        "time_min_conflicts",
        "time_simulated_annealing"
    ]

    time_labels = [
        "Backtracking (MRV+LCV)",
        "Forward Checking",
        "Min-Conflicts",
        "Simulated Annealing"
    ]

    for i, (column, label) in enumerate(zip(time_columns, time_labels)):

        values = program_means[column].reindex(programs)

        positions = x + (i - 1.5) * width

        ax.bar(
            positions,
            values,
            width,
            label=label,
            color=METHOD_COLORS[label]
        )

    ax.set_title("Execution Time")
    ax.set_ylabel("Average Execution Time (seconds)")
    ax.set_xticks(x)
    ax.set_xticklabels(programs, rotation=35, ha="right")

    ax.set_yscale("log")

    format_chart(ax)
    ax.legend(ncol=4)

    fig.suptitle(
        "AMIS Student Schedule Builder - Overall CSP Performance",
        fontsize=16,
        fontweight="bold"
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    fig.savefig(output_dir / "aggregate_06_overview.png")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Create six aggregate CSP comparison figures.")
    parser.add_argument("--input", default="../data/aggregate_results.csv",
                        help="CSV containing one row per degree-program/year-level instance.")
    parser.add_argument("--output", default="../figures/aggregate_figures",
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

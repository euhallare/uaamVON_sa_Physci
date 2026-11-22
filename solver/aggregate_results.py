"""
aggregate_results.py
Aggregate the existing per-degree-program CSP figures' measurements.

Expected input: aggregate_data.csv.
One row = one degree program + one year-level instance.

Expected output: Figures of overall results
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
    # "original_domain_values",
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
        "n_vars", "original_domain_values",
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

    # Convert original domain values to numeric.
    df["original_domain_values"] = pd.to_numeric(
        df["original_domain_values"],
        errors="coerce"
    )

    # Every method should have the same original domain size for the same CSP instance.
    original_counts = (
        df.groupby(["degree_program", "year_level"])["original_domain_values"]
        .nunique()
    )

    inconsistent = original_counts[original_counts > 1]

    if not inconsistent.empty:
        raise ValueError(
            "Inconsistent original domain values between methods:\n"
            + inconsistent.to_string()
        )

    # Every instance needs a valid original domain size.
    missing_original = df[
        df["original_domain_values"].isna()
        | (df["original_domain_values"] <= 0)
    ]

    if not missing_original.empty:
        missing_instances = missing_original[
            ["degree_program", "year_level", "method"]
        ].to_dict("records")

        raise ValueError(
            "Missing or invalid original_domain_values. "
            "Rerun these instances using the updated plot_results.py:\n"
            + str(missing_instances)
        )

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

    # Store the original domain size once per CSP instance.
    original_domain_sizes = (
        df.groupby(["degree_program", "year_level"])["original_domain_values"]
        .first()
    )

    wide_df["original_domain_values"] = original_domain_sizes

    # Calculate Forward Checking's pruning intensity.
    # This uses cumulative pruning events, not unique domain entries.
    wide_df["pruning_intensity_pct"] = (
        wide_df["pruned_values_forward_checking"]
        / wide_df["original_domain_values"]
    ) * 100

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

def create_pruning_summary(df):
    """
    Create a per-degree-program summary of Forward Checking's
    original domain values and cumulative pruning events.
    """

    summary = (
        df.groupby("degree_program")
        .agg(
            instances=("year_level", "nunique"),
            total_original_domain_values=(
                "original_domain_values", "sum"
            ),
            total_pruned_values=(
                "pruned_values_forward_checking", "sum"
            ),
            average_pruning_intensity_pct=(
                "pruning_intensity_pct", "mean"
            ),
        )
        .reindex(PROGRAM_ORDER)
    )

    # Calculate the weighted overall pruning intensity.
    summary["overall_pruning_intensity_pct"] = (
        summary["total_pruned_values"]
        / summary["total_original_domain_values"]
    ) * 100

    return summary.reset_index()

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

    # ===================== Figure 4 — Solution success rate =====================

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

    # ===================== Figure 5 — Overall CSP Performance =====================

    # Calculate the overall average across all degree programs and year levels.
    overall_means = df.mean(numeric_only=True)

    # Create the figure and primary axis.
    fig, ax1 = plt.subplots(figsize=(12, 8))

    # Create the secondary Y-axis for execution time.
    ax2 = ax1.twinx()

    # Algorithm names and corresponding columns.
    search_columns = [
        "nodes_backtracking",
        "nodes_forward_checking",
        "steps_min_conflicts",
        "steps_simulated_annealing"
    ]

    time_columns = [
        "time_backtracking",
        "time_forward_checking",
        "time_min_conflicts",
        "time_simulated_annealing"
    ]

    labels = [
        "Backtracking (MRV+LCV)",
        "Forward Checking",
        "Min-Conflicts",
        "Simulated Annealing"
    ]

    # Positions of the four algorithms.
    x = np.arange(len(labels))
    width = 0.3

    # Display numerical values above each bar.
    def add_overall_labels(ax, bars, offset=5):
        for bar in bars:
            height = bar.get_height()

            if np.isfinite(height) and height > 0:
                ax.annotate(
                    f"{height:.4f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, offset),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=9
                )

    # SEARCH EFFORT — LEFT Y-AXIS
    search_values = [
        overall_means[column] for column in search_columns
    ]

    search_bars = ax1.bar(
        x - width / 2,
        search_values,
        width,
        label="Search Effort",
        color="#55A868"
    )

    add_overall_labels(ax1, search_bars)

    # EXECUTION TIME — RIGHT Y-AXIS
    time_values = [
        overall_means[column] for column in time_columns
    ]

    time_bars = ax2.bar(
        x + width / 2,
        time_values,
        width,
        label="Execution Time",
        color="#4C72B0"
    )

    add_overall_labels(ax2, time_bars)

    # Chart formatting.
    ax1.set_ylabel("Average Search Effort (Nodes / Steps)", labelpad=15)
    ax2.set_ylabel("Average Execution Time (Seconds)", labelpad=15)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)

    ax1.set_title("Overall Search Effort and Execution Time")

    format_chart(ax1)

    # Combine both legends.
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()

    ax1.legend(
        handles1 + handles2,
        labels1 + labels2,
        loc="upper right"
    )

    fig.suptitle(
        "AMIS Student Schedule Builder - Overall CSP Performance",
        fontsize=16,
        fontweight="bold"
    )

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    fig.savefig(output_dir / "aggregate_07_overall_performance.png")
    plt.close(fig)

    # ===================== Figure 6 — Forward Checking Pruning Summary =====================

    pruning_summary = create_pruning_summary(df)

    programs = pruning_summary["degree_program"]

    original_values = pruning_summary["total_original_domain_values"]
    pruned_values = pruning_summary["total_pruned_values"]
    overall_percentages = pruning_summary["overall_pruning_intensity_pct"]

    total_original = original_values.sum()
    total_pruned = pruned_values.sum()

    overall_percentage = (
        total_pruned / total_original
    ) * 100 if total_original > 0 else 0

    fig, ax = plt.subplots(figsize=(14, 7))

    # Background bars: total original domain values
    original_bars = ax.bar(
        programs,
        original_values,
        color="#DDEEDC",
        edgecolor="white",
        label="Original Domain Values"
    )

    # Foreground bars: cumulative values pruned
    pruned_bars = ax.bar(
        programs,
        pruned_values,
        color="#55A868",
        edgecolor="white",
        label="Cumulative Pruned Values"
    )

    # Display integer values on both sets of bars
    ax.bar_label(
        original_bars,
        fmt="%.0f",
        padding=3,
        fontsize=8
    )

    ax.bar_label(
        pruned_bars,
        fmt="%.0f",
        padding=3,
        fontsize=8
    )

    ax.set_xlabel("Degree Program")
    ax.set_ylabel("Number of Domain Values")
    ax.set_title(
        "Forward Checking: Original Domain Values vs. Cumulative Pruned Values",
        fontsize=16,
        fontweight="bold"
    )

    ax.text(0.98, 0.95, f"Overall Pruning Intensity: {overall_percentage:.2f}%",
            transform=ax.transAxes, ha="right", va="top", fontsize=11, fontweight="bold"
    )

    ax.legend()

    format_chart(ax)

    fig.tight_layout()
    fig.savefig(output_dir / "aggregate_08_pruning_intensity.png")
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

    output_dir = Path(args.output)

    save_figures(df, output_dir)

    # Generate and save the pruning summary.
    pruning_summary = create_pruning_summary(df)

    summary_path = output_dir / "aggregate_pruning_summary.csv"
    pruning_summary.to_csv(summary_path, index=False)

    print("\nFORWARD CHECKING PRUNING SUMMARY")
    print("=" * 90)

    print(
        pruning_summary.to_string(
            index=False,
            formatters={
                "average_pruning_intensity_pct": "{:.2f}%".format,
                "overall_pruning_intensity_pct": "{:.2f}%".format,
            }
        )
    )

    print(f"\nPruning summary saved to: {summary_path}")
    print(f"Created eight aggregate figures in: {output_dir}")

if __name__ == "__main__":
    main()

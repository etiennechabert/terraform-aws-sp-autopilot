"""
Generate a chart showing how gap_split distributes Savings Plans purchases over time.

Simulates 10 years of gap_split with 1-year commitments and divider=2.
Daily resolution rendering, monthly purchases (1st of each month).
Plans purchased on the 1st expire exactly 1 year later (also the 1st),
so the scheduler always catches expirations on the same run.

Usage:
    python docs/generate_gap_split_chart.py
"""

import matplotlib.pyplot as plt
from dataclasses import dataclass

DAYS_PER_YEAR = 365

# Day-of-year for the 1st of each month (non-leap year)
MONTH_STARTS = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]


@dataclass
class Plan:
    coverage_pct: float
    start_day: int
    end_day: int


def _monthly_purchase_days(total_years: int) -> list[int]:
    """Generate purchase days: 1st of each month for N years."""
    days = []
    for year in range(total_years + 1):
        for month_start in MONTH_STARTS:
            day = year * DAYS_PER_YEAR + month_start
            if day <= total_years * DAYS_PER_YEAR:
                days.append(day)
    return sorted(set(days))


def build_plan_history(
    divider: float,
    term_years: int,
    total_years: int,
    min_purchase_pct: float = 1.0,
    renewal_window_days: int = 7,
) -> tuple[list[float], list[float], list[Plan]]:
    """Simulate gap_split at daily resolution with monthly purchases on the 1st.

    Plans expire exactly term_years later, which also falls on the 1st —
    so the scheduler catches expirations on the same run (no gap).
    """
    target = 100.0
    term_days = term_years * DAYS_PER_YEAR
    total_days = total_years * DAYS_PER_YEAR
    purchase_days = set(_monthly_purchase_days(total_years))

    padding_days = 30
    all_plans: list[Plan] = []
    time_points: list[float] = []
    coverages: list[float] = []
    active_plans: list[Plan] = []

    for day in range(-padding_days, total_days + padding_days + 1):
        # Expire plans
        active_plans = [p for p in active_plans if p.end_day > day]
        current = sum(p.coverage_pct for p in active_plans)

        # Record coverage
        time_points.append(day / DAYS_PER_YEAR)
        coverages.append(current)

        # Purchase on scheduler run days (1st of each month)
        if day in purchase_days:
            # Scheduler treats plans expiring within renewal_window as already gone
            effective = sum(
                p.coverage_pct for p in active_plans
                if p.end_day > day + renewal_window_days
            )
            gap = target - effective
            if gap > 0.001:
                divided = gap / divider
                purchase = max(divided, min_purchase_pct)
                if gap < min_purchase_pct:
                    purchase = gap
                plan = Plan(purchase, day, day + term_days)
                active_plans.append(plan)
                all_plans.append(plan)

                # Update coverage after purchase
                coverages[-1] = sum(p.coverage_pct for p in active_plans)

    return time_points, coverages, all_plans


def generate_chart(output_path: str = "docs/images/gap-split-lifecycle.png") -> None:
    divider = 2.0
    term_years = 1
    total_years = 5

    # min_purchase = 1/12 of total — at most 12 plans per 1-year term
    min_purchase_pct = 100.0 / 12

    time_points, coverages, all_plans = build_plan_history(
        divider, term_years, total_years, min_purchase_pct
    )

    fig, (ax, ax2, ax3) = plt.subplots(
        3, 1, figsize=(12, 6.5), height_ratios=[3, 1, 1], sharex=True,
        gridspec_kw={"hspace": 0.08},
    )

    # === Top: coverage over time ===
    sample_step = 7
    padding = 30
    sample_days = list(range(-padding, total_years * DAYS_PER_YEAR + padding + 1, sample_step))
    sample_years = [d / DAYS_PER_YEAR for d in sample_days]

    unique_plans = sorted(
        {(p.start_day, p.coverage_pct): p for p in all_plans}.values(),
        key=lambda p: p.start_day,
    )

    plan_contributions = [
        [p.coverage_pct if p.start_day <= d < p.end_day else 0.0 for d in sample_days]
        for p in unique_plans
    ]

    cmap = plt.cm.Blues
    max_c = max(p.coverage_pct for p in unique_plans)
    plan_colors = [cmap(0.25 + 0.55 * (p.coverage_pct / max_c)) for p in unique_plans]

    ax.stackplot(sample_years, *plan_contributions, colors=plan_colors, alpha=0.85)
    ax.axhline(y=100, color="#ff9900", linewidth=2, linestyle="--", label="Target (100%)")
    ax.plot(time_points, coverages, color="#232f3e", linewidth=0.8, label="Total coverage")

    # Annotate coverage at the first purchase of each year
    for y in range(total_years + 1):
        target_time = float(y)
        # Find closest time point after this year boundary
        closest_idx = min(
            range(len(time_points)),
            key=lambda i: abs(time_points[i] - target_time) if time_points[i] >= target_time else float("inf"),
        )
        cov = coverages[closest_idx]
        if cov > 0:
            ax.annotate(
                f"{cov:.0f}%",
                xy=(time_points[closest_idx], cov),
                xytext=(0, 8), textcoords="offset points",
                fontsize=7, color="#232f3e", fontweight="bold",
                ha="center",
            )

    ax.annotate(
        "First renewals — large plans\nreplaced by smaller distributed ones",
        xy=(1.0, 75), xytext=(1.5, 35),
        fontsize=7, color="#555",
        arrowprops=dict(arrowstyle="->", color="#999", lw=0.8),
    )
    ax.annotate(
        "Plans distribute\nrenewals smooth out",
        xy=(4.0, 97), xytext=(4.0, 55),
        fontsize=7, color="#555", ha="center",
        arrowprops=dict(arrowstyle="->", color="#999", lw=0.8),
    )

    ax.set_ylabel("Coverage (%)", fontsize=9)
    ax.set_xlim(-1 / 12, total_years + 1 / 12)
    ax.set_ylim(0, 110)
    ax.tick_params(axis="y", labelsize=8)
    ax.tick_params(axis="x", labelbottom=False)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax.set_title(
        "Gap Split Lifecycle — Monthly Purchases (1st), 1-Year Terms, divider=2",
        fontsize=11, fontweight="bold", pad=8,
    )

    # === Middle: largest plan (%) + active plan count ===
    max_plan_pcts = []
    active_counts = []
    for d in sample_days:
        active = [p for p in all_plans if p.start_day <= d < p.end_day]
        max_plan_pcts.append(max(p.coverage_pct for p in active) if active else 0.0)
        active_counts.append(len(active))

    ax2.fill_between(sample_years, max_plan_pcts, alpha=0.3, color="#c0392b")
    ax2.plot(sample_years, max_plan_pcts, color="#c0392b", linewidth=1.2, label="Largest plan")
    ax2.set_ylabel("Coverage (%)", fontsize=8)
    ax2.set_xlim(0, total_years)
    ax2.set_ylim(0)
    ax2.tick_params(axis="x", labelbottom=False)
    ax2.tick_params(axis="y", labelsize=8)
    ax2.grid(axis="y", alpha=0.2)

    ax2_twin = ax2.twinx()
    ax2_twin.plot(sample_years, active_counts, color="#2980b9", linewidth=1.2, label="Active plans")
    ax2_twin.set_ylabel("Plans", fontsize=8, color="#2980b9")
    ax2_twin.tick_params(axis="y", labelsize=8, colors="#2980b9")
    ax2_twin.set_ylim(0)

    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="right", fontsize=7, framealpha=0.9)

    # === Bottom: days until next plan expires ===
    days_to_next_expiry = []
    for d in sample_days:
        active = [p for p in all_plans if p.start_day <= d < p.end_day]
        if active:
            next_expiry = min(p.end_day for p in active)
            days_to_next_expiry.append(next_expiry - d)
        else:
            days_to_next_expiry.append(0)

    ax3.fill_between(sample_years, days_to_next_expiry, alpha=0.3, color="#27ae60")
    ax3.plot(sample_years, days_to_next_expiry, color="#27ae60", linewidth=1.2, label="Days to next expiry")
    ax3.set_ylabel("Days", fontsize=8)
    ax3.set_xlabel("Time (years)", fontsize=9)
    ax3.set_xlim(-1 / 12, total_years + 1 / 12)
    ax3.set_ylim(0)
    ax3.set_xticks(range(0, total_years + 1))
    ax3.set_xticklabels([f"Y{i}" for i in range(total_years + 1)], fontsize=8)
    ax3.tick_params(axis="y", labelsize=8)
    ax3.grid(axis="y", alpha=0.2)
    ax3.legend(loc="upper right", fontsize=7, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Chart saved to {output_path}")
    plt.close()


if __name__ == "__main__":
    generate_chart()

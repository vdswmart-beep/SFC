"""Charts for the thesis (pure functions): growth of 1 and drawdown, as matplotlib figures."""
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter

# first three categorical colours of the reference palette: checked colour-blind safe as a set
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE, INK, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"


def _axes(title: str) -> tuple[Figure, object]:
    """Empty figure with quiet chrome: hairline horizontal grid, no box, muted ticks."""
    fig = Figure(figsize=(8, 4.5), facecolor=SURFACE)
    ax = fig.subplots()
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=12)
    ax.grid(axis="y", color=GRID, linewidth=0.75)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, length=0)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    return fig, ax


def growth_and_drawdown(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Growth of 1 and drawdown from the previous peak of each column of monthly returns.
    Also used by the web app, so that its charts match the report's."""
    start = returns.index[0] - pd.offsets.MonthEnd(1)  # every curve starts at 1, a month earlier
    growth = pd.concat([pd.DataFrame(1.0, index=[start], columns=returns.columns),
                        (1 + returns).cumprod()])
    return growth, growth / growth.cummax() - 1


def performance_charts(returns: pd.DataFrame) -> dict[str, Figure]:
    """Growth of 1 and drawdown of each column of monthly returns (at most three columns).
    Output: {PNG file name: figure}; the legend carries the values, so no label can collide."""
    growth, drawdown = growth_and_drawdown(returns)
    fig_growth, ax_growth = _axes("Growth of 1, net of costs")
    fig_dd, ax_dd = _axes("Drawdown from the previous peak")
    ax_dd.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    for color, name in zip(COLORS, returns.columns, strict=False):
        end, trough = growth[name].iloc[-1], drawdown[name].idxmin()
        ax_growth.plot(growth.index, growth[name], color=color, linewidth=1.5,
                       label=f"{name}: {end:.2f}")
        ax_growth.plot(growth.index[-1], end, "o", color=color, markersize=6,
                       markeredgecolor=SURFACE, markeredgewidth=1.5)  # end of the curve
        ax_dd.plot(drawdown.index, drawdown[name], color=color, linewidth=1.5,
                   label=f"{name}: max {drawdown[name].min():.0%}")
        ax_dd.plot(trough, drawdown[name].min(), "o", color=color, markersize=6,
                   markeredgecolor=SURFACE, markeredgewidth=1.5)  # deepest point
    for ax in [ax_growth, ax_dd]:  # legend under the plot: it can never hide a curve
        ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3,
                  labelcolor=INK, fontsize=9)
    return {"cumulative.png": fig_growth, "drawdown.png": fig_dd}

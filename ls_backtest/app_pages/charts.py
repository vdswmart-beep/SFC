"""Interactive charts of the web app (Altair), in the colors of the report's charts."""
import altair as alt
import pandas as pd

from src.charts import COLORS

RED, GRAY, BLUE = "#c8453c", "#d9d8d2", "#2a78d6"  # SHORT, small weight, LONG


def line_chart(lines: pd.DataFrame, number_format: str) -> alt.Chart:
    """One line per column (monthly index), in the colors of the report, values on hover."""
    long = lines.rename_axis("Month").reset_index().melt("Month", var_name="Series",
                                                          value_name="Value")
    colors = alt.Scale(domain=list(lines.columns), range=COLORS[: len(lines.columns)])
    return alt.Chart(long).mark_line().encode(
        x=alt.X("Month:T", title=None, axis=alt.Axis(format="%Y-%m")),
        y=alt.Y("Value:Q", title=None, axis=alt.Axis(format=number_format),
                scale=alt.Scale(zero=False)),
        color=alt.Color("Series:N", scale=colors, legend=alt.Legend(orient="bottom", title=None)),
        tooltip=[alt.Tooltip("Month:T", format="%Y-%m"), "Series",
                 alt.Tooltip("Value:Q", format=number_format)],
    )


def heatmap(cells: pd.DataFrame, row: str) -> alt.Chart:
    """Weights over time: one row per value of `row` (a stock or a sector), one column per
    month; blue = LONG, red = SHORT. Input: columns Month, Weight, `row` and tooltip fields."""
    limit = cells["Weight"].abs().max()
    # "lab": a straight fade from gray to each color (the default bends through other hues)
    color = alt.Scale(domain=[-limit, 0, limit], range=[RED, GRAY, BLUE], interpolate="lab")
    tooltip = [field for field in ["Month", "Ticker", "Sector", "Side"] if field in cells]
    return alt.Chart(cells).mark_rect().encode(
        x=alt.X("Month:O", title=None),
        y=alt.Y(f"{row}:N", sort="ascending", title=None,
                axis=alt.Axis(labelOverlap=False, labelLimit=320)),
        # legend above the rows: it stays readable even when the heatmap has only a few rows
        color=alt.Color("Weight:Q", scale=color,
                        legend=alt.Legend(format="%", title="Weight", orient="top")),
        tooltip=[*tooltip, alt.Tooltip("Weight:Q", format=".1%")],
    ).properties(height=alt.Step(20))  # 20 pixels per row, whatever the number of rows


def sector_bars(exposure: pd.DataFrame) -> alt.Chart:
    """Exposure by sector: LONG bar to the right, SHORT bar to the left, net as a black tick.
    Input: explain.sector_exposure output."""
    table = exposure.reset_index()
    order = table["Sector"].tolist()  # largest net exposure on top
    bars = alt.Chart(table.melt("Sector", ["LONG", "SHORT"], "Side", "Weight")).mark_bar().encode(
        x=alt.X("Weight:Q", title=None, axis=alt.Axis(format="%")),
        y=alt.Y("Sector:N", sort=order, title=None, axis=alt.Axis(labelLimit=320)),
        color=alt.Color("Side:N", scale=alt.Scale(domain=["LONG", "SHORT"], range=[BLUE, RED]),
                        legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["Sector", "Side", alt.Tooltip("Weight:Q", format=".1%")],
    )
    net = alt.Chart(table).mark_tick(color="#0b0b0b", thickness=3, size=20).encode(
        x="Net:Q", y=alt.Y("Sector:N", sort=order),
        tooltip=["Sector", alt.Tooltip("Net:Q", format=".1%")],
    )
    return (bars + net).properties(height=32 * len(table) + 40)

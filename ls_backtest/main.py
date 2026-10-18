"""Command line: runs the model in the mode set by LONG_ONLY in config.py, prints the tables and
writes the CSV files, the Excel report and the charts. Usage: python main.py [data folder]."""
import sys
from pathlib import Path

import config
from model import run_model
from src.charts import performance_charts
from src.data import load_data, make_fake_data
from src.export import save_outputs


def main(folder: str | None = None) -> dict:
    """Runs the model, prints the tables and writes the outputs.
    Input: folder of CSV files (None = fake data); output: the run (see model.run_model)."""
    data = load_data(folder) if folder else make_fake_data()
    run = run_model(data, config.LONG_ONLY)
    print(f"Mode: {run['mode']}")
    for title, table in run["tables"].items():
        if title != "Monthly returns":  # too long for the console: see the Excel report
            print(f"\n=== {title} ===\n" + table.to_string(float_format="{:.3f}".format))
    # one sub-folder per mode: the two reports can be compared side by side
    out = Path(config.OUTPUT_DIR) / ("long_only" if config.LONG_ONLY else "long_short")
    save_outputs(run["tables"], performance_charts(run["curves"]), str(out))
    print(f"\nCSV tables, report.xlsx and charts written to {out}/")
    return run


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)

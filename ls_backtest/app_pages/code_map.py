"""Code map page: where to change what, the role of each file, and the code itself."""
import ast
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parents[1]  # the ls_backtest folder
FOLDERS = {".": "Run and settings", "src": "The model", "app_pages": "The web app",
           "tests": "Tests"}
CHANGES = [  # (what to change, where to change it)
    ("Long/short or long-only", "config.py → LONG_ONLY, or the toggle in the sidebar"),
    ("Number of positions", "config.py → N_POSITIONS (even number: 20 = 10 LONG + 10 SHORT)"),
    ("A signal, or a new one", "src/signals.py → compute_signals, then config.py → SIGNALS; "
                               "its words in this app: src/explain.py → WORDS"),
    ("How pairs are chosen and weighted", "src/portfolio.py → _sector_pairs, _date_weights"),
    ("The exclusion rule (H1)", "config.py → EXCL_THRESHOLD; src/portfolio.py → _eligible"),
    ("Costs", "config.py → TC_BPS, BORROW_BPS_YR; their grids TC_GRID_BPS, BORROW_GRID_BPS_YR"),
    ("The beta hedge", "config.py → BETA_HEDGE, BETA_WINDOW; src/backtest.py → _hedge"),
    ("The strategies compared", "model.py → build_strategies"),
    ("A table of the report", "src/report.py, then model.py → build_tables"),
    ("The data source", "fetch_yahoo.py (Yahoo) or bloomberg_to_csv.py (Bloomberg)"),
    ("This web app", "app.py (sidebar, cache), then app_pages/ (one file per page)"),
]


def project_files() -> list[Path]:
    """The project's Python files, folder by folder (empty package markers left out)."""
    files = [sorted((ROOT / folder).glob("*.py")) for folder in FOLDERS]
    return [path for group in files for path in group if path.name != "__init__.py"]


def name_of(path: Path) -> str:
    """Path of a file inside the project, e.g. 'src/data.py'."""
    return path.relative_to(ROOT).as_posix()


def docstring(node: ast.AST) -> str:
    """The docstring of a module or of a function, on one line."""
    return " ".join((ast.get_docstring(node) or "").split())


def role(path: Path) -> str:
    """What a file does: the first sentence of its docstring."""
    text = docstring(ast.parse(path.read_text(encoding="utf-8")))
    return text.split(". ")[0].removesuffix(".") + "."


def functions(path: Path) -> pd.DataFrame:
    """The functions of one file: name, lines and docstring."""
    rows = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.FunctionDef):
            rows.append({"Function": node.name, "Lines": f"{node.lineno}-{node.end_lineno}",
                         "What it does": docstring(node)})
    return pd.DataFrame(rows, columns=["Function", "Lines", "What it does"])


st.title("Code map")
st.markdown("Every file is short and every function does one thing, said in its docstring. "
            "The tables below are read from the code itself, so they are always up to date.")
st.subheader("Where to change what")
st.table(pd.DataFrame(CHANGES, columns=["To change", "Go to"]), hide_index=True)
st.subheader("The files")
files = project_files()
folders = [FOLDERS[path.parent.relative_to(ROOT).as_posix()] for path in files]
st.table(pd.DataFrame({"Part": folders, "File": [name_of(p) for p in files],
                       "Role": [role(p) for p in files]}), hide_index=True)
st.subheader("Read the code")
chosen = st.selectbox("File", files, index=files.index(ROOT / "model.py"), format_func=name_of)
st.table(functions(chosen), hide_index=True)
st.code(chosen.read_text(encoding="utf-8"), language="python", line_numbers=True)

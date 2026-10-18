"""Smoke test of the web app: every page runs without error, in both modes, on the first data
source of the sidebar (a folder of data/ if there is one, else the fake data)."""
from streamlit.testing.v1 import AppTest

PAGES = ["app_pages/how_it_works.py", "app_pages/code_map.py", "app_pages/portfolio.py",
         "app_pages/performance.py"]


def test_every_page_in_both_modes() -> None:
    """Long/short then long-only (the sidebar toggle): each page in turn."""
    app = AppTest.from_file("../app.py", default_timeout=180).run()
    assert not app.exception, app.exception
    for long_only in [False, True]:
        app.sidebar.toggle[0].set_value(long_only).run()
        weights = app.session_state["run"]["strategies"].values()
        shorts = sum(int((w < 0).to_numpy().sum()) for w in weights)
        assert (shorts == 0) == long_only  # the switch: not a single SHORT in long-only mode
        for page in PAGES:
            app.switch_page(page).run()
            assert not app.exception, (page, app.exception)

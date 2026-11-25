from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_app_runs_end_to_end():
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=30).run()
    assert not at.exception
    at.sidebar.button[0].click().run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 6

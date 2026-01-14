import importlib.util
import sys
from pathlib import Path

import pytest


# ============================================================
# Helper Classes and Functions
# ============================================================

class _FakeSoundDevice:
    """
    Fake replacement for the `sounddevice` module used during testing.

    This class prevents real audio hardware access when importing
    ai_integrated_mechanism.py. It simulates the minimal behavior
    required by the prefer_wasapi() function.
    """

    class _Default:
        """
        Simulates sounddevice.default settings.
        """
        hostapi = None
        device = (0, 0)

    default = _Default()

    @staticmethod
    def query_hostapis():
        """
        Simulates sounddevice.query_hostapis().

        @return list of dicts representing available host APIs,
                including WASAPI so prefer_wasapi() can succeed
        """
        return [
            {"name": "MME"},
            {"name": "WASAPI"},
        ]


def _import_target_module(tmp_path, monkeypatch):
    """
    Safely imports ai_integrated_mechanism.py for unit testing.

    This function:
    - Replaces the real sounddevice module with a fake stub
    - Prevents hardware access during import
    - Dynamically loads the target module from the project root

    @param tmp_path   Pytest temporary path fixture (unused but required by pytest)
    @param monkeypatch Pytest fixture used to modify sys.modules
    @return Imported ai_integrated_mechanism module
    @throws FileNotFoundError if the target script cannot be located
    """

    # Inject fake sounddevice before importing the module
    monkeypatch.setitem(sys.modules, "sounddevice", _FakeSoundDevice)

    # Locate ai_integrated_mechanism.py in the project root
    project_root = Path(__file__).resolve().parents[1]
    script_path = project_root / "ai_integrated_mechanism.py"

    if not script_path.exists():
        raise FileNotFoundError(
            f"Could not find {script_path}. Put ai_integrated_mechanism.py in the project root."
        )

    # Dynamically import the module
    spec = importlib.util.spec_from_file_location("ai_integrated_mechanism", script_path)
    assert spec and spec.loader

    module = importlib.util.module_from_spec(spec)
    sys.modules["ai_integrated_mechanism"] = module
    spec.loader.exec_module(module)

    return module


# ============================================================
# Unit Tests: LiveLine Class
# ============================================================

def test_liveline_init_default_prefix(monkeypatch, tmp_path):
    """
    Tests that LiveLine initializes correctly using default values.

    Verifies:
    - Default prefix is set correctly
    - Internal text buffer starts empty
    """
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine()

    assert ll.prefix == "You: "
    assert ll.buf == ""


def test_liveline_init_custom_prefix(monkeypatch, tmp_path):
    """
    Tests LiveLine initialization with a custom prefix.

    Verifies:
    - Custom prefix is stored correctly
    - Text buffer starts empty
    """
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine(prefix="Test> ")

    assert ll.prefix == "Test> "
    assert ll.buf == ""


def test_liveline_clear_writes_ansi_clear_and_carriage_return(monkeypatch, tmp_path, capsys):
    """
    Tests that clear() outputs the correct ANSI escape sequence.

    Verifies:
    - The terminal line is cleared using ANSI escape codes
    - The cursor returns to the start of the line
    """
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine()

    ll.clear()

    out = capsys.readouterr().out
    assert out == ll.CSI + "2K\r"


def test_liveline_print_updates_buffer_and_writes_prefix_and_text(
    monkeypatch, tmp_path, capsys
):
    """
    Tests the print() method behavior.

    Verifies:
    - Internal buffer is updated with new text
    - The current terminal line is cleared
    - The prefix and text are printed on the same line
    """
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine(prefix="P: ")

    ll.print("hello")

    out = capsys.readouterr().out
    assert ll.buf == "hello"
    assert out == (ll.CSI + "2K\r" + "P: hello")


def test_liveline_finalize_clears_and_prints_newline(monkeypatch, tmp_path, capsys):
    """
    Tests the finalize() method.

    Verifies:
    - The line is cleared before final output
    - Final text is printed with a newline
    - The output format matches expected terminal behavior
    """
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine(prefix="You: ")

    ll.finalize("final words")

    out = capsys.readouterr().out
    assert out.startswith(ll.CSI + "2K\r")
    assert out.endswith("You: final words\n")

import importlib.util
import sys
from pathlib import Path

import pytest


# --------------------------
# Helpers: safe module import
# --------------------------

class _FakeSoundDevice:
    """Minimal stub to satisfy prefer_wasapi() during import."""
    class _Default:
        hostapi = None
        device = (0, 0)

    default = _Default()

    @staticmethod
    def query_hostapis():
        # Include a WASAPI entry so prefer_wasapi can set default.hostapi
        return [
            {"name": "MME"},
            {"name": "WASAPI"},
        ]


def _import_target_module(tmp_path, monkeypatch):
    """
    Import the user's script as a module without running real sounddevice logic.
    Assumes the file is in the project root or alongside tests.
    """
    # Stub sounddevice BEFORE import
    monkeypatch.setitem(sys.modules, "sounddevice", _FakeSoundDevice)

    # You can adjust this path if your tests folder is elsewhere.
    # This looks for ai_integrated_mechanism.py at the repo root.
    project_root = Path(__file__).resolve().parents[1]
    script_path = project_root / "ai_integrated_mechanism.py"

    if not script_path.exists():
        raise FileNotFoundError(
            f"Could not find {script_path}. Put ai_integrated_mechanism.py in the project root."
        )

    spec = importlib.util.spec_from_file_location("ai_integrated_mechanism", script_path)
    assert spec and spec.loader

    module = importlib.util.module_from_spec(spec)
    sys.modules["ai_integrated_mechanism"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------
# Tests: LiveLine class
# --------------------------

def test_liveline_init_default_prefix(monkeypatch, tmp_path):
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine()
    assert ll.prefix == "You: "
    assert ll.buf == ""


def test_liveline_init_custom_prefix(monkeypatch, tmp_path):
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine(prefix="Test> ")
    assert ll.prefix == "Test> "
    assert ll.buf == ""


def test_liveline_clear_writes_ansi_clear_and_carriage_return(monkeypatch, tmp_path, capsys):
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine()

    ll.clear()

    out = capsys.readouterr().out
    # clear() writes CSI + "2K\r"
    assert out == ll.CSI + "2K\r"


def test_liveline_print_updates_buffer_and_writes_prefix_and_text(monkeypatch, tmp_path, capsys):
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine(prefix="P: ")

    ll.print("hello")

    out = capsys.readouterr().out
    # clear() then writes prefix+text (no newline)
    assert ll.buf == "hello"
    assert out == (ll.CSI + "2K\r" + "P: hello")


def test_liveline_finalize_clears_and_prints_newline(monkeypatch, tmp_path, capsys):
    m = _import_target_module(tmp_path, monkeypatch)
    ll = m.LiveLine(prefix="You: ")

    ll.finalize("final words")

    out = capsys.readouterr().out
    # finalize does clear() (no newline), then print(prefix+final) (with newline)
    assert out.startswith(ll.CSI + "2K\r")
    assert out.endswith("You: final words\n")

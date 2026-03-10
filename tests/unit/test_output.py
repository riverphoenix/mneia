from __future__ import annotations

import io
import json

import pytest

from mneia.output import Output, OutputMode, _detect_no_color, get_output, reset_output


@pytest.fixture(autouse=True)
def _reset():
    reset_output()
    yield
    reset_output()


def test_default_mode():
    output = Output()
    assert output.mode in (OutputMode.RICH, OutputMode.PLAIN)


def test_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    assert _detect_no_color() is True


def test_no_color_env_any_value(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert _detect_no_color() is True


def test_no_color_unset(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    assert _detect_no_color() is False


def test_term_dumb(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "dumb")
    assert _detect_no_color() is True


def test_configure_json_mode():
    output = Output()
    output.configure(json_mode=True)
    assert output.mode == OutputMode.JSON
    assert output.is_json is True


def test_configure_no_color():
    output = Output()
    output.configure(no_color=True)
    assert output.mode == OutputMode.PLAIN


def test_configure_no_input():
    output = Output()
    output.configure(no_input=True)
    assert output.no_input is True


def test_print_suppressed_in_json_mode(capsys):
    output = Output()
    output.configure(json_mode=True)
    output.print("should not appear")
    captured = capsys.readouterr()
    assert "should not appear" not in captured.out


def test_print_suppressed_in_quiet_mode(capsys):
    output = Output()
    output.configure(quiet=True)
    output.print("should not appear")
    captured = capsys.readouterr()
    assert "should not appear" not in captured.out


def test_error_always_outputs(capsys):
    output = Output()
    output.configure(json_mode=True)
    output.error("something failed")
    captured = capsys.readouterr()
    assert "something failed" in captured.err


def test_debug_hidden_by_default(capsys):
    output = Output()
    output.debug("debug info")
    captured = capsys.readouterr()
    assert "debug info" not in captured.err


def test_debug_shown_when_verbose(capsys):
    output = Output()
    output.configure(verbose=True)
    output.debug("debug info")
    captured = capsys.readouterr()
    assert "debug info" in captured.err


def test_json_result(capsys):
    output = Output()
    output.configure(json_mode=True)
    output.json_result({"key": "value"})
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["key"] == "value"


def test_get_output_singleton():
    a = get_output()
    b = get_output()
    assert a is b


def test_reset_output():
    a = get_output()
    reset_output()
    b = get_output()
    assert a is not b


def test_safe_prompt_no_input():
    output = Output()
    output.configure(no_input=True)
    result = output.safe_prompt("Name", default="fallback")
    assert result == "fallback"


def test_safe_prompt_no_input_no_default():
    from click.exceptions import Exit

    output = Output()
    output.configure(no_input=True)
    with pytest.raises(Exit):
        output.safe_prompt("Name")


def test_safe_confirm_no_input():
    output = Output()
    output.configure(no_input=True)
    assert output.safe_confirm("Continue?", default=False) is False
    assert output.safe_confirm("Continue?", default=True) is True


def test_success_suppressed_in_quiet(capsys):
    output = Output()
    output.configure(quiet=True)
    output.success("done")
    captured = capsys.readouterr()
    assert "done" not in captured.out


def test_emit_json_mode(capsys):
    output = Output()
    output.configure(json_mode=True)
    output.emit(data={"count": 42}, rich_fn=lambda: None)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["count"] == 42


def test_emit_rich_mode():
    called = []
    output = Output()
    output.emit(data={"count": 42}, rich_fn=lambda: called.append(1))
    assert called == [1]

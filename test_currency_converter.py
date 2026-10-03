import logging
import pytest
import currency_converter as cc

LEAK_MARKERS = ["Traceback", "InvalidOperation", "Decimal", "ConversionError", ".py", "line "]

# (case id, args, expected error code, text the user must see)
FAILURES = [
    ("empty amount",         ("", "USD", "EUR"),            "EMPTY_INPUT",        "enter an amount"),
    ("whitespace amount",    ("   ", "USD", "EUR"),         "EMPTY_INPUT",        "enter an amount"),
    ("empty currency",       ("10", "", "EUR"),             "EMPTY_INPUT",        "currency code"),
    ("very long amount",     ("9" * 5000, "USD", "EUR"),    "INPUT_TOO_LONG",     "too long"),
    ("very long currency",   ("10", "U" * 5000, "EUR"),     "INPUT_TOO_LONG",     "too long"),
    ("None amount",          (None, "USD", "EUR"),          "BAD_TYPE",           "must be a number"),
    ("list amount",          ([1, 2], "USD", "EUR"),        "BAD_TYPE",           "must be a number"),
    ("dict amount",          ({"a": 1}, "USD", "EUR"),      "BAD_TYPE",           "must be a number"),
    ("bool amount",          (True, "USD", "EUR"),          "BAD_TYPE",           "must be a number"),
    ("int currency",         ("10", 123, "EUR"),            "BAD_TYPE",           "three-letter code"),
    ("text amount",          ("abc", "USD", "EUR"),         "NOT_A_NUMBER",       "valid amount"),
    ("NaN",                  ("nan", "USD", "EUR"),         "NOT_FINITE",         "real number"),
    ("infinity",             ("inf", "USD", "EUR"),         "NOT_FINITE",         "real number"),
    ("zero",                 ("0", "USD", "EUR"),           "NOT_POSITIVE",       "greater than zero"),
    ("negative",             ("-5", "USD", "EUR"),          "NOT_POSITIVE",       "greater than zero"),
    ("too large",            ("1e12", "USD", "EUR"),        "AMOUNT_TOO_LARGE",   "too large"),
    ("bad currency format",  ("10", "US1", "EUR"),          "BAD_CURRENCY_FORMAT","three letters"),
    ("unknown currency",     ("10", "USD", "XYZ"),          "UNKNOWN_CURRENCY",   "isn't supported"),
]


@pytest.mark.parametrize("name,args,code,expected", FAILURES, ids=[f[0] for f in FAILURES])
def test_failure_is_graceful(name, args, code, expected, caplog):
    with caplog.at_level(logging.INFO, logger="currency_converter"):
        ok, message = cc.safe_convert(*args)
    assert ok is False
    assert expected in message
    assert not any(m in message for m in LEAK_MARKERS), message
    assert len(message) < 200  # huge input is never echoed back
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert f"code={code}" in logged
    assert "9" * 100 not in logged and "U" * 100 not in logged  # logs are truncated too


def test_unexpected_error_hides_internals_but_logs_traceback(monkeypatch, caplog):
    def boom(*a):
        raise RuntimeError("secret-db-password")
    monkeypatch.setattr(cc, "_compute", boom)
    with caplog.at_level(logging.INFO, logger="currency_converter"):
        ok, message = cc.safe_convert("10", "USD", "EUR")
    assert ok is False
    assert "secret-db-password" not in message and "RuntimeError" not in message
    assert "reference" in message
    record = caplog.records[-1]
    assert record.levelno == logging.ERROR and record.exc_info
    assert "secret-db-password" in caplog.text
    ref = message.split("reference ")[1].rstrip(".")
    assert ref in caplog.text  # user's reference ID matches the log


def test_success():
    assert cc.safe_convert("100", "usd", "ngn") == (True, "100.00 USD = 150,000.00 NGN")
    assert cc.safe_convert(25.5, " eur ", "GBP")[0] is True


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CONVERTER_LOG", str(tmp_path / "t.log"))
    assert cc.main(["100", "USD", "EUR"]) == 0
    assert cc.main(["", "USD", "EUR"]) == 1
    assert cc.main([]) == 2
    assert "Usage" in capsys.readouterr().out

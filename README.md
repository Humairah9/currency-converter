# Currency Converter: graceful failure demo

[![tests](https://github.com/Humairah9/currency-converter/actions/workflows/tests.yml/badge.svg)](https://github.com/Humairah9/currency-converter/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

A small Python CLI that converts amounts between USD, EUR, GBP, JPY and NGN using a **fixed local rate table**. It makes no network calls. The point of the project is the error handling: every bad input produces a clear, safe message for the user and a useful log line for the developer.

## Run it

```bash
python currency_converter.py 100 USD NGN     # 100.00 USD = 150,000.00 NGN
python currency_converter.py "" USD NGN      # Please enter an amount, for example 100.
```

Exit codes: `0` success, `1` conversion failed, `2` wrong number of arguments.
Logs go to `converter.log` (override with the `CONVERTER_LOG` env var).

## Test it

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

The same tests run automatically on GitHub for Python 3.9 to 3.13 (see `.github/workflows/tests.yml`).

## How errors are handled

- Expected bad input raises `ConversionError(code, user_message, log_detail)`.
- `safe_convert()` catches it, logs a **WARNING** with the code, and returns only `user_message`.
- Anything unexpected is a bug. The user sees a generic message with a random reference ID. The full traceback is logged at **ERROR** under the same ID, so support can find it.
- Logs never contain more than 30 characters of an input (type and length are recorded instead), so a 5,000-character paste can't flood the log.

## Failure cases

| # | Case | Example input | User sees | Logged (WARNING) |
|---|------|---------------|-----------|------------------|
| 1 | Empty or whitespace | `""`, `"   "` | "Please enter an amount, for example 100." (or "...a currency code, such as USD or NGN.") | `code=EMPTY_INPUT field=<which>` |
| 2 | Very long input | 5,000 digits | "That amount is too long (limit is 32 characters). Please enter a shorter value." | `code=INPUT_TOO_LONG field=... type=str len=5000 value='99999...'(truncated)` |
| 3 | Unexpected type | `None`, `[1,2]`, `{}`, `True`, int currency | "Amount must be a number like 100 or 25.50." (or "Currency must be a three-letter code like USD.") | `code=BAD_TYPE field=... type=list len=2 value=[1, 2]` |
| 4 | Not a number | `abc` | "That doesn't look like a valid amount. Use digits only, like 100 or 25.50." | `code=NOT_A_NUMBER ... value='abc'` |
| 5 | NaN / infinity | `nan`, `inf` | "Please enter a real number (not NaN or infinity)." | `code=NOT_FINITE ...` |
| 6 | Zero or negative | `0`, `-5` | "Amount must be greater than zero." | `code=NOT_POSITIVE ...` |
| 7 | Amount too large | `1e12` | "Amount is too large. The maximum is 1,000,000,000." | `code=AMOUNT_TOO_LARGE ...` |
| 8 | Malformed currency code | `US1` | "Currency codes are exactly three letters, like USD or NGN." | `code=BAD_CURRENCY_FORMAT ...` |
| 9 | Unsupported currency | `XYZ` | "Currency 'XYZ' isn't supported. Supported: EUR, GBP, JPY, NGN, USD." | `code=UNKNOWN_CURRENCY field=... code=XYZ` |
| 10 | Unexpected internal error (bug) | n/a | "Something went wrong on our side. Please try again; if it persists, quote reference `a1b2c3d4`." | **ERROR** `conversion_crashed ref=a1b2c3d4` plus full traceback |
| 11 | Wrong CLI argument count | `python currency_converter.py 5` | Usage text with an example | nothing (exit code 2) |

Each of cases 1 to 10 has a matching test in `test_currency_converter.py`. The tests also assert that the user message contains no `Traceback`, exception class names or file paths, that long input is never echoed back, and that the reference ID shown to the user appears in the log.

## Real output

Commands run against the program, with what the user saw and the matching lines from `converter.log`:

```text
$ python currency_converter.py "" USD NGN
Please enter an amount, for example 100.

$ python currency_converter.py abc USD NGN
That doesn't look like a valid amount. Use digits only, like 100 or 25.50.

$ python currency_converter.py 10 USD XYZ
Currency 'XYZ' isn't supported. Supported: EUR, GBP, JPY, NGN, USD.
```

```text
WARNING currency_converter conversion_failed code=EMPTY_INPUT field=amount
WARNING currency_converter conversion_failed code=NOT_A_NUMBER field=amount type=str len=3 value='abc'
WARNING currency_converter conversion_failed code=UNKNOWN_CURRENCY field=to currency code=XYZ
```

For an unexpected bug (simulated here by forcing a divide-by-zero), the user sees only the generic message and a reference ID. The log holds the cause:

```text
Something went wrong on our side. Please try again; if it persists, quote reference 2b4fe46d.
```

```text
ERROR currency_converter conversion_crashed ref=2b4fe46d
Traceback (most recent call last):
  ...
```

## Notes

The rates are illustrative, not real market data.

Licensed under the MIT License (see `LICENSE`).

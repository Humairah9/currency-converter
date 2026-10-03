"""Tiny currency converter using a fixed local rate table (no network calls).

Every expected failure raises ConversionError, which carries:
  - code:         stable identifier, used in logs and the README
  - user_message: safe, actionable text shown to the user
  - log_detail:   extra context for the log only
Anything else is treated as a bug: the user gets a generic message plus a
reference ID, and the full traceback goes to the log under that ID.
"""
import logging
import os
import re
import sys
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

log = logging.getLogger("currency_converter")

# Fixed, illustrative rates: units of currency per 1 USD.
RATES_PER_USD = {
    "USD": Decimal("1"),
    "EUR": Decimal("0.92"),
    "GBP": Decimal("0.79"),
    "JPY": Decimal("150"),
    "NGN": Decimal("1500"),
}
MAX_INPUT_LEN = 32
MAX_AMOUNT = Decimal("1000000000")
_CODE_RE = re.compile(r"^[A-Z]{3}$")


class ConversionError(Exception):
    def __init__(self, code, user_message, log_detail=""):
        super().__init__(code)
        self.code = code
        self.user_message = user_message
        self.log_detail = log_detail


def _describe(value):
    """Log-safe summary of an input: type, length, truncated repr."""
    text = repr(value)
    if len(text) > 30:
        text = text[:30] + "...(truncated)"
    length = len(value) if isinstance(value, (str, bytes, list, tuple, dict)) else "n/a"
    return f"type={type(value).__name__} len={length} value={text}"


def _clean_text(value, field):
    allowed = (str, int, float, Decimal) if field == "amount" else (str,)
    if value is None or isinstance(value, bool) or not isinstance(value, allowed):
        msg = ("Amount must be a number like 100 or 25.50." if field == "amount"
               else "Currency must be a three-letter code like USD.")
        raise ConversionError("BAD_TYPE", msg, f"field={field} {_describe(value)}")
    text = str(value).strip()
    if not text:
        msg = ("Please enter an amount, for example 100." if field == "amount"
               else "Please enter a currency code, such as USD or NGN.")
        raise ConversionError("EMPTY_INPUT", msg, f"field={field}")
    if len(text) > MAX_INPUT_LEN:
        raise ConversionError(
            "INPUT_TOO_LONG",
            f"That {field} is too long (limit is {MAX_INPUT_LEN} characters). Please enter a shorter value.",
            f"field={field} {_describe(text)}",
        )
    return text


def _parse_amount(value):
    text = _clean_text(value, "amount")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ConversionError(
            "NOT_A_NUMBER",
            "That doesn't look like a valid amount. Use digits only, like 100 or 25.50.",
            f"field=amount {_describe(text)}",
        ) from None
    if not amount.is_finite():
        raise ConversionError("NOT_FINITE", "Please enter a real number (not NaN or infinity).",
                              f"field=amount {_describe(text)}")
    if amount <= 0:
        raise ConversionError("NOT_POSITIVE", "Amount must be greater than zero.",
                              f"field=amount {_describe(text)}")
    if amount > MAX_AMOUNT:
        raise ConversionError("AMOUNT_TOO_LARGE",
                              f"Amount is too large. The maximum is {MAX_AMOUNT:,}.",
                              f"field=amount {_describe(text)}")
    return amount


def _parse_currency(value, field):
    text = _clean_text(value, field).upper()
    if not _CODE_RE.match(text):
        raise ConversionError("BAD_CURRENCY_FORMAT",
                              "Currency codes are exactly three letters, like USD or NGN.",
                              f"field={field} {_describe(text)}")
    if text not in RATES_PER_USD:
        raise ConversionError(
            "UNKNOWN_CURRENCY",
            f"Currency '{text}' isn't supported. Supported: {', '.join(sorted(RATES_PER_USD))}.",
            f"field={field} code={text}",
        )
    return text


def _compute(amount, src, dst):
    result = amount / RATES_PER_USD[src] * RATES_PER_USD[dst]
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def convert(amount, from_code, to_code):
    """Return (parsed_amount, result). Raises ConversionError on bad input."""
    amt = _parse_amount(amount)
    src = _parse_currency(from_code, "from currency")
    dst = _parse_currency(to_code, "to currency")
    return amt, src, dst, _compute(amt, src, dst)


def safe_convert(amount, from_code, to_code):
    """Never raises. Returns (ok: bool, message: str) for display to the user."""
    try:
        amt, src, dst, result = convert(amount, from_code, to_code)
        return True, f"{amt:,.2f} {src} = {result:,.2f} {dst}"
    except ConversionError as err:
        log.warning("conversion_failed code=%s %s", err.code, err.log_detail)
        return False, err.user_message
    except Exception:  # unexpected: a bug, not bad input
        ref = uuid.uuid4().hex[:8]
        log.exception("conversion_crashed ref=%s", ref)
        return False, f"Something went wrong on our side. Please try again; if it persists, quote reference {ref}."


def main(argv):
    logging.basicConfig(
        filename=os.environ.get("CONVERTER_LOG", "converter.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if len(argv) != 3:
        print("Usage: python currency_converter.py AMOUNT FROM TO\nExample: python currency_converter.py 100 USD NGN")
        return 2
    ok, message = safe_convert(*argv)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

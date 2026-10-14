"""
validators.py - checks incoming data and raises ONE kind of error: ApiError.
app.py turns every ApiError into   {"error": "...", "details": {...}}
"""
import math
import re
from datetime import datetime

from flask import request

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ApiError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object (send header Content-Type: application/json)", 400)
    return data


def is_valid_date(value):
    if not isinstance(value, str) or not DATE_PATTERN.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


class Fields:
    """Collects ALL problems in a request, so the user can fix them in one go."""

    def __init__(self, data):
        self.data = data
        self.errors = {}

    def error(self, field, message):
        self.errors.setdefault(field, message)

    def done(self):
        if self.errors:
            raise ApiError("Validation failed", 400, self.errors)

    def _missing(self, name, required):
        if required:
            self.error(name, f"{name} is required")

    def text(self, name, required=False, min_len=None, max_len=None, choices=None, default=None, strip=True):
        raw = self.data.get(name)
        if raw is None or (isinstance(raw, str) and (raw.strip() if strip else raw) == ""):
            self._missing(name, required)
            return default
        if not isinstance(raw, str):
            self.error(name, f"{name} must be text")
            return default
        value = raw.strip() if strip else raw
        if min_len is not None and len(value) < min_len:
            self.error(name, f"{name} must be at least {min_len} characters")
        if max_len is not None and len(value) > max_len:
            self.error(name, f"{name} must be at most {max_len} characters")
        if choices is not None:
            by_lower = {c.lower(): c for c in choices}
            if value.lower() not in by_lower:
                self.error(name, f"{name} must be one of: {', '.join(choices)}")
                return default
            value = by_lower[value.lower()]
        return value

    def integer(self, name, required=False, minimum=None, maximum=None, default=None):
        raw = self.data.get(name)
        if raw is None or raw == "":
            self._missing(name, required)
            return default
        if isinstance(raw, bool) or not isinstance(raw, int):
            self.error(name, f"{name} must be a whole number")
            return default
        if minimum is not None and raw < minimum:
            self.error(name, f"{name} must be at least {minimum}")
        if maximum is not None and raw > maximum:
            self.error(name, f"{name} must be at most {maximum}")
        return raw

    def number(self, name, required=False, greater_than=None, minimum=None, maximum=None, default=None):
        raw = self.data.get(name)
        if raw is None or raw == "":
            self._missing(name, required)
            return default
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
            self.error(name, f"{name} must be a number")
            return default
        if greater_than is not None and raw <= greater_than:
            self.error(name, f"{name} must be greater than {greater_than}")
        if minimum is not None and raw < minimum:
            self.error(name, f"{name} must be at least {minimum}")
        if maximum is not None and raw > maximum:
            self.error(name, f"{name} must be at most {maximum}")
        return float(raw)

    def date(self, name, required=False, default=None):
        raw = self.data.get(name)
        if raw is None or raw == "":
            self._missing(name, required)
            return default
        if not is_valid_date(raw):
            self.error(name, f"{name} must be a real date in YYYY-MM-DD format, e.g. 2026-10-31")
            return default
        return raw


def query_int(name, default, minimum=None, maximum=None):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError("Invalid query parameter", 400, {name: f"{name} must be a whole number"})
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ApiError("Invalid query parameter", 400, {name: f"{name} must be between {minimum} and {maximum}"})
    return value


def query_date(name):
    raw = request.args.get(name)
    if not raw:
        return None
    if not is_valid_date(raw):
        raise ApiError("Invalid query parameter", 400, {name: f"{name} must be a date like 2026-10-31"})
    return raw

"""Minimal client for the Alani Insights REST API. Standard library only.

The API key is read from the ALANI_API_KEY environment variable and is never
printed or written to disk by this module.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("ALANI_API_BASE", "https://api.alaniinsights.com/v1")


class InsightsError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {str(body)[:300]}")
        self.status = status
        self.body = body


def _key():
    key = os.environ.get("ALANI_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "Set ALANI_API_KEY in your environment first. See .env.example."
        )
    return key


def request(method, path, body=None, query=None, timeout=60):
    """One HTTP call. Returns (status, parsed_body). Never raises on HTTP errors."""
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"x-api-key": _key()}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as err:
        raw = err.read().decode()
        try:
            return err.code, json.loads(raw)
        except ValueError:
            return err.code, raw[:300]


def call(method, path, body=None, query=None, retries=4):
    """Like request(), but retries server errors and raises on failure.

    Only use for calls that are safe to repeat. A create is NOT safe to repeat
    blindly: if the response was lost, the record may already exist. Use
    create_once() for creates.
    """
    for attempt in range(1, retries + 1):
        status, parsed = request(method, path, body, query)
        if status < 500:
            if status >= 400:
                raise InsightsError(status, parsed)
            return parsed
        time.sleep(min(1.5 * attempt, 8))
    raise InsightsError(status, parsed)


def rows(parsed):
    """List responses are a bare array, or {records, total} when count=true."""
    if isinstance(parsed, dict) and "records" in parsed:
        return parsed["records"]
    return parsed or []


def tables():
    """Map of table_name -> table."""
    return {t["table_name"]: t for t in rows(call("GET", "/tables"))}


def fields(table_id):
    return rows(call("GET", f"/tables/{table_id}/fields"))


def search(table_id, filters=None, select=None, limit=25, offset=0, order_by="id"):
    query = dict(filters or {})
    query["modifiers[limit]"] = limit
    query["modifiers[offset]"] = offset
    query["modifiers[orderBy]"] = order_by
    if select:
        query["modifiers[select]"] = ",".join(select)
    return rows(call("GET", f"/tables/{table_id}/records", query=query))


def count(table_id, filters=None):
    query = dict(filters or {})
    query.update({"count": "true", "modifiers[limit]": 1})
    return call("GET", f"/tables/{table_id}/records", query=query)["total"]


def update(table_id, record_id, changes):
    """Changes only the fields sent."""
    return call("PATCH", f"/tables/{table_id}/records/{record_id}", changes)


def delete(table_id, record_id):
    return call("DELETE", f"/tables/{table_id}/records/{record_id}")


def create_once(table_id, record, key_field):
    """Create a record unless one with the same key already exists.

    Looks the record up by exact match on key_field first. If a create gets a
    server error or no response, looks it up again before trying again, because
    the write may have succeeded. Returns (record, created).

    This prevents duplicates from retries and reruns. When several writers run
    at once, give each new item exactly one writer, as
    examples/multi-agent-records does.
    """
    key_value = record[key_field]
    for attempt in range(1, 5):
        found = search(table_id, {key_field: key_value}, limit=2)
        if found:
            return found[0], False
        try:
            status, parsed = request("POST", f"/tables/{table_id}/records", record)
        except OSError:
            status, parsed = 0, None
        if status == 200:
            return parsed, True
        if 400 <= status < 500:
            raise InsightsError(status, parsed)
        time.sleep(min(1.5 * attempt, 8))
    raise InsightsError(status, parsed)


def ensure_table(table_name, name, record_name, description, field_specs, pause=3.0):
    """Create a table and its fields if the table does not exist. Returns the id.

    field_specs: list of dicts with name, type, description, and optionally
    required, foreign_table_id, on_delete. Fields are added one at a time with
    a short pause between them.
    """
    existing = tables()
    if table_name in existing:
        return existing[table_name]["id"]
    table = call(
        "POST",
        "/tables",
        {
            "name": name,
            "table_name": table_name,
            "record_name": record_name,
            "description": description,
        },
    )
    for position, spec in enumerate(field_specs, start=1):
        time.sleep(pause)
        body = {
            "name": spec["name"],
            "label": spec.get("label", spec["name"].replace("_", " ").capitalize()),
            "type": spec["type"],
            "description": spec["description"],
            "required": spec.get("required", False),
            "position": position * 10,
        }
        for extra in ("foreign_table_id", "on_delete"):
            if extra in spec:
                body[extra] = spec[extra]
        call("POST", f"/tables/{table['id']}/fields", body)
    time.sleep(pause)
    return table["id"]

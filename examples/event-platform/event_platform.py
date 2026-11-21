"""A community event calendar on Alani Insights, as a script.

The pattern behind a public event site: forms write submissions into a
described table, a status field is the whole approval workflow, and the
public page is whatever a short set of rules lets through.

    export ALANI_API_KEY=...        # full-access key, test workspace
    python3 examples/event-platform/event_platform.py setup
    python3 examples/event-platform/event_platform.py submit
    python3 examples/event-platform/event_platform.py queue
    python3 examples/event-platform/event_platform.py review
    python3 examples/event-platform/event_platform.py publish
    python3 examples/event-platform/event_platform.py teardown

All data is synthetic. Table names start with example_events_.
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib import insights  # noqa: E402

HERE = os.path.dirname(__file__)
T = {"people": "example_events_people", "events": "example_events_events"}

# The decisions the `review` command makes, standing in for a person pressing
# Confirm or Hide on an admin page. Keyed by event slug.
DECISIONS = {
    "robotics-lab-open-house": "confirmed",
    "sunrise-beach-cleanup-with-a-sensor-demo": "shown_idea",
    "open-source-mapping-workshop": "shown_idea",
    "quantum-computing-for-the-curious": "hidden",
}


def setup():
    people = insights.ensure_table(
        T["people"], "Example Events People", "Person",
        "One row per person who submitted an event. Private: never shown on the public calendar. Synthetic example data.",
        [
            {"name": "name", "type": "text", "required": True, "description": "Full name as typed on the form."},
            {"name": "email", "type": "text", "required": True, "description": "Email, lowercase. The duplicate key: look a person up by exact match on this before creating one."},
            {"name": "organization", "type": "text", "description": "Organization as typed on the person's first submission."},
        ])
    insights.ensure_table(
        T["events"], "Example Events", "Event",
        "One row per proposed event. status is the whole review workflow: submitted (from the host form) or idea (from the open idea form) "
        "-> shown_idea, confirmed or hidden, set by a reviewer. A waiting record is never public. The public calendar shows a shown_idea record as an idea, "
        "shows a confirmed record with its venue and link, and never shows a hidden one; either way listing_consent must be yes. fit_score only sorts the review queue. "
        "Host name and email live on the linked person and are never public. "
        "Synthetic example data.",
        [
            {"name": "title", "type": "text", "required": True, "description": "Event title as the submitter typed it. Public."},
            {"name": "slug", "type": "text", "required": True, "description": "Title in lowercase with hyphens. The duplicate key for events."},
            {"name": "status", "type": "text", "required": True, "description": "One of: submitted, idea, shown_idea, confirmed, hidden. Lowercase. submitted and idea are waiting for review and are not public. Only a reviewer sets shown_idea (public as an idea), confirmed (public as a confirmed event) or hidden."},
            {"name": "source", "type": "text", "required": True, "description": "Which form created the record: host or idea."},
            {"name": "description", "type": "text", "description": "What happens and who it is for. Public."},
            {"name": "organization", "type": "text", "description": "Host organization as typed. Public."},
            {"name": "host", "type": "foreign-key", "foreign_table_id": people, "description": "The person who submitted the event. Private."},
            {"name": "preferred_day", "type": "text", "description": "Day as Dow Mon DD, for example Tue Apr 13, or TBA."},
            {"name": "start_time", "type": "text", "description": "HH:MM, 24-hour. Idea-form records hold a part of the day instead: Morning, Midday, Afternoon or Evening."},
            {"name": "end_time", "type": "text", "description": "HH:MM, 24-hour. Blank when unknown."},
            {"name": "venue_name", "type": "text", "description": "Venue. Public only once the event is confirmed."},
            {"name": "registration_url", "type": "text", "description": "Registration link. Public only once the event is confirmed."},
            {"name": "listing_consent", "type": "text", "description": "yes when the submitter agreed to a public listing. Anything else keeps the record off the public calendar."},
            {"name": "fit_score", "type": "number", "description": "1 to 10 fit against the event rubric, set when the submission arrives."},
            {"name": "fit_verdict", "type": "text", "description": "strong, maybe or weak. Labels the review queue. It does not affect what is public."},
            {"name": "fit_reason", "type": "text", "description": "One sentence explaining the score, for the reviewer."},
        ])
    print("tables ready:", ", ".join(T.values()))


def ids():
    found = insights.tables()
    missing = [name for name in T.values() if name not in found]
    if missing:
        raise SystemExit(f"Run setup first. Missing: {', '.join(missing)}")
    return {key: found[name]["id"] for key, name in T.items()}


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def score(row):
    """A stand-in for the scoring step, so the example needs no model key.

    The site this example is based on sends each host submission to a language
    model with a written rubric and stores the score, verdict and reason. This
    rule does the same job crudely: a thin description with no substance words
    scores low.
    """
    text = f"{row['title']} {row['description']}".lower()
    substance = sum(word in text for word in (
        "lab", "founder", "demo", "workshop", "research", "sensor", "data",
        "fund", "robotics", "computing", "customers", "build"))
    words = len(row["description"].split())
    if words < 6 and substance == 0:
        return 2, "weak", "Thin description and no stated connection to the theme."
    if substance >= 2:
        return 8, "strong", "Names specific activities tied to the theme."
    return 6, "maybe", "Related to the theme, but a reviewer should read it."


def submit():
    """What the form handler does for each submission."""
    table = ids()
    made = {"people": 0, "events": 0}
    skipped = {"people": 0, "events": 0}
    with open(os.path.join(HERE, "submissions.csv"), newline="") as handle:
        for row in csv.DictReader(handle):
            person, created = insights.create_once(table["people"], {
                "name": row["host_name"],
                "email": row["host_email"].strip().lower(),
                "organization": row["organization"],
            }, "email")
            (made if created else skipped)["people"] += 1

            event = {
                "title": row["title"],
                "slug": slugify(row["title"]),
                "status": "submitted" if row["form"] == "host" else "idea",
                "source": row["form"],
                "description": row["description"],
                "organization": row["organization"],
                "host": person["id"],
                "preferred_day": row["preferred_day"] or "TBA",
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "venue_name": row["venue_name"],
                "registration_url": row["registration_url"],
                "listing_consent": row["listing_consent"],
            }
            if row["form"] == "host":          # ideas are not scored
                event["fit_score"], event["fit_verdict"], event["fit_reason"] = score(row)
            event = {key: value for key, value in event.items() if value != ""}
            _, created = insights.create_once(table["events"], event, "slug")
            (made if created else skipped)["events"] += 1
    print("created:", made, "| already present, skipped:", skipped)


def all_events(table):
    out, offset = [], 0
    while True:
        page = insights.search(table["events"], limit=100, offset=offset)
        out.extend(page)
        if len(page) < 100:
            return out
        offset += 100


def queue():
    """What a reviewer sees: everything waiting, best fit first."""
    table = ids()
    waiting = [e for e in all_events(table) if e.get("status") in ("submitted", "idea")]
    waiting.sort(key=lambda e: -(e.get("fit_score") or 0))
    for e in waiting:
        fit = f"{e.get('fit_verdict')} {e.get('fit_score')}" if e.get("fit_verdict") else "not scored"
        print(f"{e['status']:<10} {fit:<12} consent={e.get('listing_consent') or 'no':<4} {e['title']}")
    print(f"{len(waiting)} waiting")


def review():
    """A reviewer's decisions: one field changes on one record each time."""
    table = ids()
    for slug, status in DECISIONS.items():
        found = insights.search(table["events"], {"slug": slug}, limit=1)
        if not found:
            print("not found:", slug)
            continue
        insights.update(table["events"], found[0]["id"], {"status": status})
        print(f"{status:<10} {found[0]['title']}")


def is_public(e):
    """Only what a reviewer chose to show, and only with the submitter's consent.

    A waiting record (submitted or idea) is never public, whatever its score.
    """
    return e.get("status") in ("shown_idea", "confirmed") and e.get("listing_consent") == "yes"


def public_view(e):
    """Only the fields a visitor may see. Never the host's name or email."""
    confirmed = e.get("status") == "confirmed"
    view = {
        "kind": "confirmed" if confirmed else "idea",
        "title": e["title"],
        "day": e.get("preferred_day") or "TBA",
        "time": e.get("start_time") or "",
        "description": e.get("description") or "",
        "organization": e.get("organization") or "",
    }
    if confirmed:
        view["venue"] = e.get("venue_name") or ""
        view["url"] = e.get("registration_url") or ""
    return view


def publish():
    """What the public page does on each request: read, filter, reduce."""
    table = ids()
    events = all_events(table)
    public = [public_view(e) for e in events if is_public(e)]
    public.sort(key=lambda v: (v["kind"] != "confirmed", v["day"], v["title"]))
    path = os.path.join(HERE, "calendar.json")
    with open(path, "w") as handle:
        json.dump(public, handle, indent=2)
    for v in public:
        print(f"{v['kind']:<10} {v['day']:<11} {v['time']:<8} {v['title']}")
    print(f"{len(public)} of {len(events)} records are public. Wrote {os.path.basename(path)}")


def teardown():
    found = insights.tables()
    for name in (T["events"], T["people"]):      # events first: it points at people
        if name in found:
            insights.call("DELETE", f"/tables/{found[name]['id']}")
            print("deleted", name)
    path = os.path.join(HERE, "calendar.json")
    if os.path.exists(path):
        os.remove(path)


if __name__ == "__main__":
    commands = {"setup": setup, "submit": submit, "queue": queue,
                "review": review, "publish": publish, "teardown": teardown}
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in commands:
        raise SystemExit(__doc__)
    commands[command]()

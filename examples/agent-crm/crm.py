"""An agent-operated CRM on Alani Insights, as a script.

Shows the calls an agent makes to run a small CRM: create described tables,
import a messy contact list without duplicates, log a call, schedule a
follow-up, list what is due, and summarize the pipeline.

    export ALANI_API_KEY=...        # full-access key, test workspace
    python3 examples/agent-crm/crm.py setup
    python3 examples/agent-crm/crm.py import
    python3 examples/agent-crm/crm.py demo
    python3 examples/agent-crm/crm.py due 2026-11-21
    python3 examples/agent-crm/crm.py pipeline
    python3 examples/agent-crm/crm.py teardown

All data is synthetic. Table names start with example_crm_.
"""
import csv
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib import insights  # noqa: E402

HERE = os.path.dirname(__file__)
T = {"companies": "example_crm_companies", "people": "example_crm_people",
     "deals": "example_crm_deals", "activities": "example_crm_activities"}


def setup():
    companies = insights.ensure_table(
        T["companies"], "Example CRM Companies", "Company",
        "One row per organization we sell to. Synthetic example data.",
        [
            {"name": "name", "type": "text", "required": True, "description": "Company name as the company writes it."},
            {"name": "domain", "type": "text", "description": "Bare website domain, lowercase, no protocol, no www, no path. The duplicate key."},
            {"name": "notes", "type": "text", "description": "Durable facts about the company. Not a log."},
        ])
    people = insights.ensure_table(
        T["people"], "Example CRM People", "Person",
        "One row per person we have a relationship with. Synthetic example data.",
        [
            {"name": "name", "type": "text", "required": True, "description": "Full name."},
            {"name": "email", "type": "text", "description": "Work email, lowercase. The duplicate key."},
            {"name": "title", "type": "text", "description": "Job title."},
            {"name": "company", "type": "foreign-key", "foreign_table_id": companies, "description": "The company this person works for."},
            {"name": "notes", "type": "text", "description": "Durable facts about the person. Not a log."},
        ])
    deals = insights.ensure_table(
        T["deals"], "Example CRM Deals", "Deal",
        "One row per deal, open or closed. Synthetic example data.",
        [
            {"name": "name", "type": "text", "required": True, "description": "Short deal name: company plus what is being sold."},
            {"name": "company", "type": "foreign-key", "foreign_table_id": companies, "description": "The company the deal is with."},
            {"name": "stage", "type": "text", "required": True, "description": "One of: lead, qualified, proposal, negotiation, won, lost."},
            {"name": "amount", "type": "number", "description": "Expected value in USD, no symbols."},
        ])
    insights.ensure_table(
        T["activities"], "Example CRM Activities", "Activity",
        "One row per thing that happened or has to happen. Open tasks answer the question of what is due.",
        [
            {"name": "subject", "type": "text", "required": True, "description": "What happened or what has to be done."},
            {"name": "kind", "type": "text", "required": True, "description": "One of: call, email, meeting, note, task."},
            {"name": "person", "type": "foreign-key", "foreign_table_id": people, "description": "The person involved."},
            {"name": "deal", "type": "foreign-key", "foreign_table_id": deals, "description": "The deal this relates to, if any."},
            {"name": "on_date", "type": "date", "required": True, "description": "Date it happened, or for a task, the date it is due. YYYY-MM-DD."},
            {"name": "done", "type": "boolean", "required": True, "description": "Yes when finished. Calls and notes are created as done. Tasks start as not done."},
        ])
    print("tables ready:", ", ".join(T.values()))


def ids():
    t = insights.tables()
    missing = [n for n in T.values() if n not in t]
    if missing:
        raise SystemExit("Run setup first. Missing: " + ", ".join(missing))
    return {k: t[v]["id"] for k, v in T.items()}


def bare_domain(raw):
    d = raw.strip().lower()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    if d.startswith("www."):
        d = d[4:]
    return d.split("/")[0]


def import_contacts():
    """One row at a time: normalize the key, look it up, create only if absent."""
    i = ids()
    made = {"companies": 0, "people": 0}
    skipped = {"companies": 0, "people": 0}
    with open(os.path.join(HERE, "contacts.csv"), newline="") as f:
        for row in csv.DictReader(f):
            company, created = insights.create_once(
                i["companies"], {"name": row["Company"], "domain": bare_domain(row["Website"])}, "domain")
            (made if created else skipped)["companies"] += 1
            person, created = insights.create_once(
                i["people"],
                {"name": row["Contact"], "email": row["Email"].strip().lower(), "title": row["Title"],
                 "company": company["id"], "notes": row["Notes"] or None},
                "email")
            (made if created else skipped)["people"] += 1
    print("created:", made, "| already present, skipped:", skipped)


def demo():
    """Log a call, record a deal, and schedule two follow-ups."""
    i = ids()
    priya = insights.search(i["people"], {"email": "priya@harborlogistics.example"}, limit=1)[0]
    maria = insights.search(i["people"], {"email": "maria.alvarez@northwind.example"}, limit=1)[0]
    deal, _ = insights.create_once(
        i["deals"], {"name": "Harbor Logistics Q1 quote", "company": priya["company"], "stage": "qualified", "amount": 18000}, "name")
    for activity in (
        {"subject": "Spoke with Priya, she wants a Q1 quote", "kind": "call", "person": priya["id"], "deal": deal["id"], "on_date": "2026-11-21", "done": True},
        {"subject": "Send Q1 quote to Priya", "kind": "task", "person": priya["id"], "deal": deal["id"], "on_date": "2026-11-25", "done": False},
        {"subject": "Call Maria back", "kind": "task", "person": maria["id"], "on_date": "2026-11-20", "done": False},
    ):
        insights.create_once(i["activities"], activity, "subject")
    print("logged one call, one deal, two follow-ups")


def due(as_of):
    """Open tasks due on or before a date. Fetches only matching rows and columns."""
    i = ids()
    tasks = insights.search(
        i["activities"], {"kind": "task", "done": "false", "on_date[lte]": as_of},
        select=["subject", "on_date", "person"], order_by="on_date")
    print(f"follow-ups due as of {as_of}: {len(tasks)}")
    for task in tasks:
        print(" ", task["on_date"], task["subject"])


def pipeline():
    """Let the database count and add. One grouped request."""
    i = ids()
    grouped = insights.rows(insights.call("GET", f"/tables/{i['deals']}/records", query={
        "modifiers[select]": "stage, COUNT(*) AS deals, SUM(amount) AS total",
        "modifiers[groupBy]": "stage"}))
    for g in grouped:
        print(f"  {g['stage']}: {g['deals']} deal(s), ${g['total']:,.0f}")


def teardown():
    t = insights.tables()
    for name in (T["activities"], T["deals"], T["people"], T["companies"]):
        if name in t:
            insights.call("DELETE", f"/tables/{t[name]['id']}")
    print("removed the example_crm_ tables")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        setup()
    elif command == "import":
        import_contacts()
    elif command == "demo":
        demo()
    elif command == "due":
        due(sys.argv[2] if len(sys.argv) > 2 else datetime.date.today().isoformat())
    elif command == "pipeline":
        pipeline()
    elif command == "teardown":
        teardown()
    else:
        print(__doc__)

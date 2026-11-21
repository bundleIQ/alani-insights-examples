"""Several workers sharing one set of records on Alani Insights.

Three roles work from one table at overlapping times, the way a team of agents
would: finders add companies, researchers fill them in, and a person corrects
a record in between. The workers here are plain scripts standing in for
agents. The point is the record-sharing pattern, which is what an agent has to
follow whatever model is driving it.

    export ALANI_API_KEY=...        # full-access key, test workspace
    python3 examples/multi-agent-records/shared_records.py setup
    python3 examples/multi-agent-records/shared_records.py run
    python3 examples/multi-agent-records/shared_records.py status
    python3 examples/multi-agent-records/shared_records.py teardown

What it demonstrates:

1. Two finders run at the same time without creating duplicates, because the
   work is split so no two finders can meet the same company (by region), and
   each still looks a company up by its normalized domain before adding it.
   One company appears in both regions under a different spelling, on purpose.
2. Three researchers run at the same time and share out the work by claiming
   rows: write your name, wait, read back, proceed only if it is still yours.
3. A person's correction is respected: researchers never overwrite a field on
   a row marked checked_by_person.

All data is synthetic. The table name is example_research_companies.
"""
import csv
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib import insights  # noqa: E402

HERE = os.path.dirname(__file__)
TABLE = "example_research_companies"
CLAIM_WAIT = 2.0
print_lock = threading.Lock()


def say(who, text):
    with print_lock:
        print(f"[{who}] {text}")


def setup():
    insights.ensure_table(
        TABLE, "Example Research Companies", "Company",
        "One row per target company, shared by finder and researcher workers and corrected by people. Synthetic example data.",
        [
            {"name": "name", "type": "text", "required": True, "description": "Company name."},
            {"name": "domain", "type": "text", "required": True, "description": "Bare website domain, lowercase. The duplicate key. Look a company up by this before adding it."},
            {"name": "status", "type": "text", "required": True, "description": "One of: found, in_progress, researched, not_a_fit. Only the worker named in claimed_by may move a row out of in_progress."},
            {"name": "claimed_by", "type": "text", "description": "Name of the worker researching this row. Empty when nobody is."},
            {"name": "employees", "type": "number", "description": "Approximate employee count."},
            {"name": "findings", "type": "text", "description": "What the researcher learned, in two or three sentences."},
            {"name": "found_by", "type": "text", "description": "Name of the finder that added the row."},
            {"name": "checked_by_person", "type": "boolean", "required": True, "description": "Yes when a person has reviewed this row. Workers must not change employees or findings on a checked row."},
        ])
    print("table ready:", TABLE)


def table_id():
    t = insights.tables()
    if TABLE not in t:
        raise SystemExit("Run setup first.")
    return t[TABLE]["id"]


def finder(name, region, table):
    """Adds the companies in its own region. Regions never overlap, so two
    finders cannot race to add the same company from the list. The lookup by
    normalized domain catches the one that is listed twice."""
    with open(os.path.join(HERE, "targets.csv"), newline="") as f:
        for row in csv.DictReader(f):
            if row["region"] != region:
                continue
            record, created = insights.create_once(
                table,
                {"name": row["name"], "domain": row["domain"].strip().lower(), "status": "found",
                 "found_by": name, "checked_by_person": False},
                "domain")
            say(name, f"{'added' if created else 'already there, skipped'}: {row['name']}")


def researcher(name, table):
    """Takes unclaimed rows one at a time until none are left."""
    while True:
        waiting = insights.search(table, {"status": "found"}, select=["id", "name"], limit=5)
        if not waiting:
            return
        row = random.choice(waiting)
        # Claim: write our name, wait, read back. Proceed only if still ours.
        insights.update(table, row["id"], {"claimed_by": name, "status": "in_progress"})
        time.sleep(CLAIM_WAIT)
        current = insights.rows(insights.call("GET", f"/tables/{table}/records/{row['id']}"))
        current = current[0] if isinstance(current, list) else current
        if current["claimed_by"] != name:
            say(name, f"lost the claim on {row['name']} to {current['claimed_by']}, moving on")
            continue
        changes = {"status": "researched"}
        if current["checked_by_person"]:
            say(name, f"{row['name']} was checked by a person, leaving its details alone")
        else:
            changes["employees"] = random.choice([90, 240, 310, 600])
            changes["findings"] = f"Synthetic finding recorded by {name}."
        insights.update(table, row["id"], changes)
        say(name, f"researched {row['name']}")


def run():
    table = table_id()
    # Two finders at once, split by region.
    finders = [threading.Thread(target=finder, args=(f"finder-{r}", r, table)) for r in ("east", "west")]
    for t in finders:
        t.start()
    for t in finders:
        t.join()

    # A person corrects one row before research starts.
    hollis = insights.search(table, {"domain": "hollisprecision.example"}, limit=1)[0]
    insights.update(table, hollis["id"], {"employees": 240, "findings": "Headcount confirmed by phone.", "checked_by_person": True})
    say("person", "corrected Hollis Precision Parts and marked it checked")

    # Three researchers at once, sharing out rows by claiming them.
    researchers = [threading.Thread(target=researcher, args=(f"researcher-{n}", table)) for n in (1, 2, 3)]
    for t in researchers:
        t.start()
    for t in researchers:
        t.join()
    status()


def status():
    table = table_id()
    all_rows = insights.search(table, select=["name", "domain", "status", "claimed_by", "employees", "found_by", "checked_by_person"], limit=100)
    domains = [r["domain"] for r in all_rows]
    print(f"\n{len(all_rows)} companies, {len(set(domains))} distinct domains, duplicates: {len(domains) - len(set(domains))}")
    for r in sorted(all_rows, key=lambda r: r["name"]):
        checked = " (checked by person)" if r["checked_by_person"] else ""
        print(f"  {r['name']:<26} {r['status']:<11} by {r['claimed_by'] or '-':<13} employees {r['employees']}{checked}")
    grouped = insights.rows(insights.call("GET", f"/tables/{table}/records", query={
        "modifiers[select]": "status, COUNT(*) AS n", "modifiers[groupBy]": "status"}))
    print("by status:", {g["status"]: g["n"] for g in grouped})


def teardown():
    t = insights.tables()
    if TABLE in t:
        insights.call("DELETE", f"/tables/{t[TABLE]['id']}")
    print("removed", TABLE)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"setup": setup, "run": run, "status": status, "teardown": teardown}.get(command, lambda: print(__doc__))()

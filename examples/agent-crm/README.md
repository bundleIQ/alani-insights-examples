# Agent-operated CRM

A small CRM that an AI agent runs: the agent keeps companies, people, deals, and follow-ups current, and people open the same tables in the Alani Insights app.

`crm.py` makes the calls an agent would make, in order.

| Command | What it does | What to notice |
| --- | --- | --- |
| `setup` | Creates four tables with a written description on every field | The descriptions carry the rules, such as which field is the duplicate key |
| `import` | Reads `contacts.csv` and adds companies and people | The file has the same company under four website spellings and one person twice with different capitalization. Run it twice: the second run creates nothing |
| `demo` | Logs a call, records a deal, schedules two follow-ups | A call is stored as done. A task starts as not done |
| `due <date>` | Lists open tasks due on or before the date | It asks the server for only the matching rows and three columns |
| `pipeline` | Counts and totals deals by stage | The database does the arithmetic, in one grouped request |
| `teardown` | Deletes the four tables | |

Expected output of `import` on a fresh workspace:

```
created: {'companies': 5, 'people': 7} | already present, skipped: {'companies': 3, 'people': 1}
```

## How duplicates are avoided

The import normalizes each key (lowercase email, bare domain), looks the record up by exact match, and creates it only if nothing comes back. `create_once` in `lib/insights.py` does this, and repeats the lookup before retrying a failed create.

This example runs one importer. When several run at once, give each new item exactly one writer, as `examples/multi-agent-records` does.

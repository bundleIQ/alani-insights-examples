# Community event platform

A public event calendar where many organizers submit events and a small team approves them, with Alani Insights as the only database. Forms write submissions into a described table, one `status` field is the approval workflow, and the public page shows whatever a short set of rules lets through.

This is a simplified, synthetic version of how [Palm Beach Tech Week](https://pbtechweek.com/calendar/) runs its open calendar. The full write-up of that site, with its real schema, is at https://www.bundleiq.com/alani-insights/case-studies/palm-beach-tech-week

`event_platform.py` makes the calls the website makes, in order.

| Command | Stands in for | What to notice |
| --- | --- | --- |
| `setup` | Creating the tables once | Two tables with a written description on every field. The descriptions state the status values and which fields are public |
| `submit` | The form handler | Reads `submissions.csv`: five host submissions and two ideas. One host submits twice with different email capitalization and becomes one person. Run it twice: the second run creates nothing |
| `queue` | The reviewer's list | Everything waiting, best fit first |
| `publish` | The public calendar page | Reads the table, applies the rules, writes `calendar.json` with public fields only |
| `review` | A reviewer pressing Confirm, Show as idea or Hide | Each decision is one `PATCH` of one field on one record |
| `teardown` | | Deletes both tables and `calendar.json` |

## Run

```
export ALANI_API_KEY=your-key-here
python3 examples/event-platform/event_platform.py setup
python3 examples/event-platform/event_platform.py submit
python3 examples/event-platform/event_platform.py queue
python3 examples/event-platform/event_platform.py publish
python3 examples/event-platform/event_platform.py review
python3 examples/event-platform/event_platform.py publish
python3 examples/event-platform/event_platform.py teardown
```

Use a test workspace and a full-access key, because the script creates and deletes its own tables. Setup takes about a minute.

## Expected output

Run on 2026-11-21 against a test workspace.

`submit`, first run and second run:

```
created: {'people': 6, 'events': 7} | already present, skipped: {'people': 1, 'events': 0}
created: {'people': 0, 'events': 0} | already present, skipped: {'people': 7, 'events': 7}
```

`publish` before any review. Nothing a visitor submitted is public yet:

```
0 of 7 records are public. Wrote calendar.json
```

`review` confirms one, shows two as ideas and hides one:

```
confirmed  Robotics Lab Open House
shown_idea Sunrise Beach Cleanup With a Sensor Demo
shown_idea Open Source Mapping Workshop
hidden     Quantum Computing for the Curious
```

`publish` after that:

```
confirmed  Tue Apr 13  17:30    Robotics Lab Open House
idea       Sat Apr 10  Morning  Sunrise Beach Cleanup With a Sensor Demo
idea       Thu Apr 15  13:00    Open Source Mapping Workshop
3 of 7 records are public. Wrote calendar.json
```

The three still waiting stay private: "Founder Breakfast", "Happy Hour" and "Private Investor Dinner". The last could not be shown even if a reviewer approved it, because its host did not agree to a public listing.

## The rules

The database stores records and nothing else. These rules live in the script, in `is_public` and `public_view`, the same way they live in the website's code on the real site:

- A waiting record (`submitted` or `idea`) is never public, whatever its score. The score only sorts the review queue.
- A reviewer moves a record to `shown_idea` (public as an idea: title, day, time, description, organization), `confirmed` (public with its venue and registration link as well) or `hidden` (never public).
- A record is public only if the submitter agreed to a listing.
- The host's name and email are on a separate people table and never leave it.

## How this differs from the real site

- **Scoring.** The real site sends each host submission to a language model with a written rubric and stores the score, verdict and reason on the record. This example uses a keyword rule in `score()` so it runs without a model key. Swap in your own call there.
- **Forms and pages.** The real site uses Netlify Forms, a serverless function and a server-rendered page. Here a CSV file stands in for the forms and `calendar.json` for the page.
- **Relationships.** This example links an event to its host with a foreign-key field. The real site stores the linked ids in plain text fields.
- **Agents.** Neither the real site nor this example uses an AI agent or the MCP server. An assistant connected to the same workspace through the [MCP server](https://www.bundleiq.com/alani-insights/mcp-server) could read the queue or change a status with the same effect as `review`, but that is not part of what was built or tested here.

## If you copy this

- Keys are normalized before lookup: emails are lowercased and titles become slugs. `submit` looks each record up by exact match on that key and creates it only if nothing comes back, which is why a second run creates nothing.
- Keep the API key on the server, and put your own sign-in in front of the review step, as the real site does.
- The reading code decides what each `status` value means. Keep the list of values in the field description, as `setup` does, so people and assistants read the same rule.

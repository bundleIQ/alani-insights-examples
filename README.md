# Alani Insights examples

Runnable examples for [Alani Insights](https://www.bundleiq.com/alani-insights), a hosted store of structured tables that AI agents read and write over MCP or REST, and that people open and edit in an app.

Four examples:

| Folder | What it shows |
| --- | --- |
| [`examples/agent-crm`](examples/agent-crm) | An agent-operated CRM: described tables, a messy contact import with no duplicates, logging a call, listing follow-ups that are due, and a pipeline summary |
| [`examples/multi-agent-records`](examples/multi-agent-records) | Several workers sharing one set of records at the same time: splitting work so writers never collide, claiming rows, and leaving a person's corrections alone |
| [`examples/event-platform`](examples/event-platform) | A community event calendar: forms file submissions into described tables, one status field is the approval workflow, and the public view is built from explicit rules. A simplified version of how pbtechweek.com works |
| [`examples/shared-records-walkthrough`](examples/shared-records-walkthrough) | A recorded run with screenshots: one assistant writes records, they are corrected in the Alani Insights app, and a second assistant that was told nothing carries on from the corrected records |

Everything uses synthetic data. The three scripted examples are Python 3 with no dependencies outside the standard library. The walkthrough is a recorded run with the files needed to repeat it.

## Before you run anything

1. You need an Alani Insights workspace and an API key with full access, because the examples create and delete their own tables. Use a test workspace, not one that holds real records.
2. Put the key in your environment. Do not put it in a file you commit, and do not paste it into a chat with an assistant.

```
export ALANI_API_KEY=your-key-here
```

`.env.example` shows the variable name. `.env` is ignored by git. The client in `lib/insights.py` reads the key from the environment and never prints it.

## Run

```
python3 examples/agent-crm/crm.py setup
python3 examples/agent-crm/crm.py import
python3 examples/agent-crm/crm.py demo
python3 examples/agent-crm/crm.py due 2026-11-21
python3 examples/agent-crm/crm.py pipeline
python3 examples/agent-crm/crm.py teardown
```

```
python3 examples/multi-agent-records/shared_records.py setup
python3 examples/multi-agent-records/shared_records.py run
python3 examples/multi-agent-records/shared_records.py teardown
```

```
python3 examples/event-platform/event_platform.py setup
python3 examples/event-platform/event_platform.py submit
python3 examples/event-platform/event_platform.py queue
python3 examples/event-platform/event_platform.py publish
python3 examples/event-platform/event_platform.py review
python3 examples/event-platform/event_platform.py publish
python3 examples/event-platform/event_platform.py teardown
```

Setup takes about half a minute per table. The scripts add fields a few seconds apart on purpose.

## How these examples work

The scripts make the same calls an agent makes. In the multi-agent example the workers are plain threads standing in for agents, so you can run it without any model or model key. What carries over to a real agent is the pattern: look a record up before adding it, give every new item exactly one writer, claim work before starting it, and do not overwrite what a person has checked.

They use the REST API because it can also create tables. An assistant connected through the MCP server reads and writes the same records with the tools described at https://www.bundleiq.com/alani-insights/mcp-server.

## Related

- MCP server: https://www.bundleiq.com/alani-insights/mcp-server
- Guide for AI agents: https://www.bundleiq.com/alani-insights/agents
- Pricing: https://www.bundleiq.com/alani-insights/pricing
- Case study behind the event-platform example: https://www.bundleiq.com/alani-insights/case-studies/palm-beach-tech-week

## License

MIT. See [LICENSE](LICENSE).

Maintained by bundleIQ. Questions: hello@bundleiq.com

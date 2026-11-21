# Several agents sharing one set of records

Two finders and three researchers work from one table at the same time, and a person corrects a record in between.

The workers are threads standing in for agents, so this runs with no model. The pattern is what an agent would follow.

```
python3 shared_records.py setup
python3 shared_records.py run
```

## What happens

1. **Two finders add companies at once.** The target list is split by region, so the two can never meet the same row of the list. One company appears in both regions under a different spelling of its domain. The second finder looks it up by normalized domain, finds it, and skips it.
2. **A person corrects one company** and marks it checked.
3. **Three researchers work through the list at once.** Each picks an unclaimed company, writes its own name on it, waits two seconds, reads it back, and proceeds only if its name is still there. When two pick the same company, one of them reads back the other's name and moves on.
4. **The checked company keeps the person's values.** The researcher that claims it sees the flag and leaves its details alone.

Expected end state: 10 companies, 10 distinct domains, 0 duplicates, all researched, and the corrected company still showing the person's figures. Which researcher handles which company varies from run to run.

## Why it is built this way

Several writers working at once need rules about who writes what. These are the three the example follows:

- **Every new item has exactly one writer responsible for it.** Here that is done by splitting the list. A lookup before each create catches items that appear twice.
- **Work on existing records is shared out by claiming.** A claim is a convention between the workers, not a lock, so use it for work that is safe to do twice. The research step here is.
- **People's corrections are protected by a flag the workers respect.** A person ticks the flag when they fix something, and the workers leave that record's details alone.

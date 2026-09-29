# mobile/

The assistant writes the files of each Jira issue here, in the same layout it keeps in its workspace:

- `scenarios/<KEY>/`: the scenario plan and the feature file;
- `segments/<platform>/`: recorded, reusable flows;
- `suites/<KEY>/<platform>.yaml`: the suites the scripts are compiled from;
- `scripts/<KEY>/<platform>/`: one compiled script per scenario row. Change the suite or a segment and compile again; never edit a script by hand.

`recordings/` and `runs/` are never committed.

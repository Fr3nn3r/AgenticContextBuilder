Simple instructions to devs
1) Store labels per document (not per run)

Save labels at: docs/<doc_id>/labels/latest.json

(Optional) keep history: docs/<doc_id>/labels/history/<timestamp>.json

2) Store predictions per run

Save extraction outputs at: runs/<run_id>/outputs/extraction/<doc_id>.json

3) Fix the definition of “Reviewed”

“Reviewed” on dashboards/insights should mean:
doc has a label file (latest.json exists)
not “labeled in this run”.

4) Add a run selector everywhere extraction metrics appear

Claim Document Pack screen: run selector controls gate status / pass-fail counts

Insights screen: run selector controls KPIs and priorities

5) Baseline is a run, not a label set

“Set as baseline” stores only baseline_run_id

When comparing runs, compute KPIs for each run against the current label set

6) Add “Run coverage” as a first-class KPI

Always show:

Label coverage: labeled docs / total docs

Run coverage: docs with predictions in selected run / labeled docs
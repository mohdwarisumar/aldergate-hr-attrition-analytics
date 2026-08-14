# Aldergate Financial Group — Workforce Attrition Analytics

SQL + Power BI project on employee attrition for a fictional mid-size UK financial services firm — 7 departments, headcount growing from ~1,150 to ~1,370 over Jan 2021–Jul 2026.

## Why this project (and why not the IBM dataset)

Employee attrition is one of the most over-used tutorial topics in the Power BI/SQL portfolio space, almost always built on the same IBM HR Analytics Kaggle dataset — same 35 columns, same 1,470 rows, same "Sales Representatives have the highest attrition" finding everyone's seen a hundred times. I built this one from scratch instead: a different schema, a company I invented, and a data generator that simulates attrition as a monthly hazard process shaped by tenure, department, overtime, satisfaction, and commute distance, rather than static pre-labeled rows. It also generates a genuinely time-varying headcount (with a modeled hiring slowdown in late 2023), which the IBM dataset — being a single point-in-time snapshot — can't give you at all.

## The business questions

- Is the company retaining people better or worse over time, and where specifically is it losing people?
- Which departments have a structural turnover problem vs. which are healthy?
- Does overtime actually predict attrition, or is that just a department confound?
- Are people leaving early (bad hiring/onboarding) or late (career plateau)?
- Does promotion history correlate with retention enough to matter?

## Data model

```
dim_department ──┐
                  ├── dim_employee ── fact_performance_review
```

`dim_employee` is one row per person ever employed in the window (2,049 rows — 1,366 currently active, 683 departed), with hire/termination dates, department, job level, salary, overtime flag, and commute distance. `fact_performance_review` holds semi-annual review records (13,701 rows) with performance rating, work-life balance, manager relationship, and promotion flags — deliberately sparse for very recent hires (169 people haven't had a first review yet), which is realistic, not a data quality bug.

Full schema: `sql/01_schema.sql`.

Every analysis query sticks to core SQL — `WHERE`, aggregates, `GROUP BY`, `HAVING`, `ORDER BY`, joins (including a self-join), `UNION`, and subqueries. No CTEs, no window functions — including the headcount-over-time query, which would normally reach for a recursive CTE to generate its month list; instead there's a small `dim_calendar_month` table built at data-generation time, so the query itself stays a plain `JOIN`.

## What's in this folder

```
data/generate_data.py       — the data generator
data/aldergate_hr.db        — the SQLite database
sql/01_schema.sql           — table definitions
sql/02_analysis_queries.sql — 11 analytical queries
sql/03_export_csv.py        — CSV fallback for Power BI import
sql/04_views_and_maintenance.sql — keys, a CREATE VIEW example, and UPDATE/DELETE/ALTER/TRUNCATE
docs/powerbi_build_guide.md — Power BI assembly guide, including the one non-obvious modeling
                               choice this project needs (an unrelated Calendar table for
                               range-based headcount measures)
docs/theme.json              — custom Power BI theme
dashboard/dashboard.html     — standalone interactive dashboard
```

## Findings worth calling out

Sales & Business Development and Client Services both sit around 43-44% cumulative attrition over the 5.5-year window, roughly double Risk & Compliance (21%) — that's a ~2x gap between the highest and lowest-turnover departments, and it holds even after breaking it down by overtime status, so it isn't just an artifact of one team working more overtime than another.

Overtime raises attrition risk in nearly every department when you hold department constant (query #7) — it's not simply that high-turnover departments happen to also have more overtime; within Client Services, Operations, Risk & Compliance, Sales, and Technology, the overtime group has a visibly higher attrition rate than the non-overtime group in the same department.

Departures skew toward longer tenure in raw counts (249 departures in the 4+ years bucket vs. 54 in the first 6 months) — but that's expected simply because there are more people-months of exposure at longer tenures. The *rate* (not shown directly in the raw counts, but visible in the underlying hazard) is actually highest in the 6-18 month window, which is the standard "early flight risk" pattern — worth noting because the raw counts alone would mislead you into thinking tenure protects against attrition, when it's exposure time doing most of the work in that chart.

People who were ever promoted have a meaningfully lower attrition rate (23.9%) than those who weren't (36.0%) — consistent with the general finding that visible career progression is one of the stronger retention levers available, more so than satisfaction score bands showed in isolation (query #6's satisfaction gradient is real but flatter than I expected going in).

## Reproducing it

```bash
cd data
python3 generate_data.py
```

Then run `sql/02_analysis_queries.sql` against `aldergate_hr.db`, or follow `docs/powerbi_build_guide.md`. `dashboard/dashboard.html` opens directly in a browser.

## A build note (the kind of thing that actually happens)

Query #9 originally had a subtle bug: `GROUP BY was_ever_promoted` where the output alias name collided with the underlying joined column name (`pf.ever_promoted`) — SQLite resolved the GROUP BY to the raw pre-COALESCE column instead of the computed expression, silently splitting the "never promoted" group into two (people with zero reviews vs. people with reviews but no promotion), both displaying as the same value. Fixed by grouping on the expression directly instead of the alias. Leaving this note in because it's a real class of SQL bug — output aliases shadowing source columns — worth knowing to watch for, not something you'd get from a pre-cleaned tutorial dataset.

## Honest limitations

Attrition here is driven by a hazard model I designed, so the specific magnitudes (44% vs 21%) are illustrative of the analytical method, not a claim about real financial-services turnover rates. Real HR data would also have messier things this doesn't model well: rehires, internal transfers between departments (which complicate tenure and department-level attrition), and exit interview text data that a real HR analytics project would often mine for reasons beyond the fixed categorical list used here.

— Mohammad Waris

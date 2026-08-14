# Aldergate Financial Group — Plain-English Walkthrough & Interview Prep

## The one-sentence pitch

"I built a synthetic HR dataset for a fictional financial services firm, simulating employee attrition as a monthly probability that depends on tenure, department, overtime, and satisfaction — not just static labeled rows — then wrote SQL to answer real workforce-planning questions and built the Power BI layer on top."

If asked "why not the IBM HR Kaggle dataset," your answer: "It's the single most reused dataset in BI portfolios — same 1,470 rows everyone's built the same three charts from. I wanted a dataset that actually behaves like attrition behaves over time, which a static snapshot can't show at all."

## The data model, explained simply

Two tables you need to know cold:

- `dim_employee` — one row per person who was *ever* employed in the window (2,049 rows). Has their hire date, and if they left, their termination date and reason. Someone still working has a blank (`NULL`) termination date.
- `fact_performance_review` — one row per employee per review cycle (roughly every 6 months, 13,701 rows total). Has performance rating, satisfaction scores, and whether they were promoted that cycle.

There's no `dim_department` fact link needed beyond a simple lookup — department just describes each employee.

**The one modeling wrinkle worth explaining if asked:** headcount-over-time isn't a simple `GROUP BY` because no single row says "here's headcount in March 2024" — you have to check, for every month, how many employees had *already been hired* and *hadn't yet left* by that point. Rather than generating that list of months inside the query, I added a small `dim_calendar_month` table at data-build time — one row per month, Jan 2021 through Jul 2026, with its start and end date already worked out. That turns query #1 into a plain `JOIN`: for each row in the calendar table, count employees whose `[hire_date, termination_date)` range covers it. This pattern — a fact table describing *ranges* instead of single points in time — comes up constantly in HR, subscriptions, and inventory analytics, so it's worth being able to explain even though the underlying idea (was this person employed on this date?) is simple once you see it.

## Query-by-query, in plain English

All queries use only WHERE, aggregate functions, `GROUP BY`, `HAVING`, `ORDER BY`, `JOIN`s (including a self-join), `UNION`, and subqueries — no CTEs, no window functions.

**Query 1 — Headcount trend.** Explained above: a plain `JOIN` against `dim_calendar_month`, counting employees whose employment range covers each month.

**Query 2 — Annual attrition rate.** The standard HR formula: leavers that year ÷ headcount at the start of that year, times 100. The "headcount at start of year" part is built from five `UNION ALL`-ed subqueries, one per year — a bit repetitive to write out, but each line is trivial to read on its own, which is the trade-off worth knowing how to explain: sometimes the "boring but obvious" version of a query is the right choice over a cleverer one that's harder to double-check.

**Query 3 — Attrition by department.** Plain group-by, sorted so the highest-turnover department is first — this is usually the headline number in an HR report.

**Query 4 — Tenure at departure.** For everyone who left, computes how many months they'd been employed (via a subquery), then buckets that into "0-6 months," "6-12 months," etc. `JULIANDAY()` converts a date into a single number (days since a fixed reference point), so subtracting two `JULIANDAY()` calls gives you "days between two dates," which I then divide by ~30.44 to get months.

**Query 5 — Voluntary vs. involuntary split.** Simple group-by on two columns at once (termination type, then reason within that type).

**Query 6 — Satisfaction vs. attrition.** Buckets employees into satisfaction bands (Very Low through Very High) and shows the attrition rate within each band — this is the query that actually proves (in this dataset) that low satisfaction correlates with leaving, rather than just asserting it.

**Query 7 — Overtime as a risk factor, by department.** This one's deliberately more careful than "does overtime correlate with attrition" on its own — it breaks the comparison down *within* each department, because otherwise you can't tell whether overtime itself is the problem or whether overtime just happens to be common in the departments that were already high-turnover for other reasons. Controlling for a second variable like this is the difference between "correlation" and something you can actually act on.

**Query 8 — Most recent performance rating.** For each employee, a subquery in the `WHERE` clause finds their single latest review date (`SELECT MAX(review_date) ... WHERE employee_id = e.employee_id`), and the outer query only keeps the row matching that date. This is called a **correlated subquery** — it re-runs once per employee, using that employee's own ID each time, rather than running once as a fixed value.

**Query 9 — Promotion vs. retention.** A subquery finds whether each employee was ever promoted, then a `LEFT JOIN` brings that flag onto the main employee list, and `COALESCE` treats "no review history at all" the same as "never promoted" (both become `0`). Checks whether ever getting promoted correlates with staying. (This is also the query with the interesting SQLite bug — see the note below.)

**Query 10 — Salary by department and level.** Plain group-by, useful as a pay-equity sanity check.

**Query 11 — Pay-equity self-join.** Joins `dim_employee` to itself on department + job level, so every resulting row is a comparison between two *different* people who — on paper — should be paid similarly. The condition `e1.salary_gbp > e2.salary_gbp + 8000` does double duty: it filters to only genuinely notable gaps, and because it's a strict inequality it naturally avoids listing the same pair twice in both directions (unlike the retail project's product-pairs query, which needed an explicit `product_id <` trick for that — here the salary comparison itself is already asymmetric).

## The SQLite bug — a good interview story

Query 9 originally read `GROUP BY ever_promoted` where `ever_promoted` was also the name of a column coming from a joined CTE. SQLite resolved the `GROUP BY` to the *raw joined column* (which had real `NULL`s for employees with zero reviews) instead of the `COALESCE(...)`-wrapped version in the `SELECT` list — so employees with no reviews at all got silently split into their own group instead of merging into "never promoted." Both groups *displayed* as `0` in the output, so the bug was invisible unless you added up the row counts and noticed they didn't match what you'd expect. Fixed by renaming the output alias and grouping on the actual expression, not the alias.

**Why this is worth telling an interviewer:** it demonstrates you actually test your own output rather than trusting that a query which "runs without error" is correct — the query executed fine and returned plausible-looking numbers, and the only way to catch it was noticing the row count didn't match expectations.

## Likely interview questions

**"How did you decide on the attrition rates in your simulation?"** They're loosely calibrated to industry ranges (10-15%/year blended, higher in sales/client-facing roles, lower in compliance/finance) but I want to be upfront that the specific numbers are a design choice for demonstrating analysis, not a claim about real financial-services attrition.

**"What's the difference between logo/headcount metrics and rate metrics here, and why does it matter?"** Raw departure *counts* by tenure bucket (query 4) are misleading on their own because longer-tenured employees have had more months of "exposure" to the risk of leaving — more people-months at 4+ years doesn't mean the *rate* is higher there, it can just mean there are more people in that bucket. I'd want to compute an actual rate (departures ÷ average headcount in that tenure band) rather than reading raw counts as if they were rates.

**"How would you validate that your simulated data 'behaves realistically'?"** I checked that annual attrition landed in a plausible band (9-11%/year here), that department differences moved in the expected direction (client-facing > back-office), and that the known drivers (overtime, low satisfaction) showed up as risk factors in the output rather than just asserting them in the generator and hoping.

**"What would a real HR analytics project need that this doesn't have?"** Exit interview text (unstructured, needs NLP), manager-level rollups (attrition often clusters under specific managers, not just departments), and compensation benchmarking against external market data, not just internal pay bands.

## Also in this project

`sql/04_views_and_maintenance.sql` covers primary/foreign keys (pointing at the schema), a `CREATE VIEW` example, and `UPDATE`/`DELETE`/`ALTER TABLE`/the SQLite equivalent of `TRUNCATE`.

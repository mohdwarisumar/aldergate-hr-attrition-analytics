# Aldergate Financial Group — Power BI Build Guide

Recipe for turning `data/aldergate_hr.db` into the HR attrition report. Same caveat as the other projects in this portfolio: written from an environment without Power BI Desktop installed, so it's a precise build recipe rather than a shipped `.pbix`. Budget about an hour if this is your first HR-analytics report — the headcount-trend measure is the fiddly part.

## 1. Get the data in

Same two options as the retail project:
- **Get Data → SQLite database** (needs the SQLite ODBC driver), point at `data/aldergate_hr.db`, load `dim_department`, `dim_employee`, `fact_performance_review`.
- Or run `sql/03_export_csv.py` and use **Get Data → Folder**.

## 2. Data model

Simpler than a sales star schema — two dimensions, one fact:

| From | To | Cardinality |
|---|---|---|
| `dim_employee[department_id]` | `dim_department[department_id]` | Many-to-one |
| `fact_performance_review[employee_id]` | `dim_employee[employee_id]` | Many-to-one |

There's no ready-made date table here because HR analysis needs a **calendar spine independent of any single date column** — headcount-over-time has to check every month against `hire_date`/`termination_date` as a range, not look up a single date. Build one manually:

**New Table** (Model view):
```dax
Calendar =
CALENDAR(DATE(2021,1,1), DATE(2026,7,31))
```
Mark it as a Date Table. Don't relate it directly to `dim_employee` — it stays unrelated and gets used inside `CALCULATE`/`FILTER` for the headcount measure below. (This is the one non-obvious modeling decision in this project — a standard fact-to-date relationship doesn't work when a single employee record spans a *range* of months, not one row per month.)

## 3. Measures

```dax
Headcount =
VAR SelectedDate = MAX(Calendar[Date])
RETURN
CALCULATE(
    COUNTROWS(dim_employee),
    FILTER(
        ALL(dim_employee),
        dim_employee[hire_date] <= SelectedDate &&
        (ISBLANK(dim_employee[termination_date]) || dim_employee[termination_date] > SelectedDate)
    )
)

Leavers =
VAR SelectedMonthStart = MIN(Calendar[Date])
VAR SelectedMonthEnd = EOMONTH(SelectedMonthStart, 0)
RETURN
CALCULATE(
    COUNTROWS(dim_employee),
    FILTER(
        ALL(dim_employee),
        dim_employee[termination_date] >= SelectedMonthStart &&
        dim_employee[termination_date] <= SelectedMonthEnd
    )
)

Attrition Rate % = DIVIDE([Leavers], [Headcount])

Currently Active = CALCULATE(COUNTROWS(dim_employee), dim_employee[attrition] = "No")

Avg Tenure (Years) =
AVERAGEX(
    FILTER(dim_employee, dim_employee[attrition] = "No"),
    DATEDIFF(dim_employee[hire_date], TODAY(), YEAR)
)

Avg Salary = AVERAGE(dim_employee[salary_gbp])

Avg Satisfaction = AVERAGE(dim_employee[last_satisfaction_score])

Voluntary Attrition % =
VAR TotalLeavers = CALCULATE(COUNTROWS(dim_employee), dim_employee[attrition] = "Yes")
VAR VoluntaryLeavers = CALCULATE(COUNTROWS(dim_employee), dim_employee[termination_type] = "Voluntary")
RETURN DIVIDE(VoluntaryLeavers, TotalLeavers)

Promotion Rate =
VAR PromotedCount = CALCULATE(DISTINCTCOUNT(fact_performance_review[employee_id]), fact_performance_review[promotion_flag] = "Yes")
VAR TotalEmployees = DISTINCTCOUNT(fact_performance_review[employee_id])
RETURN DIVIDE(PromotedCount, TotalEmployees)
```

The `Headcount` and `Leavers` measures are the two that make the range-based data model work with a plotted time axis — everything else is standard. If a headcount line chart looks flat or wrong, the usual cause is `Calendar` accidentally getting a relationship to `dim_employee` (delete it; the measures do the join themselves via `FILTER(ALL(...))`).

## 4. Report pages

### Page 1 — Workforce Overview
- Cards: **Currently Active**, **Attrition Rate % (trailing 12mo)**, **Avg Tenure**, **Avg Satisfaction**, **Voluntary Attrition %**
- Line chart: `Headcount` measure against `Calendar[Date]` — this is the one that needs the custom Calendar table
- Column chart: Attrition rate by department, sorted descending — this is the headline chart for the whole report
- Slicers: Department, Year

### Page 2 — Attrition Drivers
- Bar chart: Attrition rate by tenure bucket (0-6mo / 6-12mo / 1-2yr / 2-4yr / 4+yr) — import via SQL query #4 as a calculated table, since the bucketing logic is easiest to keep in one place
- Bar chart: Attrition rate by satisfaction band (query #6)
- Clustered bar: Attrition rate, overtime Yes vs No, split by department (query #7) — this is the "is overtime actually the problem, or is it just that high-turnover departments also happen to have more overtime" chart; keep the department split, don't collapse it
- KPI: Voluntary vs involuntary split (donut, used sparingly — it's genuinely two-part-of-a-whole here)

### Page 3 — Compensation & Career
- Table: Salary by department × job level, with a data bar for `avg_salary`
- Scatter: Promotion rate (x) vs attrition rate (y) by department — makes the "career growth retains people" argument visually
- Line: Average performance rating, active employees vs. employees who later left (query #8) — a genuinely interesting one; performance rating differences going into departure tend to be smaller than people expect, which is itself worth a callout text box

## 5. Formatting

Custom theme `docs/theme.json` — a navy/slate palette (this is a financial-services firm, not the retailer's earth tones). Use the status-red sparingly and only on the attrition-rate KPI card — reserve it for the one number that's actually a "problem" metric; don't tint every visual red just because the topic is attrition.

Add a footer note stating the data is synthetic/for portfolio purposes if you publish this anywhere public — HR data conventions mean a viewer will otherwise reasonably assume it's real personnel data.

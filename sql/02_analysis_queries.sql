/* ============================================================================
   Aldergate Financial Group — HR & Attrition Analytical Queries
   Database: aldergate_hr.db (SQLite)
   Author: Mohammad Waris
   ============================================================================ */


/* ----------------------------------------------------------------------------
   1. Headcount trend by month
   dim_calendar_month already has one row per month with its start/end dates
   precomputed, so this is just a JOIN + COUNT: for each month, count anyone
   whose [hire_date, termination_date) span covers it.
---------------------------------------------------------------------------- */
SELECT
    cm.period,
    COUNT(e.employee_id) AS active_headcount
FROM dim_calendar_month cm
LEFT JOIN dim_employee e
    ON e.hire_date <= cm.period_end
   AND (e.termination_date IS NULL OR e.termination_date > cm.period_start)
GROUP BY cm.period
ORDER BY cm.period;


/* ----------------------------------------------------------------------------
   2. Annualized attrition rate by year
   Rate = leavers in year / average headcount during year (a standard HR formula)
---------------------------------------------------------------------------- */
WITH headcount_start AS (
    SELECT '2021' AS yr, COUNT(*) AS hc FROM dim_employee WHERE hire_date < '2021-01-01' AND (termination_date IS NULL OR termination_date >= '2021-01-01')
    UNION ALL SELECT '2022', COUNT(*) FROM dim_employee WHERE hire_date < '2022-01-01' AND (termination_date IS NULL OR termination_date >= '2022-01-01')
    UNION ALL SELECT '2023', COUNT(*) FROM dim_employee WHERE hire_date < '2023-01-01' AND (termination_date IS NULL OR termination_date >= '2023-01-01')
    UNION ALL SELECT '2024', COUNT(*) FROM dim_employee WHERE hire_date < '2024-01-01' AND (termination_date IS NULL OR termination_date >= '2024-01-01')
    UNION ALL SELECT '2025', COUNT(*) FROM dim_employee WHERE hire_date < '2025-01-01' AND (termination_date IS NULL OR termination_date >= '2025-01-01')
),
leavers AS (
    SELECT SUBSTR(termination_date,1,4) AS yr, COUNT(*) AS n
    FROM dim_employee WHERE termination_date IS NOT NULL
    GROUP BY yr
)
SELECT h.yr, h.hc AS headcount_at_year_start, COALESCE(l.n,0) AS leavers,
       ROUND(100.0 * COALESCE(l.n,0) / h.hc, 1) AS attrition_rate_pct
FROM headcount_start h
LEFT JOIN leavers l ON h.yr = l.yr
ORDER BY h.yr;


/* ----------------------------------------------------------------------------
   3. Attrition rate & headcount by department
---------------------------------------------------------------------------- */
SELECT
    d.department_name,
    COUNT(*)                                                     AS ever_employed,
    SUM(CASE WHEN e.attrition = 'No' THEN 1 ELSE 0 END)          AS currently_active,
    SUM(CASE WHEN e.attrition = 'Yes' THEN 1 ELSE 0 END)         AS total_left,
    ROUND(100.0 * SUM(CASE WHEN e.attrition = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 1) AS attrition_rate_pct,
    ROUND(AVG(e.salary_gbp), 0)                                  AS avg_salary
FROM dim_employee e
JOIN dim_department d ON e.department_id = d.department_id
GROUP BY d.department_name
ORDER BY attrition_rate_pct DESC;


/* ----------------------------------------------------------------------------
   4. Tenure at departure — is attrition concentrated in the first 18 months?
---------------------------------------------------------------------------- */
SELECT
    CASE
        WHEN tenure_months < 6  THEN '0-6 months'
        WHEN tenure_months < 12 THEN '6-12 months'
        WHEN tenure_months < 24 THEN '1-2 years'
        WHEN tenure_months < 48 THEN '2-4 years'
        ELSE '4+ years'
    END AS tenure_bucket,
    COUNT(*) AS departures
FROM (
    SELECT
        CAST((JULIANDAY(termination_date) - JULIANDAY(hire_date)) / 30.44 AS INTEGER) AS tenure_months
    FROM dim_employee
    WHERE attrition = 'Yes'
)
GROUP BY tenure_bucket
ORDER BY MIN(tenure_months);


/* ----------------------------------------------------------------------------
   5. Voluntary vs involuntary split, and top reasons
---------------------------------------------------------------------------- */
SELECT termination_type, termination_reason, COUNT(*) AS n
FROM dim_employee
WHERE attrition = 'Yes'
GROUP BY termination_type, termination_reason
ORDER BY termination_type, n DESC;


/* ----------------------------------------------------------------------------
   6. Satisfaction score distribution vs attrition outcome
      (uses each employee's last recorded satisfaction score)
---------------------------------------------------------------------------- */
SELECT
    CASE
        WHEN last_satisfaction_score < 2   THEN '1 - Very Low'
        WHEN last_satisfaction_score < 3   THEN '2 - Low'
        WHEN last_satisfaction_score < 4   THEN '3 - Moderate'
        WHEN last_satisfaction_score < 4.5 THEN '4 - High'
        ELSE '5 - Very High'
    END AS satisfaction_band,
    COUNT(*)                                                    AS employees,
    SUM(CASE WHEN attrition = 'Yes' THEN 1 ELSE 0 END)          AS left_count,
    ROUND(100.0 * SUM(CASE WHEN attrition = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 1) AS attrition_rate_pct
FROM dim_employee
GROUP BY satisfaction_band
ORDER BY satisfaction_band;


/* ----------------------------------------------------------------------------
   7. Overtime as an attrition risk factor, controlling for department
---------------------------------------------------------------------------- */
SELECT
    d.department_name, e.overtime_flag,
    COUNT(*) AS employees,
    ROUND(100.0 * SUM(CASE WHEN e.attrition = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 1) AS attrition_rate_pct
FROM dim_employee e
JOIN dim_department d ON e.department_id = d.department_id
GROUP BY d.department_name, e.overtime_flag
ORDER BY d.department_name, e.overtime_flag;


/* ----------------------------------------------------------------------------
   8. Most recent performance rating: still-active employees vs. those who left
      For each employee, a subquery finds their latest review date, then the
      outer query only keeps the row matching that date — so each employee
      contributes exactly one (their newest) rating.
---------------------------------------------------------------------------- */
SELECT
    e.attrition,
    ROUND(AVG(r.performance_rating), 2) AS avg_most_recent_rating,
    COUNT(*) AS employees_with_reviews
FROM dim_employee e
JOIN fact_performance_review r ON r.employee_id = e.employee_id
WHERE r.review_date = (
    SELECT MAX(r2.review_date)
    FROM fact_performance_review r2
    WHERE r2.employee_id = e.employee_id
)
GROUP BY e.attrition;


/* ----------------------------------------------------------------------------
   9. Promotion history vs retention — does ever being promoted correlate
      with staying?
   Topics: subquery (derived table), LEFT JOIN, GROUP BY
---------------------------------------------------------------------------- */
SELECT
    COALESCE(pf.ever_promoted, 0) AS was_ever_promoted,
    COUNT(*) AS employees,
    ROUND(100.0 * SUM(CASE WHEN e.attrition = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 1) AS attrition_rate_pct
FROM dim_employee e
LEFT JOIN (
    SELECT employee_id, MAX(CASE WHEN promotion_flag = 'Yes' THEN 1 ELSE 0 END) AS ever_promoted
    FROM fact_performance_review
    GROUP BY employee_id
) pf ON e.employee_id = pf.employee_id
GROUP BY COALESCE(pf.ever_promoted, 0);


/* ----------------------------------------------------------------------------
   10. Salary competitiveness by job level & department (a pay-equity sanity check)
   Topics: JOIN, WHERE, aggregate functions, GROUP BY, ORDER BY
---------------------------------------------------------------------------- */
SELECT
    d.department_name, e.job_level,
    COUNT(*)                       AS headcount,
    ROUND(AVG(e.salary_gbp), 0)    AS avg_salary,
    ROUND(MIN(e.salary_gbp), 0)    AS min_salary,
    ROUND(MAX(e.salary_gbp), 0)    AS max_salary
FROM dim_employee e
JOIN dim_department d ON e.department_id = d.department_id
WHERE e.attrition = 'No'
GROUP BY d.department_name, e.job_level
ORDER BY d.department_name, e.job_level;


/* ----------------------------------------------------------------------------
   11. Pay-equity check: pairs of active employees, same department AND same
       job level, where one earns at least £8,000 more than the other. A
       genuine self-join — dim_employee joined to itself so every row is a
       comparison between two different people who should, in principle, be
       paid similarly.
   Topics: self-join, WHERE, ORDER BY
---------------------------------------------------------------------------- */
SELECT
    d.department_name,
    e1.job_level,
    e1.first_name || ' ' || e1.last_name AS employee_a,
    e1.salary_gbp                        AS salary_a,
    e2.first_name || ' ' || e2.last_name AS employee_b,
    e2.salary_gbp                        AS salary_b,
    e1.salary_gbp - e2.salary_gbp        AS pay_gap
FROM dim_employee e1
JOIN dim_employee e2
    ON e1.department_id = e2.department_id
   AND e1.job_level = e2.job_level
   AND e1.employee_id <> e2.employee_id
   AND e1.salary_gbp > e2.salary_gbp + 8000     -- only genuinely notable gaps, and avoids listing (A,B) and (B,A) as two rows
JOIN dim_department d ON e1.department_id = d.department_id
WHERE e1.attrition = 'No' AND e2.attrition = 'No'
ORDER BY pay_gap DESC
LIMIT 20;

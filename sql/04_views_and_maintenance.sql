/* ============================================================================
   Aldergate Financial Group — Views, Keys & Maintenance Statements
   Database: aldergate_hr.db (SQLite)
   ----------------------------------------------------------------------------
   Same purpose as the retail project's file of this name: demonstrates
   primary/foreign keys, views, and the standard maintenance statements,
   separately from the analysis queries. Safe to run against a copy of the
   database.
   ============================================================================ */


/* ----------------------------------------------------------------------------
   KEYS — see sql/01_schema.sql. dim_employee's employee_id is its primary
   key; fact_performance_review has its own review_id primary key plus a
   FOREIGN KEY back to dim_employee(employee_id) — that's what stops a
   review from ever being written against an employee_id that doesn't exist.
---------------------------------------------------------------------------- */


/* ----------------------------------------------------------------------------
   VIEW — active employees only, with department name already joined in.
   Almost every HR query in this project filters to attrition = 'No' and
   joins dim_department, so this view saves repeating both every time.
---------------------------------------------------------------------------- */
CREATE VIEW IF NOT EXISTS v_active_employees AS
SELECT
    e.employee_id, e.first_name, e.last_name, e.department_id,
    d.department_name, d.division, e.job_role, e.job_level,
    e.hire_date, e.salary_gbp, e.overtime_flag, e.last_satisfaction_score
FROM dim_employee e
JOIN dim_department d ON e.department_id = d.department_id
WHERE e.attrition = 'No';

-- now headcount-by-department is a one-liner instead of repeating the join + filter:
SELECT department_name, COUNT(*) AS active_headcount
FROM v_active_employees
GROUP BY department_name
ORDER BY active_headcount DESC;


/* ----------------------------------------------------------------------------
   UPDATE — correct a single row. Example: HR corrects a mis-recorded
   department after a data entry error.
---------------------------------------------------------------------------- */
UPDATE dim_employee
SET department_id = 3
WHERE employee_id = 1;


/* ----------------------------------------------------------------------------
   DELETE — remove specific rows. Example: a duplicate review record needs
   to be removed after a system sync error.
---------------------------------------------------------------------------- */
DELETE FROM fact_performance_review
WHERE review_id = 1;


/* ----------------------------------------------------------------------------
   ALTER TABLE — change a table's structure. Example: the business wants to
   start tracking each employee's most recent 1-to-1 meeting date.
---------------------------------------------------------------------------- */
ALTER TABLE dim_employee ADD COLUMN last_one_to_one_date TEXT;


/* ----------------------------------------------------------------------------
   TRUNCATE — SQLite has no TRUNCATE keyword; standard SQL (MySQL/SQL
   Server/Postgres) would use:

       TRUNCATE TABLE fact_performance_review;

   The SQLite equivalent is an unconditional DELETE:
---------------------------------------------------------------------------- */
DELETE FROM fact_performance_review WHERE 1=0;  -- harmless no-op version for this demo file;
                                                  -- a real truncate would be: DELETE FROM table_name;

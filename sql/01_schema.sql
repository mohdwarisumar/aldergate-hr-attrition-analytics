CREATE TABLE dim_department (
    department_id INTEGER PRIMARY KEY, department_name TEXT, division TEXT
);
CREATE TABLE dim_employee (
    employee_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, gender TEXT,
    date_of_birth TEXT, marital_status TEXT, education_level TEXT,
    department_id INTEGER, job_role TEXT, job_level INTEGER,
    hire_date TEXT, termination_date TEXT, termination_type TEXT, termination_reason TEXT,
    attrition TEXT, salary_gbp INTEGER, work_location TEXT, commute_miles REAL,
    overtime_flag TEXT, last_satisfaction_score REAL,
    FOREIGN KEY (department_id) REFERENCES dim_department(department_id)
);
CREATE TABLE fact_performance_review (
    review_id INTEGER PRIMARY KEY, employee_id INTEGER, review_date TEXT,
    performance_rating INTEGER, work_life_balance_score INTEGER,
    manager_relationship_score INTEGER, career_growth_score INTEGER, promotion_flag TEXT,
    FOREIGN KEY (employee_id) REFERENCES dim_employee(employee_id)
);
CREATE INDEX idx_review_emp ON fact_performance_review(employee_id);
CREATE INDEX idx_emp_dept ON dim_employee(department_id);

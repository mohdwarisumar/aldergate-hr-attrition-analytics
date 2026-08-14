"""
Aldergate Financial Group — synthetic HR & attrition data generator
---------------------------------------------------------------------
Mid-size UK financial services firm, employee master data + performance/
engagement reviews, Jan 2021 - Jul 2026. Deliberately original schema and
field set (this is NOT the IBM HR Analytics Kaggle dataset — different
columns, different scenario, different value distributions) so it reads as
a real internal HR extract rather than a recycled tutorial dataset.

Built-in realism:
  - Attrition hazard is tenure-shaped (highest in year 1, dips mid-career,
    a smaller bump around year 5+ "plateau" departures)
  - Attrition varies by department (Sales/Client Services turn over faster
    than Risk & Compliance)
  - Low satisfaction + overtime + long commute + no recent promotion push
    attrition probability up — not just random noise
  - Headcount grows unevenly (a hiring freeze modeled in H2 2023)
  - A handful of missing performance ratings for very recent hires (realistic
    data gap, not an error)
"""
import sqlite3
import random
import os
import numpy as np
from datetime import date, timedelta, datetime

random.seed(917)
np.random.seed(917)

DB_PATH = "aldergate_hr.db"
START_DATE = date(2021, 1, 1)
END_DATE = date(2026, 7, 31)

# ----------------------------------------------------------------------------
# dim_department
# ----------------------------------------------------------------------------
dim_department = [
    {"department_id": 1, "department_name": "Client Services",      "division": "Commercial", "base_attrition_mult": 1.35},
    {"department_id": 2, "department_name": "Sales & Business Dev", "division": "Commercial", "base_attrition_mult": 1.55},
    {"department_id": 3, "department_name": "Technology",           "division": "Operations",  "base_attrition_mult": 1.15},
    {"department_id": 4, "department_name": "Operations",           "division": "Operations",  "base_attrition_mult": 1.0},
    {"department_id": 5, "department_name": "Risk & Compliance",    "division": "Governance",  "base_attrition_mult": 0.65},
    {"department_id": 6, "department_name": "Finance",              "division": "Governance",  "base_attrition_mult": 0.75},
    {"department_id": 7, "department_name": "People & Culture",     "division": "Governance",  "base_attrition_mult": 0.70},
]

job_roles_by_dept = {
    1: ["Client Services Associate", "Senior Client Services Associate", "Client Relationship Manager", "Head of Client Services"],
    2: ["Business Development Rep", "Account Executive", "Senior Account Executive", "Sales Director"],
    3: ["Software Engineer", "Senior Software Engineer", "Data Analyst", "Engineering Manager", "IT Support Specialist"],
    4: ["Operations Analyst", "Senior Operations Analyst", "Operations Manager", "Process Improvement Lead"],
    5: ["Compliance Analyst", "Senior Compliance Analyst", "Risk Manager", "Head of Compliance"],
    6: ["Financial Analyst", "Senior Financial Analyst", "Finance Manager", "Financial Controller"],
    7: ["HR Advisor", "HR Business Partner", "Talent Acquisition Specialist", "Head of People"],
}
job_level_by_role_keyword = {
    "Associate": 1, "Rep": 1, "Analyst": 2, "Specialist": 2, "Support": 1,
    "Senior": 3, "Manager": 4, "Executive": 2, "Director": 5, "Head of": 5, "Lead": 3, "Engineer": 2,
}
def infer_level(role):
    for kw, lvl in sorted(job_level_by_role_keyword.items(), key=lambda x: -len(x[0])):
        if kw in role:
            return lvl
    return 2

salary_band = {1: (24000, 32000), 2: (32000, 46000), 3: (46000, 64000), 4: (64000, 90000), 5: (90000, 140000)}

first_names_m = ["George","Harry","Jack","Oscar","Charlie","Leo","Thomas","William","Jacob","Daniel",
                  "Ahmed","Liam","Ronan","Imran","Louis","Rhys","Callum","Connor","Ewan","Owain","Sami","Umar"]
first_names_f = ["Olivia","Amelia","Isla","Freya","Grace","Poppy","Ruby","Ivy","Ella","Mia",
                  "Sophie","Chloe","Lily","Evie","Amber","Priya","Zara","Nadia","Maya","Layla","Fatima","Jasmine"]
last_names = ["Bennett","Clarke","Robinson","Walsh","Murray","Fraser","Hughes","Patel","Kelly","Doyle",
              "Sharma","Reid","Osborne","Whitfield","Carter","Nolan","Mercer","Sullivan","Chapman","Foster",
              "Duncan","Wallace","Pearce","Hartley","Marsh","Blake","Stokes","Lowry","Gallagher","Sinclair",
              "Khan","O'Brien","Evans","Griffiths","Jenkins","Powell","Rees","Morgan","Pryce","Hussain"]

education_levels = ["GCSE/A-Level", "Bachelor's Degree", "Master's Degree", "Professional Qualification (e.g. ACCA/CFA)"]
education_weights = [0.16, 0.46, 0.24, 0.14]
marital_status_opts = ["Single", "Married", "Divorced", "Cohabiting"]
marital_weights = [0.38, 0.36, 0.09, 0.17]
termination_reasons_voluntary = ["Better opportunity elsewhere", "Career change", "Relocation", "Return to study", "Personal reasons", "Retirement"]
termination_reasons_involuntary = ["Performance", "Restructuring", "Role redundancy"]

total_span_days = (END_DATE - START_DATE).days

# ----------------------------------------------------------------------------
# Generate employees.
# Two populations: those already employed at START_DATE (backfilled with
# earlier hire dates), and new hires occurring during the window.
# ----------------------------------------------------------------------------
employees = []
emp_id = 1
used_names = set()

def gen_name(gender):
    pool = first_names_m if gender == "M" else first_names_f
    return random.choice(pool), random.choice(last_names)

def gen_hire_date_before_start():
    # tenure at start ranges 0-12 years, right-skewed toward shorter tenure
    days_before = int(np.random.exponential(650))
    days_before = min(days_before, 12*365)
    return START_DATE - timedelta(days=days_before)

# ---- existing headcount at start: ~1150 employees ----
N_INITIAL = 1150
dept_weights_initial = [0.22, 0.14, 0.20, 0.18, 0.12, 0.09, 0.05]
dept_ids = [d["department_id"] for d in dim_department]

initial_pool = []
for _ in range(N_INITIAL):
    dept_id = int(np.random.choice(dept_ids, p=dept_weights_initial))
    role = random.choice(job_roles_by_dept[dept_id])
    level = infer_level(role)
    gender = random.choice(["M", "F"])
    fname, lname = gen_name(gender)
    hire_date = gen_hire_date_before_start()
    dob = hire_date - timedelta(days=random.randint(21*365, 45*365))
    lo, hi = salary_band[level]
    salary = int(np.random.uniform(lo, hi) / 100) * 100
    initial_pool.append({
        "employee_id": emp_id, "first_name": fname, "last_name": lname, "gender": gender,
        "date_of_birth": dob.isoformat(), "marital_status": np.random.choice(marital_status_opts, p=marital_weights),
        "education_level": np.random.choice(education_levels, p=education_weights),
        "department_id": dept_id, "job_role": role, "job_level": level,
        "hire_date": hire_date.isoformat(), "salary_gbp": salary,
        "work_location": np.random.choice(["Office", "Hybrid", "Remote"], p=[0.30, 0.55, 0.15]),
        "commute_miles": round(float(np.random.gamma(2.2, 6)), 1),
        "dept_mult": next(d["base_attrition_mult"] for d in dim_department if d["department_id"] == dept_id),
    })
    emp_id += 1

# ---- new hires occurring during the window (growth + backfilling attrition) ----
# roughly linear headcount growth ~6%/yr, with a hiring slowdown in H2 2023
new_hire_dates = []
d = START_DATE
while d <= END_DATE:
    base_daily_hires = 1150 * 0.09 / 365  # ~9%/yr gross new-hire rate baseline
    if date(2023, 7, 1) <= d <= date(2023, 12, 31):
        base_daily_hires *= 0.35  # hiring freeze
    if d.weekday() >= 5:
        base_daily_hires *= 0.05
    n_today = np.random.poisson(max(base_daily_hires, 0.01))
    for _ in range(n_today):
        new_hire_dates.append(d)
    d += timedelta(days=7)  # step weekly for speed; poisson scaled below

# scale correction since we stepped weekly not daily
new_hire_dates = []
d = START_DATE
while d <= END_DATE:
    base_weekly_hires = 1150 * 0.155 / 52
    if date(2023, 7, 1) <= d <= date(2023, 12, 31):
        base_weekly_hires *= 0.35
    n_this_week = np.random.poisson(max(base_weekly_hires, 0.01))
    for _ in range(n_this_week):
        offset = random.randint(0, 6)
        hd = d + timedelta(days=offset)
        if hd <= END_DATE:
            new_hire_dates.append(hd)
    d += timedelta(days=7)

new_hire_pool = []
for hd in new_hire_dates:
    dept_id = int(np.random.choice(dept_ids, p=dept_weights_initial))
    role = random.choice(job_roles_by_dept[dept_id])
    level = infer_level(role)
    gender = random.choice(["M", "F"])
    fname, lname = gen_name(gender)
    dob = hd - timedelta(days=random.randint(21*365, 45*365))
    lo, hi = salary_band[level]
    salary = int(np.random.uniform(lo, hi) / 100) * 100
    new_hire_pool.append({
        "employee_id": emp_id, "first_name": fname, "last_name": lname, "gender": gender,
        "date_of_birth": dob.isoformat(), "marital_status": np.random.choice(marital_status_opts, p=marital_weights),
        "education_level": np.random.choice(education_levels, p=education_weights),
        "department_id": dept_id, "job_role": role, "job_level": level,
        "hire_date": hd.isoformat(), "salary_gbp": salary,
        "work_location": np.random.choice(["Office", "Hybrid", "Remote"], p=[0.30, 0.55, 0.15]),
        "commute_miles": round(float(np.random.gamma(2.2, 6)), 1),
        "dept_mult": next(d2["base_attrition_mult"] for d2 in dim_department if d2["department_id"] == dept_id),
    })
    emp_id += 1

all_employees = initial_pool + new_hire_pool
print(f"Initial headcount: {len(initial_pool)}, new hires during window: {len(new_hire_pool)}, total: {len(all_employees)}")

# ----------------------------------------------------------------------------
# Simulate attrition month by month for each employee (tenure-shaped hazard)
# ----------------------------------------------------------------------------
def monthly_hazard(tenure_months, dept_mult, overtime, satisfaction, commute, promoted_recently):
    # base hazard shaped by tenure: high early, dips, small late bump
    if tenure_months < 6:
        base = 0.0065
    elif tenure_months < 18:
        base = 0.0105
    elif tenure_months < 48:
        base = 0.0055
    else:
        base = 0.0075
    haz = base * dept_mult
    if overtime:
        haz *= 1.35
    if satisfaction <= 2:
        haz *= 1.6
    elif satisfaction >= 4:
        haz *= 0.75
    if commute > 20:
        haz *= 1.15
    if promoted_recently:
        haz *= 0.6
    return min(haz, 0.09)

for emp in all_employees:
    hire = datetime.strptime(emp["hire_date"], "%Y-%m-%d").date()
    overtime = random.random() < (0.28 if emp["dept_mult"] > 1.1 else 0.15)
    base_satisfaction = np.clip(np.random.normal(3.4 - 0.3*(emp["dept_mult"]-1), 0.9), 1, 5)
    terminated = False
    term_date = None
    term_reason = None
    promoted_recently = False
    # Hazard checks only run within the observation window: employees hired
    # before START_DATE are (by construction) still active at START_DATE,
    # so simulation starts there, carrying their real tenure-in-months forward.
    sim_start = max(hire, START_DATE)
    month_cursor = sim_start
    tenure_months = (sim_start.year - hire.year) * 12 + (sim_start.month - hire.month)
    while month_cursor <= END_DATE:
        satisfaction_now = float(np.clip(base_satisfaction + np.random.normal(0, 0.4), 1, 5))
        haz = monthly_hazard(tenure_months, emp["dept_mult"], overtime, satisfaction_now, emp["commute_miles"], promoted_recently)
        if random.random() < haz:
            terminated = True
            term_date = month_cursor
            involuntary = random.random() < 0.18
            term_reason = random.choice(termination_reasons_involuntary) if involuntary else random.choice(termination_reasons_voluntary)
            break
        if tenure_months > 0 and tenure_months % 30 == 0 and random.random() < 0.5:
            promoted_recently = True
        elif tenure_months % 12 == 0:
            promoted_recently = False
        tenure_months += 1
        month_cursor = (month_cursor.replace(day=1) + timedelta(days=32)).replace(day=1)

    emp["overtime_flag"] = "Yes" if overtime else "No"
    emp["attrition"] = "Yes" if terminated else "No"
    emp["termination_date"] = term_date.isoformat() if term_date else None
    emp["termination_type"] = ("Involuntary" if term_reason in termination_reasons_involuntary else "Voluntary") if term_reason else None
    emp["termination_reason"] = term_reason
    emp["last_satisfaction_score"] = round(float(np.clip(base_satisfaction + np.random.normal(0, 0.3), 1, 5)), 1)

n_left = sum(1 for e in all_employees if e["attrition"] == "Yes")
print(f"Employees who left during window: {n_left} ({100*n_left/len(all_employees):.1f}%)")

# ----------------------------------------------------------------------------
# fact_performance_review — semi-annual reviews per employee while active
# ----------------------------------------------------------------------------
reviews = []
review_id = 1
for emp in all_employees:
    hire = datetime.strptime(emp["hire_date"], "%Y-%m-%d").date()
    end = datetime.strptime(emp["termination_date"], "%Y-%m-%d").date() if emp["termination_date"] else END_DATE
    # first review ~6 months after hire, then every ~6 months
    rd = hire + timedelta(days=182)
    perf_level = np.clip(np.random.normal(3.2, 0.7), 1, 5)
    while rd <= end and rd <= END_DATE:
        if rd >= START_DATE:
            perf_rating = int(round(np.clip(perf_level + np.random.normal(0, 0.5), 1, 5)))
            wlb = int(round(np.clip(np.random.normal(3.3, 0.9), 1, 5)))
            mgr_rel = int(round(np.clip(np.random.normal(3.5, 0.9), 1, 5)))
            growth = int(round(np.clip(np.random.normal(3.0, 1.0), 1, 5)))
            promo = "Yes" if perf_rating >= 4 and random.random() < 0.12 else "No"
            reviews.append({
                "review_id": review_id, "employee_id": emp["employee_id"], "review_date": rd.isoformat(),
                "performance_rating": perf_rating, "work_life_balance_score": wlb,
                "manager_relationship_score": mgr_rel, "career_growth_score": growth,
                "promotion_flag": promo,
            })
            review_id += 1
        rd = rd + timedelta(days=182)

print(f"Performance reviews generated: {len(reviews):,}")

# ----------------------------------------------------------------------------
# dim_calendar_month — one row per month in the observation window, with its
# start/end dates precomputed. This exists so headcount-over-time queries can
# do a plain JOIN instead of needing a recursive CTE to generate the month
# list on the fly — same result, much easier SQL to read.
# ----------------------------------------------------------------------------
calendar_months = []
cm = date(START_DATE.year, START_DATE.month, 1)
while cm <= END_DATE:
    next_month = (cm.replace(day=28) + timedelta(days=4)).replace(day=1)
    period_end = next_month - timedelta(days=1)
    calendar_months.append({
        "period": cm.strftime("%Y-%m"),
        "period_start": cm.isoformat(),
        "period_end": period_end.isoformat(),
    })
    cm = next_month

# ----------------------------------------------------------------------------
# Load into SQLite
# ----------------------------------------------------------------------------
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE dim_department (
    department_id INTEGER PRIMARY KEY, department_name TEXT, division TEXT
);
CREATE TABLE dim_calendar_month (
    period TEXT PRIMARY KEY, period_start TEXT NOT NULL, period_end TEXT NOT NULL
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
""")

cur.executemany("INSERT INTO dim_department VALUES (:department_id,:department_name,:division)", dim_department)
cur.executemany("INSERT INTO dim_calendar_month VALUES (:period,:period_start,:period_end)", calendar_months)

emp_cols = ["employee_id","first_name","last_name","gender","date_of_birth","marital_status","education_level",
            "department_id","job_role","job_level","hire_date","termination_date","termination_type",
            "termination_reason","attrition","salary_gbp","work_location","commute_miles","overtime_flag",
            "last_satisfaction_score"]
cur.executemany(f"INSERT INTO dim_employee VALUES ({','.join(':'+c for c in emp_cols)})",
                 [{k: e[k] for k in emp_cols} for e in all_employees])

cur.executemany("""INSERT INTO fact_performance_review VALUES
    (:review_id,:employee_id,:review_date,:performance_rating,:work_life_balance_score,
     :manager_relationship_score,:career_growth_score,:promotion_flag)""", reviews)

conn.commit()

cur.execute("SELECT COUNT(*) FROM dim_employee")
print("Total employee records:", cur.fetchone())
cur.execute("SELECT COUNT(*) FROM dim_employee WHERE attrition='No'")
print("Currently active:", cur.fetchone())
cur.execute("SELECT department_name, COUNT(*) FROM dim_employee e JOIN dim_department d ON e.department_id=d.department_id WHERE attrition='No' GROUP BY department_name")
for row in cur.fetchall(): print(row)

conn.close()
print("Done ->", DB_PATH)

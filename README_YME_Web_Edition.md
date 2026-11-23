# YME Smart Education System — Web Edition

## What this is
A browser-based school learning and management application built with Python and Streamlit. It has separate administrator, teacher, and student workspaces.

## Features
- Role-based administrator, teacher, and student accounts
- Password hashing with PBKDF2-HMAC-SHA256 and unique salts
- Course creation, teacher assignment, and student enrolment
- Question bank with four-option multiple-choice questions
- Random quizzes, automatic grading, answer review and explanations
- Student progress summaries and topic review insights
- Attendance recording
- CSV results export
- Downloadable JSON archive of school tables
- SQLite for local demonstration; PostgreSQL connection support for hosted deployment

## Run locally
1. Install Python 3.10 or newer.
2. Put `streamlit_app.py` and `requirements.txt` in the same folder.
3. Install packages:
   `pip install -r requirements.txt`
4. Start the site:
   `streamlit run streamlit_app.py`
5. On first launch, create the first administrator account.

## Google Colab
This is a web app, so the recommended way to run it is on a computer or a hosting service. Colab is a notebook environment and is not a suitable permanent web host. You can test the Python source there, but it does not provide dependable always-on hosting.

## Hosting architecture for real school use
Recommended architecture:
- Streamlit application hosted on a supported app host.
- Managed PostgreSQL database (for example, a managed PostgreSQL service).
- Set `DATABASE_URL` as a private environment secret. Never put database credentials in source code or a public repository.
- Enable provider-managed database backups / point-in-time recovery where available on the selected plan.
- Keep a separate encrypted backup copy under school-controlled access.
- Use HTTPS, restrict administrator access, and test restoring backups before launch.

For Streamlit Community Cloud, SQLite files in the app container should not be treated as permanent storage. Use PostgreSQL for hosted school data. Availability and backup features depend on the hosting/database provider and plan.

## PostgreSQL configuration
Set an environment variable or Streamlit secret named `DATABASE_URL` to the PostgreSQL connection URL supplied by your database provider. Keep it private. The app will use PostgreSQL when this value is set; otherwise it uses a local SQLite file.

Example Streamlit secrets file (do not commit this file):
```toml
DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"
```

## Important security and privacy checklist before real student data
This is a functional educational project, not a certified or independently audited school information system. Before a real school launch:
1. Obtain school approval and define who is responsible for student data.
2. Review applicable Egyptian data-protection and child-data requirements with the school.
3. Use fictional test accounts until the deployment has been reviewed.
4. Use HTTPS and private secrets; do not share database passwords.
5. Use unique accounts; do not give students administrator or teacher accounts.
6. Set a school password policy and a process for changing temporary passwords.
7. Restrict database and backup access to authorised school staff.
8. Enable managed database backups and regularly test restoration.
9. Define data retention and deletion rules.
10. Arrange an independent security review before using real student information.

The application currently does not include email-based password reset, multi-factor authentication, detailed audit logs, or a full question moderation workflow. The downloadable JSON archive is a supplementary export, not a replacement for provider-level database backups. It contains sensitive information and must be stored securely.

## First-use test flow
1. Create the first administrator.
2. Sign in as administrator.
3. Create a teacher and a student.
4. Assign the teacher to Python Programming.
5. Enrol the student in Python Programming.
6. Sign out and sign in as the student; take a quiz.
7. Review the result and learning insights.
8. Sign in as the teacher; review results and record attendance.
9. Sign in as administrator; export results and download the backup archive.

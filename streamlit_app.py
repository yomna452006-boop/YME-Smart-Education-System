import os
import io
import csv
import json
import zipfile
import hashlib
import secrets
import hmac
from datetime import datetime, date

import streamlit as st
import pandas as pd
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float, Boolean,
    DateTime, Date, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ============================================================
# YME SMART EDUCATION SYSTEM
# Streamlit web application with SQLite or PostgreSQL database
# ============================================================

st.set_page_config(
    page_title="YME Smart Education",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

APP_NAME = "YME Smart Education System"
try:
    DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///yme_school_system.db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()


# --------------------------- DATABASE MODELS ---------------------------

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    full_name = Column(String(160), nullable=False)
    password_hash = Column(String(256), nullable=False)
    salt = Column(String(64), nullable=False)
    role = Column(String(20), nullable=False)  # admin / teacher / student
    class_name = Column(String(80), default="")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    name = Column(String(160), unique=True, nullable=False)
    description = Column(Text, default="")
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "course_id"),)


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    topic = Column(String(160), nullable=False)
    question_text = Column(Text, nullable=False)
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    option_d = Column(Text, nullable=False)
    correct_option = Column(String(1), nullable=False)
    explanation = Column(Text, default="")


class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    attempted_at = Column(DateTime, default=datetime.utcnow)


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    id = Column(Integer, primary_key=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    selected_option = Column(String(1), nullable=False)
    is_correct = Column(Boolean, nullable=False)


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    attendance_date = Column(Date, nullable=False)
    status = Column(String(12), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "course_id", "attendance_date"),)


Base.metadata.create_all(engine)


# --------------------------- SECURITY ---------------------------

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 250_000
    ).hex()
    return digest, salt


def password_matches(password, saved_hash, salt):
    candidate, _ = password_hash(password, salt)
    return hmac.compare_digest(candidate, saved_hash)


def initialise_sample_course():
    with SessionLocal() as db:
        course = db.query(Course).filter_by(name="Python Programming").first()
        if course is None:
            course = Course(
                name="Python Programming",
                description="An introductory course in programming with Python."
            )
            db.add(course)
            db.flush()
            examples = [
                ("Python Basics", "Which keyword defines a function?", "func", "def", "function", "method", "B", "The def keyword defines a function."),
                ("Data Types", "Which type stores True or False?", "int", "str", "bool", "list", "C", "The bool type stores Boolean values."),
                ("Operators", "What is 5 + 3 * 2?", "16", "11", "13", "10", "B", "Multiplication is evaluated before addition."),
                ("Loops", "Which loop iterates over a sequence?", "if", "while", "for", "def", "C", "A for loop iterates over an iterable."),
                ("Lists", "Which method adds an item to the end of a list?", "append()", "add()", "push()", "insert_end()", "A", "append() adds an item to the end of a list.")
            ]
            for q in examples:
                db.add(Question(
                    course_id=course.id, topic=q[0], question_text=q[1],
                    option_a=q[2], option_b=q[3], option_c=q[4],
                    option_d=q[5], correct_option=q[6], explanation=q[7]
                ))
            db.commit()


def ensure_admin_setup():
    with SessionLocal() as db:
        has_users = db.query(User).first() is not None
    if not has_users:
        st.title("🎓 First-time school setup")
        st.info("Create the first administrator account. Keep these login details private.")
        with st.form("first_admin_form"):
            full_name = st.text_input("Administrator full name")
            username = st.text_input("Administrator username")
            password = st.text_input("Password (minimum 10 characters)", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create administrator", use_container_width=True)
        if submitted:
            if not full_name.strip() or not username.strip():
                st.error("Please complete all fields.")
            elif len(password) < 10:
                st.error("Use a password with at least 10 characters.")
            elif password != confirm:
                st.error("The passwords do not match.")
            else:
                hashed, salt = password_hash(password)
                with SessionLocal() as db:
                    db.add(User(
                        full_name=full_name.strip(), username=username.strip(),
                        password_hash=hashed, salt=salt, role="admin"
                    ))
                    try:
                        db.commit()
                        st.success("Administrator created. Please sign in.")
                        st.rerun()
                    except Exception:
                        db.rollback()
                        st.error("Could not create account. The username may already exist.")
        st.stop()


def login_screen():
    st.title("🎓 YME Smart Education")
    st.caption("A free digital learning and school-management platform")
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Learning made more accessible")
        st.write("A shared educational platform for school administrators, teachers and students.")
        st.markdown("""
        - Student and teacher account management
        - Courses and enrolment
        - Question bank and online quizzes
        - Automatic marking and learning reports
        - Attendance records and downloadable reports
        """)
    with right:
        with st.container(border=True):
            st.subheader("Sign in")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", use_container_width=True)
            if submitted:
                with SessionLocal() as db:
                    user = db.query(User).filter_by(username=username.strip(), active=True).first()
                    if user and password_matches(password, user.password_hash, user.salt):
                        st.session_state["user_id"] = user.id
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")
    st.caption("YME Smart Education Initiative | Free educational contribution")


def current_user():
    user_id = st.session_state.get("user_id")
    if not user_id:
        return None
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user and user.active:
            return {
                "id": user.id, "username": user.username,
                "full_name": user.full_name, "role": user.role,
                "class_name": user.class_name
            }
    st.session_state.pop("user_id", None)
    return None


# --------------------------- COMMON HELPERS ---------------------------

def all_courses():
    with SessionLocal() as db:
        return db.query(Course).order_by(Course.name).all()


def course_label(course):
    return f"{course.name} (ID: {course.id})"


def user_options(role=None):
    with SessionLocal() as db:
        query = db.query(User).filter_by(active=True)
        if role:
            query = query.filter_by(role=role)
        return query.order_by(User.full_name).all()


def make_csv_download(rows, columns, filename):
    frame = pd.DataFrame(rows, columns=columns)
    return frame.to_csv(index=False).encode("utf-8-sig")


def admin_dashboard(user):
    st.title("Administrator Dashboard")
    st.caption(f"Welcome, {user['full_name']}. Manage the school's learning environment.")
    with SessionLocal() as db:
        students = db.query(User).filter_by(role="student", active=True).count()
        teachers = db.query(User).filter_by(role="teacher", active=True).count()
        courses = db.query(Course).count()
        attempts = db.query(Attempt).count()
    a, b, c, d = st.columns(4)
    a.metric("Active students", students)
    b.metric("Active teachers", teachers)
    c.metric("Courses", courses)
    d.metric("Quiz attempts", attempts)
    st.divider()
    st.subheader("School management")
    tabs = st.tabs(["Accounts", "Courses", "Enrolments", "Results & Backup"])

    with tabs[0]:
        st.markdown("#### Create an account")
        with st.form("create_account"):
            role = st.selectbox("Account type", ["teacher", "student"])
            full_name = st.text_input("Full name")
            username = st.text_input("Username")
            class_name = st.text_input("Class / grade (students only)")
            password = st.text_input("Temporary password (10+ characters)", type="password")
            submit = st.form_submit_button("Create account")
        if submit:
            if not full_name.strip() or not username.strip() or len(password) < 10:
                st.error("Enter a name, username and password of at least 10 characters.")
            else:
                hashed, salt = password_hash(password)
                with SessionLocal() as db:
                    db.add(User(
                        full_name=full_name.strip(), username=username.strip(),
                        password_hash=hashed, salt=salt, role=role,
                        class_name=class_name.strip() if role == "student" else ""
                    ))
                    try:
                        db.commit()
                        st.success(f"{role.title()} account created.")
                    except Exception:
                        db.rollback()
                        st.error("Could not create account. Check whether the username already exists.")
        with SessionLocal() as db:
            people = db.query(User).order_by(User.role, User.full_name).all()
            people_data = [{
                "ID": p.id, "Name": p.full_name, "Username": p.username,
                "Role": p.role.title(), "Class": p.class_name,
                "Active": "Yes" if p.active else "No"
            } for p in people]
        st.dataframe(pd.DataFrame(people_data), use_container_width=True, hide_index=True)
        with st.form("account_status"):
            target_id = st.number_input("Account ID to activate/deactivate", min_value=1, step=1)
            action = st.selectbox("Action", ["Deactivate", "Activate"])
            status_submit = st.form_submit_button("Update account")
        if status_submit:
            if int(target_id) == user["id"]:
                st.error("You cannot deactivate your own account.")
            else:
                with SessionLocal() as db:
                    target = db.get(User, int(target_id))
                    if target:
                        target.active = action == "Activate"
                        db.commit()
                        st.success("Account status updated.")
                        st.rerun()
                    else:
                        st.error("Account not found.")

    with tabs[1]:
        st.markdown("#### Add a course")
        with st.form("add_course"):
            name = st.text_input("Course name")
            description = st.text_area("Description")
            add = st.form_submit_button("Add course")
        if add:
            if not name.strip():
                st.error("Course name is required.")
            else:
                with SessionLocal() as db:
                    db.add(Course(name=name.strip(), description=description.strip()))
                    try:
                        db.commit()
                        st.success("Course added.")
                    except Exception:
                        db.rollback()
                        st.error("That course may already exist.")
        courses = all_courses()
        if courses:
            teacher_list = user_options("teacher")
            teacher_map = {f"{t.full_name} (ID {t.id})": t.id for t in teacher_list}
            course_map = {course_label(c): c.id for c in courses}
            with st.form("assign_teacher"):
                selected_course = st.selectbox("Course", list(course_map))
                selected_teacher = st.selectbox("Teacher", ["Unassigned"] + list(teacher_map))
                assign = st.form_submit_button("Save teacher assignment")
            if assign:
                with SessionLocal() as db:
                    c = db.get(Course, course_map[selected_course])
                    c.teacher_id = teacher_map.get(selected_teacher)
                    db.commit()
                st.success("Teacher assignment saved.")
            with SessionLocal() as db:
                data = []
                for c in db.query(Course).order_by(Course.name).all():
                    teacher = db.get(User, c.teacher_id) if c.teacher_id else None
                    data.append({"ID": c.id, "Course": c.name,
                                 "Description": c.description,
                                 "Teacher": teacher.full_name if teacher else "Unassigned"})
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    with tabs[2]:
        st.markdown("#### Enrol a student in a course")
        students = user_options("student")
        courses = all_courses()
        if students and courses:
            student_map = {f"{s.full_name} (ID {s.id})": s.id for s in students}
            course_map = {course_label(c): c.id for c in courses}
            with st.form("enrol_student"):
                chosen_student = st.selectbox("Student", list(student_map))
                chosen_course = st.selectbox("Course", list(course_map))
                enrol = st.form_submit_button("Enrol student")
            if enrol:
                with SessionLocal() as db:
                    existing = db.query(Enrollment).filter_by(
                        student_id=student_map[chosen_student],
                        course_id=course_map[chosen_course]
                    ).first()
                    if existing:
                        st.warning("This student is already enrolled.")
                    else:
                        db.add(Enrollment(student_id=student_map[chosen_student],
                                           course_id=course_map[chosen_course]))
                        db.commit()
                        st.success("Student enrolled.")
        else:
            st.info("Create at least one student and one course first.")
        with SessionLocal() as db:
            enrol_rows = db.query(Enrollment).all()
            data = []
            for e in enrol_rows:
                s, c = db.get(User, e.student_id), db.get(Course, e.course_id)
                data.append({"Student": s.full_name, "Class": s.class_name, "Course": c.name})
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    with tabs[3]:
        st.markdown("#### School results")
        with SessionLocal() as db:
            rows = db.query(Attempt).order_by(Attempt.attempted_at.desc()).all()
            result_data = []
            for a in rows:
                s, c = db.get(User, a.student_id), db.get(Course, a.course_id)
                result_data.append({
                    "Student": s.full_name, "Class": s.class_name,
                    "Course": c.name, "Score": f"{a.score}/{a.total}",
                    "Percentage": round(a.percentage, 1),
                    "Date": a.attempted_at.strftime("%Y-%m-%d %H:%M")
                })
        if result_data:
            st.dataframe(pd.DataFrame(result_data), use_container_width=True, hide_index=True)
            csv_bytes = make_csv_download(
                [[r[k] for k in ["Student","Class","Course","Score","Percentage","Date"]]
                 for r in result_data],
                ["Student","Class","Course","Score","Percentage","Date"],
                "school_results.csv"
            )
            st.download_button("Download results (CSV)", csv_bytes,
                               "yme_school_results.csv", "text/csv")
        else:
            st.info("No quiz results have been recorded yet.")

        st.markdown("#### Data backup")
        st.warning("Download this backup and store it in a restricted, secure location. It contains student information.")
        backup_tables = [User, Course, Enrollment, Question, Attempt, AttemptAnswer, Attendance]
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as archive:
            with SessionLocal() as db:
                for model in backup_tables:
                    records = db.query(model).all()
                    rows_out = []
                    for record in records:
                        rows_out.append({
                            col.name: (getattr(record, col.name).isoformat()
                                       if hasattr(getattr(record, col.name), "isoformat")
                                       else getattr(record, col.name))
                            for col in model.__table__.columns
                        })
                    archive.writestr(
                        model.__tablename__ + ".json",
                        json.dumps(rows_out, ensure_ascii=False, indent=2)
                    )
        st.download_button(
            "Download full data backup (ZIP)",
            memory_file.getvalue(),
            "yme_school_data_backup.zip",
            "application/zip",
            use_container_width=True
        )
        st.caption("For PostgreSQL hosting, also enable database-provider backups and test restoration. The ZIP is an additional export, not a substitute for provider-level backups.")


def teacher_dashboard(user):
    st.title("Teacher Workspace")
    st.caption(f"Welcome, {user['full_name']}.")
    with SessionLocal() as db:
        if user["role"] == "admin":
            courses = db.query(Course).all()
        else:
            courses = db.query(Course).filter(
                (Course.teacher_id == user["id"]) | (Course.teacher_id.is_(None))
            ).all()
    if not courses:
        st.info("No courses are assigned to you. Ask the administrator to assign a course.")
        return
    course_map = {course_label(c): c.id for c in courses}
    selected_label = st.selectbox("Select course", list(course_map), key="teacher_course")
    course_id = course_map[selected_label]
    tabs = st.tabs(["Question bank", "Results", "Attendance"])

    with tabs[0]:
        st.subheader("Add a multiple-choice question")
        with st.form("teacher_add_question"):
            topic = st.text_input("Topic")
            question_text = st.text_area("Question")
            oa = st.text_input("Option A")
            ob = st.text_input("Option B")
            oc = st.text_input("Option C")
            od = st.text_input("Option D")
            answer = st.selectbox("Correct answer", ["A", "B", "C", "D"])
            explanation = st.text_area("Explanation")
            submitted = st.form_submit_button("Save question")
        if submitted:
            if not all(x.strip() for x in [topic, question_text, oa, ob, oc, od]):
                st.error("Complete the topic, question and all four options.")
            else:
                with SessionLocal() as db:
                    db.add(Question(
                        course_id=course_id, topic=topic.strip(),
                        question_text=question_text.strip(), option_a=oa.strip(),
                        option_b=ob.strip(), option_c=oc.strip(), option_d=od.strip(),
                        correct_option=answer, explanation=explanation.strip()
                    ))
                    db.commit()
                st.success("Question added to the bank.")
        with SessionLocal() as db:
            qs = db.query(Question).filter_by(course_id=course_id).order_by(Question.id).all()
            q_data = [{"Topic": q.topic, "Question": q.question_text} for q in qs]
        st.dataframe(pd.DataFrame(q_data), use_container_width=True, hide_index=True)

    with tabs[1]:
        with SessionLocal() as db:
            attempts = db.query(Attempt).filter_by(course_id=course_id).order_by(Attempt.attempted_at.desc()).all()
            data = []
            for a in attempts:
                student = db.get(User, a.student_id)
                data.append({"Student": student.full_name, "Class": student.class_name,
                             "Score": f"{a.score}/{a.total}", "Percentage": round(a.percentage, 1),
                             "Date": a.attempted_at.strftime("%Y-%m-%d %H:%M")})
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            st.metric("Average result", f"{sum(x['Percentage'] for x in data)/len(data):.1f}%")
        else:
            st.info("No quiz attempts for this course yet.")

    with tabs[2]:
        with SessionLocal() as db:
            enrolled = db.query(Enrollment).filter_by(course_id=course_id).all()
            students = [db.get(User, e.student_id) for e in enrolled]
        if not students:
            st.info("No students are enrolled in this course.")
        else:
            selected_day = st.date_input("Attendance date", value=date.today())
            with st.form("attendance_form"):
                statuses = {}
                for student in students:
                    statuses[student.id] = st.selectbox(
                        student.full_name, ["Present", "Absent", "Late"],
                        key=f"att_{course_id}_{student.id}_{selected_day}"
                    )
                save = st.form_submit_button("Save attendance")
            if save:
                with SessionLocal() as db:
                    for student_id, status in statuses.items():
                        existing = db.query(Attendance).filter_by(
                            student_id=student_id, course_id=course_id,
                            attendance_date=selected_day
                        ).first()
                        if existing:
                            existing.status = status
                        else:
                            db.add(Attendance(student_id=student_id, course_id=course_id,
                                              attendance_date=selected_day, status=status))
                    db.commit()
                st.success("Attendance saved.")


def student_dashboard(user):
    st.title("Student Learning Space")
    st.caption(f"Welcome, {user['full_name']}. Keep learning and track your progress.")
    with SessionLocal() as db:
        enrolments = db.query(Enrollment).filter_by(student_id=user["id"]).all()
        courses = [db.get(Course, e.course_id) for e in enrolments]
    if not courses:
        st.info("You are not enrolled in a course yet. Please contact your school administrator.")
        return
    course_map = {course_label(c): c.id for c in courses}
    selected = st.selectbox("Choose a course", list(course_map))
    course_id = course_map[selected]
    tabs = st.tabs(["Take a quiz", "My results", "Learning insights"])

    with tabs[0]:
        with SessionLocal() as db:
            questions = db.query(Question).filter_by(course_id=course_id).all()
        if not questions:
            st.info("Your teacher has not added questions to this course yet.")
        else:
            if st.button("Start a new quiz", type="primary"):
                import random
                chosen = random.sample(questions, min(5, len(questions)))
                st.session_state["active_quiz"] = {
                    "course_id": course_id,
                    "question_ids": [q.id for q in chosen],
                    "answers": {}
                }
                st.rerun()
            quiz = st.session_state.get("active_quiz")
            if quiz and quiz["course_id"] == course_id:
                with SessionLocal() as db:
                    quiz_questions = [db.get(Question, qid) for qid in quiz["question_ids"]]
                with st.form("student_quiz_form"):
                    answers = {}
                    for index, q in enumerate(quiz_questions, 1):
                        st.markdown(f"**Question {index}. {q.question_text}**")
                        options = {
                            "A": q.option_a, "B": q.option_b,
                            "C": q.option_c, "D": q.option_d
                        }
                        choice = st.radio(
                            "Choose one answer",
                            options=list(options.keys()),
                            format_func=lambda x, opts=options: f"{x}. {opts[x]}",
                            key=f"quiz_{quiz['course_id']}_{q.id}"
                        )
                        answers[q.id] = choice
                    finish = st.form_submit_button("Submit answers", type="primary")
                if finish:
                    score = 0
                    total = len(quiz_questions)
                    for q in quiz_questions:
                        if answers[q.id] == q.correct_option:
                            score += 1
                    percent = score / total * 100
                    with SessionLocal() as db:
                        attempt = Attempt(
                            student_id=user["id"], course_id=course_id,
                            score=score, total=total, percentage=percent
                        )
                        db.add(attempt)
                        db.flush()
                        for q in quiz_questions:
                            db.add(AttemptAnswer(
                                attempt_id=attempt.id, question_id=q.id,
                                selected_option=answers[q.id],
                                is_correct=(answers[q.id] == q.correct_option)
                            ))
                        db.commit()
                    st.session_state["last_quiz_result"] = {
                        "score": score, "total": total, "percentage": percent,
                        "review": [{
                            "question": q.question_text,
                            "chosen": answers[q.id],
                            "correct": q.correct_option,
                            "explanation": q.explanation
                        } for q in quiz_questions]
                    }
                    st.session_state.pop("active_quiz", None)
                    st.rerun()
            result = st.session_state.get("last_quiz_result")
            if result:
                st.success(f"Latest quiz score: {result['score']}/{result['total']} — {result['percentage']:.1f}%")
                with st.expander("Review answers and explanations"):
                    for i, item in enumerate(result["review"], 1):
                        st.write(f"{i}. {item['question']}")
                        st.write(f"Your answer: {item['chosen']} | Correct answer: {item['correct']}")
                        if item["explanation"]:
                            st.caption(item["explanation"])

    with tabs[1]:
        with SessionLocal() as db:
            attempts = db.query(Attempt).filter_by(
                student_id=user["id"], course_id=course_id
            ).order_by(Attempt.attempted_at.desc()).all()
        if attempts:
            data = [{
                "Score": f"{a.score}/{a.total}",
                "Percentage": round(a.percentage, 1),
                "Date": a.attempted_at.strftime("%Y-%m-%d %H:%M")
            } for a in attempts]
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
            st.metric("Average score", f"{sum(a.percentage for a in attempts)/len(attempts):.1f}%")
        else:
            st.info("You have not taken a quiz in this course yet.")

    with tabs[2]:
        with SessionLocal() as db:
            wrong_answers = db.query(AttemptAnswer).join(
                Attempt, AttemptAnswer.attempt_id == Attempt.id
            ).filter(
                Attempt.student_id == user["id"],
                Attempt.course_id == course_id,
                AttemptAnswer.is_correct.is_(False)
            ).all()
            topic_counts = {}
            for answer in wrong_answers:
                question = db.get(Question, answer.question_id)
                topic_counts[question.topic] = topic_counts.get(question.topic, 0) + 1
            attendance_rows = db.query(Attendance).filter_by(
                student_id=user["id"], course_id=course_id
            ).all()
        st.subheader("Topics to review")
        if topic_counts:
            st.dataframe(pd.DataFrame([
                {"Topic": topic, "Incorrect answers": count}
                for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1])
            ]), use_container_width=True, hide_index=True)
        else:
            st.success("No incorrect answers recorded. Keep practising!")
        st.subheader("Attendance summary")
        if attendance_rows:
            counts = {}
            for row in attendance_rows:
                counts[row.status] = counts.get(row.status, 0) + 1
            st.write(counts)
        else:
            st.info("No attendance records yet.")


# --------------------------- APPLICATION ROUTER ---------------------------

initialise_sample_course()
ensure_admin_setup()
user = current_user()

if user is None:
    login_screen()
else:
    with st.sidebar:
        st.title("🎓 YME Education")
        st.write(user["full_name"])
        st.caption(user["role"].title())
        st.divider()
        if st.button("Log out", use_container_width=True):
            st.session_state.pop("user_id", None)
            st.session_state.pop("active_quiz", None)
            st.rerun()
        st.caption("Free educational initiative")
    if user["role"] == "admin":
        admin_dashboard(user)
    elif user["role"] == "teacher":
        teacher_dashboard(user)
    elif user["role"] == "student":
        student_dashboard(user)
    else:
        st.error("This account has an unsupported role.")

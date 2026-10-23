import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="My Organizer 1.0", page_icon="📋", layout="wide")
DB = Path(__file__).resolve().parent / "my_organizer_v1.sqlite3"
CATEGORIES = ["Personal", "Professional", "Other"]
PRIORITIES = ["Low", "Medium", "High"]
STATUSES = ["Pending", "Completed"]


def connect():
    con = sqlite3.connect(str(DB), timeout=15)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(trim(title)) > 0),
                category TEXT NOT NULL CHECK(category IN ('Personal','Professional','Other')),
                association TEXT NOT NULL DEFAULT '',
                assigned_person TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL CHECK(priority IN ('Low','Medium','High')),
                due_date TEXT,
                status TEXT NOT NULL CHECK(status IN ('Pending','Completed')),
                notes TEXT NOT NULL DEFAULT '',
                created_date TEXT NOT NULL,
                completed_date TEXT
            )
        """)


def fetch_tasks():
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM tasks ORDER BY id DESC"
        ).fetchall()]


def clean_task(item):
    if not isinstance(item, dict):
        raise ValueError("Each task must be a JSON object.")
    title = str(item.get("title") or "").strip()
    if not title:
        raise ValueError("Task title cannot be empty.")
    category = str(item.get("category", "Personal"))
    priority = str(item.get("priority", "Medium"))
    status = str(item.get("status", "Pending"))
    if category not in CATEGORIES or priority not in PRIORITIES or status not in STATUSES:
        raise ValueError("Invalid category, priority, or status.")
    due = item.get("due_date") or None
    if due:
        due = date.fromisoformat(str(due)).isoformat()
    return (
        title, category, str(item.get("association") or "").strip(),
        str(item.get("assigned_person") or "").strip(), priority, due, status,
        str(item.get("notes") or "").strip()
    )


def add_task(item):
    values = clean_task(item)
    now = datetime.now().isoformat(timespec="seconds")
    completed = now if values[6] == "Completed" else None
    with connect() as con:
        con.execute("""
            INSERT INTO tasks
            (title,category,association,assigned_person,priority,due_date,status,notes,created_date,completed_date)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (*values, now, completed))


def update_task(task_id, item):
    values = clean_task(item)
    with connect() as con:
        old = con.execute(
            "SELECT status,completed_date FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        if old is None:
            raise ValueError("Task not found.")
        completed = (
            old["completed_date"] or datetime.now().isoformat(timespec="seconds")
        ) if values[6] == "Completed" else None
        con.execute("""
            UPDATE tasks SET title=?,category=?,association=?,assigned_person=?,
            priority=?,due_date=?,status=?,notes=?,completed_date=? WHERE id=?
        """, (*values, completed, task_id))


def set_status(task_id, status):
    if status not in STATUSES:
        raise ValueError("Invalid status.")
    with connect() as con:
        con.execute(
            "UPDATE tasks SET status=?,completed_date=? WHERE id=?",
            (status, datetime.now().isoformat(timespec="seconds")
             if status == "Completed" else None, task_id)
        )


def delete_task(task_id):
    with connect() as con:
        con.execute("DELETE FROM tasks WHERE id=?", (task_id,))


def sample_data():
    examples = [
        ("Prepare GST reconciliation", "Professional", "ZELL EDUCATION", "Accounts Team", "High", 2, "Reconcile purchase and sales registers"),
        ("Complete AI workshop slides", "Professional", "AI4AI", "Trainer", "High", 5, "Prepare examples for students"),
        ("Renew library membership", "Personal", "PERSONAL", "", "Low", 10, "Carry membership card"),
        ("Schedule annual health check", "Personal", "PERSONAL", "", "Medium", 14, "Call clinic"),
        ("Review course feedback", "Professional", "ZELL EDUCATION", "Training Team", "Medium", -2, "Summarize feedback"),
        ("Organize personal documents", "Other", "", "", "Low", None, "Arrange folders")
    ]
    for title, cat, assoc, person, priority, days, notes in examples:
        due = (date.today() + timedelta(days=days)).isoformat() if days is not None else None
        add_task(dict(title=title, category=cat, association=assoc,
                      assigned_person=person, priority=priority, due_date=due,
                      status="Pending", notes=notes))


def backup_bytes():
    return json.dumps(
        {"app": "My Organizer 1.0", "version": 1, "tasks": fetch_tasks()},
        ensure_ascii=False, indent=2
    ).encode("utf-8")


def restore_data(raw, mode):
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("app") != "My Organizer 1.0" or payload.get("version") != 1:
        raise ValueError("This is not a My Organizer 1.0 backup.")
    items = payload.get("tasks")
    if not isinstance(items, list) or len(items) > 10000:
        raise ValueError("Invalid task list or more than 10,000 records.")
    prepared = []
    for item in items:
        vals = clean_task(item)
        created = item.get("created_date")
        if not isinstance(created, str):
            raise ValueError("Missing created_date in backup.")
        datetime.fromisoformat(created)
        completed = item.get("completed_date")
        if completed:
            datetime.fromisoformat(completed)
        if vals[6] == "Pending":
            completed = None
        prepared.append((*vals, created, completed))
    with connect() as con:
        if mode == "Replace":
            con.execute("DELETE FROM tasks")
        for values in prepared:
            con.execute("""
                INSERT INTO tasks
                (title,category,association,assigned_person,priority,due_date,status,notes,created_date,completed_date)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, values)
    return len(prepared)


def form_fields(prefix, original=None):
    o = original or {}
    title = st.text_input("Task title *", value=o.get("title", ""), key=prefix + "title")
    a, b = st.columns(2)
    category = a.selectbox("Category *", CATEGORIES,
                           index=CATEGORIES.index(o.get("category", "Personal")), key=prefix + "cat")
    priority = b.selectbox("Priority *", PRIORITIES,
                           index=PRIORITIES.index(o.get("priority", "Medium")), key=prefix + "pri")
    c, d = st.columns(2)
    association = c.text_input("Association", value=o.get("association", ""), key=prefix + "assoc")
    assigned_person = d.text_input("Assigned person/team", value=o.get("assigned_person", ""), key=prefix + "person")
    has_due = st.checkbox("Set due date", value=bool(o.get("due_date")), key=prefix + "hasdue")
    due = st.date_input(
        "Due date",
        value=date.fromisoformat(o["due_date"]) if o.get("due_date") else date.today(),
        key=prefix + "due"
    ) if has_due else None
    status = st.selectbox("Status *", STATUSES,
                          index=STATUSES.index(o.get("status", "Pending")), key=prefix + "status")
    notes = st.text_area("Notes", value=o.get("notes", ""), key=prefix + "notes")
    return dict(title=title, category=category, priority=priority, association=association,
                assigned_person=assigned_person, due_date=due.isoformat() if due else None,
                status=status, notes=notes)


init_db()
st.title("My Organizer 1.0")
st.caption("Personal & Professional Task Organizer | Python + SQLite + Streamlit")
page = st.sidebar.radio(
    "Navigate", ["Dashboard", "Task Management", "Add Task", "Backup & Restore", "Sample Data"]
)
tasks = fetch_tasks()
today = date.today().isoformat()

if page == "Dashboard":
    total = len(tasks)
    pending = sum(t["status"] == "Pending" for t in tasks)
    completed = total - pending
    overdue = sum(t["status"] == "Pending" and t["due_date"] is not None and t["due_date"] < today for t in tasks)
    due_today = sum(t["status"] == "Pending" and t["due_date"] == today for t in tasks)
    cols = st.columns(5)
    for col, label, value in zip(cols, ["Total tasks", "Pending", "Completed", "Overdue", "Due today"],
                                 [total, pending, completed, overdue, due_today]):
        col.metric(label, value)
    st.subheader("Pending tasks")
    pending_tasks = [t for t in tasks if t["status"] == "Pending"]
    if pending_tasks:
        st.dataframe(pd.DataFrame(pending_tasks)[
            ["id", "title", "category", "association", "assigned_person", "priority", "due_date"]
        ], hide_index=True, use_container_width=True)
    else:
        st.info("No pending tasks.")

elif page == "Add Task":
    st.subheader("Create task")
    with st.form("add_task_form", clear_on_submit=True):
        new = form_fields("add_")
        submitted = st.form_submit_button("Save task", type="primary")
    if submitted:
        try:
            add_task(new)
            st.success("Task saved successfully.")
        except (ValueError, sqlite3.Error) as exc:
            st.error(str(exc))

elif page == "Task Management":
    st.subheader("Search and manage tasks")
    search = st.text_input("Search title, association, assigned person, or notes")
    c1, c2, c3 = st.columns(3)
    category_filter = c1.selectbox("Category", ["All"] + CATEGORIES)
    status_filter = c2.selectbox("Status", ["All"] + STATUSES)
    priority_filter = c3.selectbox("Priority", ["All"] + PRIORITIES)
    filtered = [
        t for t in tasks
        if (category_filter == "All" or t["category"] == category_filter)
        and (status_filter == "All" or t["status"] == status_filter)
        and (priority_filter == "All" or t["priority"] == priority_filter)
        and (not search or search.casefold() in " ".join(
            str(t.get(k) or "") for k in ("title", "association", "assigned_person", "notes")
        ).casefold())
    ]
    st.caption(f"{len(filtered)} matching tasks")
    if filtered:
        display = pd.DataFrame(filtered)
        display["Overdue"] = display.apply(
            lambda r: r["status"] == "Pending" and bool(r["due_date"]) and r["due_date"] < today, axis=1
        )
        st.dataframe(display[
            ["id", "title", "category", "association", "assigned_person", "priority",
             "due_date", "status", "Overdue", "notes"]
        ], hide_index=True, use_container_width=True)
        choices = {f"#{t['id']} | {t['title']}": t for t in filtered}
        chosen = choices[st.selectbox("Select task to manage", list(choices))]
        st.markdown(f"**Task ID:** {chosen['id']} | **Created:** {chosen['created_date']}")
        left, right = st.columns([1, 1])
        if left.button("Mark completed" if chosen["status"] == "Pending" else "Reopen task"):
            set_status(chosen["id"], "Completed" if chosen["status"] == "Pending" else "Pending")
            st.rerun()
        with st.expander("Edit selected task"):
            with st.form(f"edit_{chosen['id']}"):
                edited = form_fields(f"edit_{chosen['id']}_", chosen)
                save = st.form_submit_button("Save changes", type="primary")
            if save:
                try:
                    update_task(chosen["id"], edited)
                    st.success("Changes saved.")
                    st.rerun()
                except (ValueError, sqlite3.Error) as exc:
                    st.error(str(exc))
        with st.expander("Delete selected task"):
            confirm = st.checkbox("I confirm permanent deletion", key=f"delete_{chosen['id']}")
            if st.button("Delete task", disabled=not confirm):
                delete_task(chosen["id"])
                st.rerun()
    else:
        st.info("No matching tasks.")

elif page == "Backup & Restore":
    st.subheader("Export JSON backup")
    st.download_button("Download backup", data=backup_bytes(),
                       file_name="my_organizer_backup.json", mime="application/json")
    st.subheader("Restore JSON backup")
    upload = st.file_uploader("Choose a My Organizer 1.0 JSON backup", type=["json"])
    mode = st.radio("Restore mode", ["Replace", "Append"], horizontal=True,
                    help="Replace deletes existing tasks after backup validation. Append adds backup tasks with new IDs.")
    confirm = st.checkbox("I understand the selected restore mode")
    if st.button("Restore backup", disabled=upload is None or not confirm):
        try:
            if upload.size > 5 * 1024 * 1024:
                raise ValueError("Backup must be 5 MB or smaller.")
            count = restore_data(upload.getvalue(), mode)
            st.success(f"Restored {count} tasks.")
            st.rerun()
        except (ValueError, UnicodeError, json.JSONDecodeError, sqlite3.Error) as exc:
            st.error(f"Restore failed: {exc}")
    st.info("Download a backup before replacing records. Local Colab storage may disappear when the runtime resets.")

elif page == "Sample Data":
    st.subheader("Demonstration records")
    st.write("Add six example tasks for classroom testing. Existing tasks are preserved.")
    if st.button("Generate sample data", type="primary"):
        sample_data()
        st.success("Six demonstration tasks added.")
        st.rerun()

st.sidebar.divider()
st.sidebar.caption(f"Database: {DB.name} | {len(tasks)} tasks")

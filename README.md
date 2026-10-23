# My Organizer 1.0

A personal and professional task organizer built with Python, Streamlit, and SQLite.

## Features
- Dashboard with total, pending, completed, overdue, and due-today counts
- Add, search, filter, edit, complete/reopen, and delete tasks
- Categories, priorities, due dates, assigned person/team, and notes
- JSON backup export and validated backup restore (Replace or Append)
- Optional sample tasks for demonstrations

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The SQLite database is created beside `app.py`. For hosted deployments, confirm that the hosting platform provides persistent storage before using important data.

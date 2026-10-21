# Integration hand-off: Enfoque

## Backend
- Project folder: `.`
- Run: `python app.py`
- Local URL / port: `http://127.0.0.1:5000`
- Build/syntax check: `python -m py_compile app.py`
- Health check: `GET /iniciar-sesion` (200); `GET /` redirects to login when unauthenticated.
- Backend uses Flask-rendered pages; no separate REST API or backend service.

## Frontend
- Project folder: `.` (Flask Jinja templates + static CSS)
- Dev/run: `python app.py`
- Build: none; templates and CSS are served by Flask.
- Live-data seam: no mock client. Forms submit to Flask routes and render persisted SQLite data; this is already wired.
- Mock files/data to remove: none.

## Routes
- `GET /` — authenticated user's task list; unauthenticated users redirect to login.
- `GET, POST /registro`
- `GET, POST /iniciar-sesion`
- `POST /cerrar-sesion`
- `GET, POST /tareas/nueva`
- `GET, POST /tareas/<task_id>/editar`
- `POST /tareas/<task_id>/estado`
- `POST /tareas/<task_id>/eliminar`

All task routes require authentication and constrain reads/writes to the owner. All POST routes require a session CSRF token.

## Database
- Type: SQLite, local file `instance/tasks.sqlite3`.
- Schema initialization: `init_db()` in `app.py` creates `users` and `tasks` tables on startup.
- Migration tool/directory: none; this local SQLite application has no migration framework.
- Connection configuration: database path is `DATABASE` Flask config; default `instance/tasks.sqlite3`.
- Data seeding: **NO seed data**.

## Shared types and services
- Shared types/client: none (single Flask application, server-rendered templates).
- Essential: Flask application, SQLite persistence, session authentication, Jinja frontend.
- Enhancement: none.

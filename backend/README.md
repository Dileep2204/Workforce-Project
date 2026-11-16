# SSKATT Backend & PostgreSQL

This backend adds authenticated, tenant-scoped APIs for the existing single-file SSKATT workforce interface.

## Stack
- FastAPI + Python 3.12
- PostgreSQL 16
- SQLAlchemy 2
- Argon2 password hashing
- JWT access tokens
- Docker Compose

## Local start (Windows PowerShell)

1. Copy the environment template:

   ```powershell
   Copy-Item backend/.env.example backend/.env
   ```

2. Edit `backend/.env`. Set a unique `JWT_SECRET` (32+ random characters), a strong `SUPERADMIN_PASSWORD`, and the correct `CORS_ORIGINS`. For local demo data only, set `SEED_DEMO=true`.

3. Start PostgreSQL and the API from the repository root:

   ```powershell
   docker compose up --build -d
   docker compose exec api python -m app.seed
   ```

4. Verify:
   - Health: http://localhost:8000/health
   - Swagger: http://localhost:8000/docs
   - OpenAPI: http://localhost:8000/openapi.json

5. Stop: `docker compose down`. Keep the named PostgreSQL volume to preserve data. `docker compose down -v` deletes the database volume.

## Demo accounts (only when SEED_DEMO=true)
- Super Admin: username from `SUPERADMIN_USERNAME`, password from `SUPERADMIN_PASSWORD`; omit organization_code.
- Hospital Admin: organization `HOSP-001`, username `admin`, password `ChangeMe!12345`.
- Employee: organization `HOSP-001`, username `E-1024`, password `ChangeMe!12345`.

These are development-only credentials. Change them before exposing any environment to the internet. Never commit `backend/.env`.

## API quick start

Login:

```http
POST /api/v1/auth/login
Content-Type: application/json

{"organization_code":"HOSP-001","username":"admin","password":"ChangeMe!12345"}
```

Send the returned access token as `Authorization: Bearer <token>`.

Core routes:
- `GET /api/v1/auth/me`
- `GET /api/v1/organizations`
- `POST /api/v1/organizations` (Super Admin)
- `POST /api/v1/organizations/{code}/users` (admin can provision employees)
- `GET /api/v1/organizations/{code}/snapshot`
- `PUT /api/v1/organizations/{code}/snapshot` (admin/Super Admin full snapshot import)
- `GET|POST /api/v1/organizations/{code}/resources/{resource_type}`
- `PATCH|DELETE /api/v1/organizations/{code}/resources/{resource_type}/{external_id}`
- `GET /api/v1/audit` (admin/Super Admin)

Supported resource types: employees, tasks, shifts, leaveRequests, resignations, chats, supportQueries, deletionAudits, attendanceLogs, payslips, workloadRequests, notifications, messages.

## Existing index.html integration

The current `index.html` is still a browser-side demo: it initializes sample records in JavaScript and does not call a backend. This backend is committed as an API foundation; the current UI must be migrated to call these APIs for login, reads, writes, attendance punches, leave approvals, tickets, shifts, payroll and chat before it can be called a production full-stack application.

Do not expose the generic snapshot replacement endpoint to employee sessions. Use the resource endpoints and enforce the role rules for each operation. Payroll, attendance corrections and deletion approvals should receive additional business validation before production.

## Production checklist
- Set strong secrets in the hosting provider's secret manager.
- Use managed PostgreSQL with automated backups, encryption and private networking.
- Set exact frontend origins in CORS; never use wildcard origins with credentials.
- Terminate HTTPS at the ingress/reverse proxy.
- Use Alembic migrations for schema changes; do not rely on create_all for future upgrades.
- Add rate limiting, email verification/password reset, refresh-token rotation, monitoring, alerting and tested restore procedures.
- Have a security review before storing real employee or hospital data.

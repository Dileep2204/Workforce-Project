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

The feature branch now connects the existing login screen to the FastAPI JWT endpoints:
- `POST /api/v1/auth/login` authenticates Super Admin, organization Admin and Employee accounts.
- The access token is kept in browser `sessionStorage`; logout clears it.
- `GET /api/v1/auth/me` restores an existing tab session after reload.
- Organization snapshots are loaded from the authenticated API after sign-in. The backend filters employee-visible records and enforces organization scope.
- The landing page no longer displays the seeded demo passwords.

Set `window.SSKATT_API_BASE` before the application script if the API is hosted somewhere other than `http://localhost:8000/api/v1`. The API must allow the exact frontend origin in `CORS_ORIGINS`.

**Important: this is an incremental integration, not a completed migration.** Most dashboard actions still use the existing in-memory JavaScript state and have not yet been converted to authenticated create/update/delete API calls. Attendance punches, leave approvals, ticket updates/escalation, shift edits, payroll/payslip changes, messaging and notifications still need end-to-end wiring and tests.

Do not expose the generic snapshot replacement endpoint to employee sessions. Use resource endpoints and enforce role rules for each operation. Payroll, attendance corrections and deletion approvals need additional business validation before production.

## Production checklist
- Set strong secrets in the hosting provider's secret manager.
- Use managed PostgreSQL with automated backups, encryption and private networking.
- Set exact frontend origins in CORS; never use wildcard origins with credentials.
- Terminate HTTPS at the ingress/reverse proxy.
- Use Alembic migrations for schema changes; do not rely on create_all for future upgrades.
- Add rate limiting, email verification/password reset, refresh-token rotation, monitoring, alerting and tested restore procedures.
- Have a security review before storing real employee or hospital data.

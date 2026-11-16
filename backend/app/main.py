from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID
import re

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app.deps import get_current_user, require_roles
from app.models import AuditLog, Organization, ResourceRecord, User
from app.schemas import LoginRequest, OrganizationCreate, ResourceCreate, ResourceUpdate, SnapshotUpdate, UserCreate
from app.security import create_access_token, hash_password, verify_password

RESOURCE_TYPES = {
    "employees", "tasks", "shifts", "leaveRequests", "resignations", "chats",
    "supportQueries", "deletionAudits", "attendanceLogs", "payslips",
    "workloadRequests", "notifications", "messages"
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are created for a fresh installation. Use Alembic migrations for managed production upgrades.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def org_for_user(db: Session, code: str, user: User) -> Organization:
    org = db.scalar(select(Organization).where(Organization.code == code, Organization.is_active.is_(True)))
    if not org:
        raise HTTPException(404, "Organization not found")
    if user.role != "superadmin" and user.organization_id != org.id:
        raise HTTPException(403, "You cannot access another organization's data")
    return org


def audit(db: Session, user: User, org: Organization | None, action: str, kind: str | None = None, record_id: str | None = None):
    db.add(AuditLog(
        organization_id=org.id if org else None, actor_user_id=user.id,
        action=action, resource_type=kind, record_id=record_id
    ))


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "service": settings.app_name, "database": "connected"}


@app.post(f"{settings.api_prefix}/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    stmt = select(User).where(User.username == body.username, User.is_active.is_(True))
    candidates = list(db.scalars(stmt))
    user = None
    for candidate in candidates:
        if candidate.role == "superadmin" and body.organization_code is None:
            if verify_password(body.password, candidate.password_hash):
                user = candidate
                break
        elif candidate.organization and body.organization_code and candidate.organization.code == body.organization_code.upper():
            if verify_password(body.password, candidate.password_hash):
                user = candidate
                break
    if not user:
        raise HTTPException(status_code=401, detail="Invalid organization, username, or password")
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    return {
        "access_token": create_access_token(str(user.id), user.role),
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
        "user": {
            "id": str(user.id), "username": user.username, "full_name": user.full_name,
            "role": user.role, "employee_id": user.employee_id,
            "organization_code": org.code if org else None,
            "organization_name": org.name if org else None,
            "sector": org.sector if org else None,
        },
    }


@app.get(f"{settings.api_prefix}/auth/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    return {
        "id": str(user.id), "username": user.username, "full_name": user.full_name,
        "role": user.role, "employee_id": user.employee_id,
        "organization_code": org.code if org else None,
        "organization_name": org.name if org else None,
        "sector": org.sector if org else None,
    }


@app.get(f"{settings.api_prefix}/organizations")
def list_organizations(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    stmt = select(Organization).where(Organization.is_active.is_(True))
    if user.role != "superadmin":
        stmt = stmt.where(Organization.id == user.organization_id)
    return [{"code": o.code, "sector": o.sector, "name": o.name, "settings": o.settings} for o in db.scalars(stmt).all()]


@app.post(f"{settings.api_prefix}/organizations", status_code=201)
def create_organization(
    body: OrganizationCreate, db: Session = Depends(get_db),
    user: User = Depends(require_roles("superadmin"))
):
    code = body.code.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,39}", code):
        raise HTTPException(422, "Organization code may contain only letters, numbers, and hyphens")
    if db.scalar(select(Organization).where(Organization.code == code)):
        raise HTTPException(409, "Organization code already exists")
    org = Organization(code=code, sector=body.sector, name=body.name, settings=body.settings)
    db.add(org)
    db.flush()
    audit(db, user, org, "organization.created")
    db.commit()
    return {"code": org.code, "sector": org.sector, "name": org.name}


@app.post(f"{settings.api_prefix}/organizations/{{code}}/users", status_code=201)
def create_user(
    code: str, body: UserCreate, db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    org = org_for_user(db, code.upper(), user)
    if body.role not in {"admin", "employee"}:
        raise HTTPException(422, "Only admin or employee roles can be provisioned here")
    if user.role == "admin" and body.role != "employee":
        raise HTTPException(403, "Organization admins can create employee accounts only")
    if user.role not in {"superadmin", "admin"}:
        raise HTTPException(403, "Only administrators can create accounts")
    existing = db.scalar(select(User).where(User.organization_id == org.id, User.username == body.username))
    if existing:
        raise HTTPException(409, "Username already exists in this organization")
    new_user = User(
        organization_id=org.id, username=body.username.strip(), full_name=body.full_name.strip(),
        email=body.email, role=body.role, employee_id=body.employee_id,
        password_hash=hash_password(body.password)
    )
    db.add(new_user)
    audit(db, user, org, "user.created", "users", body.username)
    db.commit()
    return {"username": new_user.username, "role": new_user.role, "employee_id": new_user.employee_id}


def assert_resource_access(org: Organization, resource_type: str, payload: dict, user: User, write: bool, external_id: str | None = None):
    if user.role == "superadmin":
        return
    if user.organization_id != org.id:
        raise HTTPException(403, "Cross-organization access denied")
    if user.role == "admin":
        return
    if not write:
        owner = payload.get("employee_id") or payload.get("empId") or payload.get("submitterId")
        if resource_type in {"employees", "tasks", "shifts"}:
            if resource_type == "employees" and (payload.get("employee_id") or payload.get("id") or external_id) != user.employee_id:
                raise HTTPException(403, "You can only view your own employee record")
            if resource_type in {"tasks", "shifts"}:
                return
        elif owner and str(owner) != str(user.employee_id):
            raise HTTPException(403, "You can only view your own records")
        return
    if resource_type not in {"attendanceLogs", "leaveRequests", "supportQueries", "resignations", "workloadRequests", "messages", "chats"}:
        raise HTTPException(403, "Employees cannot modify this resource")
    owner = payload.get("employee_id") or payload.get("empId") or payload.get("submitterId")
    if not owner or str(owner) != str(user.employee_id):
        raise HTTPException(403, "Employee-owned record is required")


@app.get(f"{settings.api_prefix}/organizations/{{code}}/resources/{{resource_type}}")
def list_resources(
    code: str, resource_type: str, db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if resource_type not in RESOURCE_TYPES:
        raise HTTPException(404, "Unknown resource type")
    org = org_for_user(db, code.upper(), user)
    rows = db.scalars(select(ResourceRecord).where(
        ResourceRecord.organization_id == org.id, ResourceRecord.resource_type == resource_type
    )).all()
    result = []
    for row in rows:
        try:
            assert_resource_access(org, resource_type, row.payload, user, False, row.external_id)
            result.append({"id": row.external_id, **row.payload})
        except HTTPException:
            continue
    return result


@app.post(f"{settings.api_prefix}/organizations/{{code}}/resources/{{resource_type}}", status_code=201)
def create_resource(
    code: str, resource_type: str, body: ResourceCreate, db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if resource_type not in RESOURCE_TYPES:
        raise HTTPException(404, "Unknown resource type")
    org = org_for_user(db, code.upper(), user)
    assert_resource_access(org, resource_type, body.payload, user, True)
    existing = db.scalar(select(ResourceRecord).where(
        ResourceRecord.organization_id == org.id, ResourceRecord.resource_type == resource_type,
        ResourceRecord.external_id == body.external_id
    ))
    if existing:
        raise HTTPException(409, "Record already exists")
    row = ResourceRecord(organization_id=org.id, resource_type=resource_type, external_id=body.external_id, payload=body.payload)
    db.add(row)
    audit(db, user, org, f"{resource_type}.created", resource_type, body.external_id)
    db.commit()
    return {"id": row.external_id, **row.payload}


@app.patch(f"{settings.api_prefix}/organizations/{{code}}/resources/{{resource_type}}/{{external_id}}")
def update_resource(
    code: str, resource_type: str, external_id: str, body: ResourceUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if resource_type not in RESOURCE_TYPES:
        raise HTTPException(404, "Unknown resource type")
    org = org_for_user(db, code.upper(), user)
    row = db.scalar(select(ResourceRecord).where(
        ResourceRecord.organization_id == org.id, ResourceRecord.resource_type == resource_type,
        ResourceRecord.external_id == external_id
    ))
    if not row:
        raise HTTPException(404, "Record not found")
    assert_resource_access(org, resource_type, row.payload, user, True)
    assert_resource_access(org, resource_type, body.payload, user, True)
    row.payload = body.payload
    audit(db, user, org, f"{resource_type}.updated", resource_type, external_id)
    db.commit()
    return {"id": row.external_id, **row.payload}


@app.delete(f"{settings.api_prefix}/organizations/{{code}}/resources/{{resource_type}}/{{external_id}}", status_code=204)
def delete_resource(
    code: str, resource_type: str, external_id: str, db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "superadmin"))
):
    if resource_type not in RESOURCE_TYPES:
        raise HTTPException(404, "Unknown resource type")
    org = org_for_user(db, code.upper(), user)
    row = db.scalar(select(ResourceRecord).where(
        ResourceRecord.organization_id == org.id, ResourceRecord.resource_type == resource_type,
        ResourceRecord.external_id == external_id
    ))
    if not row:
        raise HTTPException(404, "Record not found")
    db.delete(row)
    audit(db, user, org, f"{resource_type}.deleted", resource_type, external_id)
    db.commit()
    return None


@app.get(f"{settings.api_prefix}/organizations/{{code}}/snapshot")
def get_snapshot(
    code: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    org = org_for_user(db, code.upper(), user)
    rows = db.scalars(select(ResourceRecord).where(ResourceRecord.organization_id == org.id)).all()
    result = {kind: [] for kind in RESOURCE_TYPES}
    for row in rows:
        try:
            assert_resource_access(org, row.resource_type, row.payload, user, False, row.external_id)
            result[row.resource_type].append({"id": row.external_id, **row.payload})
        except HTTPException:
            continue
    return {"organization": {"code": org.code, "sector": org.sector, "name": org.name}, "resources": result}


@app.put(f"{settings.api_prefix}/organizations/{{code}}/snapshot")
def replace_snapshot(
    code: str, body: SnapshotUpdate, db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "superadmin"))
):
    org = org_for_user(db, code.upper(), user)
    unknown = set(body.resources) - RESOURCE_TYPES
    if unknown:
        raise HTTPException(422, f"Unsupported resource types: {', '.join(sorted(unknown))}")
    db.query(ResourceRecord).filter(ResourceRecord.organization_id == org.id).delete()
    for kind, records in body.resources.items():
        for item in records:
            external_id = str(item.get("id") or item.get("external_id") or "")
            if not external_id:
                raise HTTPException(422, f"Each {kind} record requires an id")
            payload = {k: v for k, v in item.items() if k not in {"id", "external_id"}}
            db.add(ResourceRecord(organization_id=org.id, resource_type=kind, external_id=external_id, payload=payload))
    audit(db, user, org, "snapshot.replaced")
    db.commit()
    return {"saved": True, "resource_types": len(body.resources)}


@app.get(f"{settings.api_prefix}/audit")
def list_audit(
    limit: int = 100, db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "superadmin"))
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(max(limit, 1), 500))
    if user.role != "superadmin":
        stmt = stmt.where(AuditLog.organization_id == user.organization_id)
    return [{
        "action": row.action, "resource_type": row.resource_type, "record_id": row.record_id,
        "details": row.details, "created_at": row.created_at.isoformat()
    } for row in db.scalars(stmt).all()]

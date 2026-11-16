"""Create the first platform administrator and an optional demo hospital."""
from sqlalchemy import select
from app.config import settings
from app.database import SessionLocal
from app.models import Organization, User, ResourceRecord
from app.security import hash_password


def run():
    db = SessionLocal()
    try:
        root = db.scalar(select(User).where(User.role == "superadmin", User.username == settings.superadmin_username))
        if not root:
            db.add(User(
                organization_id=None, username=settings.superadmin_username,
                full_name="SSKATT Platform Administrator", role="superadmin",
                password_hash=hash_password(settings.superadmin_password)
            ))
        if settings.seed_demo:
            org = db.scalar(select(Organization).where(Organization.code == "HOSP-001"))
            if not org:
                org = Organization(code="HOSP-001", sector="Hospital", name="Apex Healthcare & Research Institute")
                db.add(org)
                db.flush()
            admin = db.scalar(select(User).where(User.organization_id == org.id, User.username == "admin"))
            if not admin:
                db.add(User(organization_id=org.id, username="admin", full_name="Hospital Administrator",
                            role="admin", password_hash=hash_password("ChangeMe!12345")))
            employee = db.scalar(select(User).where(User.organization_id == org.id, User.username == "E-1024"))
            if not employee:
                db.add(User(organization_id=org.id, username="E-1024", employee_id="E-1024",
                            full_name="Dr. Ananya Rao", role="employee",
                            password_hash=hash_password("ChangeMe!12345")))
            db.flush()
            sample = [
                ("employees", "E-1024", {"name":"Dr. Ananya Rao","dept":"Emergency","role":"Chief Trauma Specialist","shift":"Morning A (08:00 - 16:30)","status":"Present","basePay":180000,"attendedDays":24,"totalDays":26,"casualLeaves":6,"sickLeaves":4,"privilegeLeaves":12,"employee_id":"E-1024"}),
                ("shifts", "SHIFT-001", {"name":"Morning Shift (Ward Coverage)","hours":"07:00 - 15:30","required":85,"allocated":88,"status":"Optimal"}),
                ("tasks", "TSK-H1", {"title":"Emergency Trauma Duty","zone":"Ward A / Trauma","assignee":"Dr. Ananya Rao","priority":"High","progress":85,"status":"In Progress"}),
            ]
            for kind, key, payload in sample:
                exists = db.scalar(select(ResourceRecord).where(ResourceRecord.organization_id == org.id, ResourceRecord.resource_type == kind, ResourceRecord.external_id == key))
                if not exists:
                    db.add(ResourceRecord(organization_id=org.id, resource_type=kind, external_id=key, payload=payload))
        db.commit()
        print("SSKATT database initialized.")
        print(f"Super Admin username: {settings.superadmin_username}")
        if settings.seed_demo:
            print("Demo hospital: HOSP-001; admin username: admin; employee username: E-1024")
            print("Demo passwords are ChangeMe!12345. Change them immediately after first login.")
    finally:
        db.close()


if __name__ == "__main__":
    run()

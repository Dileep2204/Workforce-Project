import os
from uuid import uuid4

os.environ.setdefault("JWT_SECRET", "ci-only-test-secret-not-production")
os.environ.setdefault("SUPERADMIN_PASSWORD", "ci-only-password-not-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Organization, User
from app.security import hash_password


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    org_code = f"TST-{uuid4().hex[:8].upper()}"
    with SessionLocal() as db:
        org = Organization(code=org_code, sector="Hospital", name="Integration Test Hospital")
        db.add(org)
        db.flush()
        db.add(User(organization_id=org.id, username="test-admin", full_name="Test Admin",
                    role="admin", password_hash=hash_password("AdminPassword!123")))
        db.add(User(organization_id=None, username="test-root", full_name="Test Root",
                    role="superadmin", password_hash=hash_password("RootPassword!123")))
        db.commit()
    with TestClient(app) as test_client:
        test_client.org_code = org_code
        yield test_client
    Base.metadata.drop_all(bind=engine)


def login(client, username, password, org_code=None):
    response = client.post("/api/v1/auth/login", json={
        "organization_code": org_code, "username": username, "password": password
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_employee_provision_login_and_attendance_are_persistent(client):
    admin = login(client, "test-admin", "AdminPassword!123", client.org_code)
    response = client.post(f"/api/v1/organizations/{client.org_code}/employees", headers=admin, json={
        "username": "EMP-100", "password": "EmployeePassword!123",
        "full_name": "Integration Employee", "employee_id": "EMP-100",
        "employee": {"id": "EMP-100", "name": "Integration Employee", "dept": "Emergency", "basePay": 50000}
    })
    assert response.status_code == 201, response.text
    assert "password" not in response.json()["employee"]

    employee = login(client, "EMP-100", "EmployeePassword!123", client.org_code)
    punch_in = client.post(f"/api/v1/organizations/{client.org_code}/attendance/punch",
                           headers=employee, json={"action": "in"})
    assert punch_in.status_code == 201, punch_in.text
    assert punch_in.json()["attendedDays"] == 1
    duplicate = client.post(f"/api/v1/organizations/{client.org_code}/attendance/punch",
                            headers=employee, json={"action": "in"})
    assert duplicate.status_code == 409
    punch_out = client.post(f"/api/v1/organizations/{client.org_code}/attendance/punch",
                            headers=employee, json={"action": "out"})
    assert punch_out.status_code == 201
    snapshot = client.get(f"/api/v1/organizations/{client.org_code}/snapshot", headers=employee)
    assert snapshot.status_code == 200
    assert snapshot.json()["resources"]["employees"][0]["attendedDays"] == 1


def test_leave_request_approval_notifies_employee(client):
    admin = login(client, "test-admin", "AdminPassword!123", client.org_code)
    provision = client.post(f"/api/v1/organizations/{client.org_code}/employees", headers=admin, json={
        "username": "EMP-200", "password": "EmployeePassword!123",
        "full_name": "Leave Tester", "employee_id": "EMP-200",
        "employee": {"id": "EMP-200", "name": "Leave Tester", "dept": "Ward"}
    })
    assert provision.status_code == 201
    employee = login(client, "EMP-200", "EmployeePassword!123", client.org_code)
    leave = client.post(f"/api/v1/organizations/{client.org_code}/resources/leaveRequests",
                        headers=employee, json={"external_id": "LR-200", "payload": {
                            "id": "LR-200", "employee_id": "EMP-200", "empId": "EMP-200",
                            "empName": "Leave Tester", "status": "Pending", "days": 2
                        }})
    assert leave.status_code == 201, leave.text
    decision = client.post(f"/api/v1/organizations/{client.org_code}/leave-requests/LR-200/decision",
                           headers=admin, json={"status": "Approved", "remarks": "Approved for test"})
    assert decision.status_code == 200, decision.text
    snapshot = client.get(f"/api/v1/organizations/{client.org_code}/snapshot", headers=employee)
    assert snapshot.json()["resources"]["leaveRequests"][0]["status"] == "Approved"
    assert snapshot.json()["resources"]["notifications"][0]["employee_id"] == "EMP-200"


def test_tenant_boundary_blocks_other_organization(client):
    admin = login(client, "test-admin", "AdminPassword!123", client.org_code)
    other_code = f"OTH-{uuid4().hex[:8].upper()}"
    with SessionLocal() as db:
        db.add(Organization(code=other_code, sector="Retail", name="Other Tenant"))
        db.commit()
    response = client.get(f"/api/v1/organizations/{other_code}/snapshot", headers=admin)
    assert response.status_code == 403

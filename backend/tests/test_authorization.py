import os
from types import SimpleNamespace
from uuid import uuid4

os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production")
os.environ.setdefault("SUPERADMIN_PASSWORD", "test-only-password-not-for-production")

import pytest
from fastapi import HTTPException

from app.main import assert_resource_access


ORG_ID = uuid4()
OTHER_ORG_ID = uuid4()
employee = SimpleNamespace(role="employee", organization_id=ORG_ID, employee_id="EMP-001")
admin = SimpleNamespace(role="admin", organization_id=ORG_ID, employee_id=None)
superadmin = SimpleNamespace(role="superadmin", organization_id=None, employee_id=None)
org = SimpleNamespace(id=ORG_ID)


def test_employee_can_read_own_employee_record():
    assert_resource_access(org, "employees", {"id": "EMP-001"}, employee, False, "EMP-001")


def test_employee_cannot_read_another_employee_record():
    with pytest.raises(HTTPException) as error:
        assert_resource_access(org, "employees", {"id": "EMP-002"}, employee, False, "EMP-002")
    assert error.value.status_code == 403


def test_employee_cannot_read_unowned_task():
    with pytest.raises(HTTPException) as error:
        assert_resource_access(org, "tasks", {"title": "Unassigned task"}, employee, False, "TSK-1")
    assert error.value.status_code == 403


def test_employee_can_read_own_task():
    assert_resource_access(org, "tasks", {"employee_id": "EMP-001"}, employee, False, "TSK-1")


def test_employee_can_submit_own_leave_request():
    assert_resource_access(org, "leaveRequests", {"employee_id": "EMP-001"}, employee, True)


@pytest.mark.parametrize("resource_type", [
    "employees", "tasks", "shifts", "attendanceLogs", "payslips",
    "notifications", "messages", "chats", "supportQueries"
])
def test_employee_cannot_create_privileged_or_general_records(resource_type):
    with pytest.raises(HTTPException) as error:
        assert_resource_access(org, resource_type, {"employee_id": "EMP-001"}, employee, True)
    assert error.value.status_code == 403


def test_employee_cannot_read_other_tenant_even_if_called_directly():
    other_org = SimpleNamespace(id=OTHER_ORG_ID)
    with pytest.raises(HTTPException) as error:
        assert_resource_access(other_org, "tasks", {"employee_id": "EMP-001"}, employee, False)
    assert error.value.status_code == 403


def test_admin_can_access_records_in_own_tenant():
    assert_resource_access(org, "payslips", {"employee_id": "EMP-002"}, admin, False)
    assert_resource_access(org, "payslips", {"employee_id": "EMP-002"}, admin, True)


def test_superadmin_can_access_any_tenant_resource():
    other_org = SimpleNamespace(id=OTHER_ORG_ID)
    assert_resource_access(other_org, "payslips", {"employee_id": "EMP-002"}, superadmin, True)

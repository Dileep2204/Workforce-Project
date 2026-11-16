from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    organization_code: str | None = None
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class OrganizationCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    sector: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=200)
    settings: dict = Field(default_factory=dict)


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=120)
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=256)
    role: str = "employee"
    employee_id: str | None = None
    email: str | None = None


class ResourceCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=120)
    payload: dict


class ResourceUpdate(BaseModel):
    payload: dict


class SnapshotUpdate(BaseModel):
    resources: dict[str, list[dict]]


class UserOut(BaseModel):
    id: str
    username: str
    full_name: str
    role: str
    organization_code: str | None
    employee_id: str | None

    model_config = ConfigDict(from_attributes=True)


from typing import Literal


class AttendancePunchRequest(BaseModel):
    action: Literal["in", "out"]

from typing import Literal
from pydantic import BaseModel, Field

class EmployeeProvisionRequest(BaseModel):
    username: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=2, max_length=200)
    employee_id: str = Field(min_length=1, max_length=80)
    employee: dict


class LeaveDecisionRequest(BaseModel):
    status: Literal["Approved", "Rejected"]
    remarks: str = Field(default="", max_length=1000)


class OrganizationProvisionRequest(OrganizationCreate):
    admin_username: str = Field(min_length=2, max_length=120)
    admin_password: str = Field(min_length=12, max_length=256)
    admin_full_name: str = Field(default="Organization Administrator", min_length=2, max_length=200)

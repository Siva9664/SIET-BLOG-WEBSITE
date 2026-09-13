from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LabBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=50)
    slug: str = Field(..., min_length=2, max_length=150)
    department_id: Optional[int] = None
    description: Optional[str] = None
    is_active: bool = True


class LabCreate(LabBase):
    pass


class LabUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    slug: Optional[str] = None
    department_id: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class LabResponse(LabBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LabMembershipCreate(BaseModel):
    user_id: int
    role: str = "LAB_ADMIN"
    is_active: bool = True


class LabMembershipResponse(BaseModel):
    id: int
    user_id: int
    lab_id: int
    role: str
    is_active: bool
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TemplateLabAssignmentCreate(BaseModel):
    template_id: int
    is_active: bool = True


class TemplateLabAssignmentResponse(BaseModel):
    id: int
    template_id: int
    lab_id: int
    is_active: bool
    template_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

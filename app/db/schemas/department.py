from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Название отдела")


class DepartmentData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str

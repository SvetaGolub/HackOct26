from pydantic import BaseModel, Field, field_validator


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("Название отдела не может быть пустым")
        return name


class DepartmentData(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str

from pydantic import BaseModel


class CampusBase(BaseModel):
    name: str
    code: str
    address: str
    latitude: float
    longitude: float
    description: str | None = None


class CampusCreate(CampusBase):
    pass


class CampusUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None


class CampusResponse(CampusBase):
    id: int

    model_config = {"from_attributes": True}
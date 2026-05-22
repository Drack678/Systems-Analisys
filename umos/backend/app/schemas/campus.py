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


class CampusResponse(CampusBase):
    id: int

    model_config = {"from_attributes": True}
from pydantic import BaseModel

class CurrentUser(BaseModel):
    id: str
    name: str
    scopes: list[str]
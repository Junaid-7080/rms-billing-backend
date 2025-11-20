from pydantic import BaseModel
from typing import Optional

class ChangeRoleResponse(BaseModel):
    message: str
    userId: str
    oldRole: str
    newRole: str
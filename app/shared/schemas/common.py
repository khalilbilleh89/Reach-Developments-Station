"""Common response schemas used across all modules."""

from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel

DataT = TypeVar("DataT")


class ResponseEnvelope(BaseModel, Generic[DataT]):
    """Standard API response envelope."""

    data: Optional[DataT] = None
    errors: List[dict] = []

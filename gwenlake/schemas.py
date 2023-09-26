
"""Schemas for the Gwenlake API."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    PrivateAttr,
    StrictBool,
    StrictFloat,
    StrictInt,
)

# try:
#     from pydantic.v1 import (  # type: ignore[import]
#         BaseModel,
#         Field,
#         PrivateAttr,
#         StrictBool,
#         StrictFloat,
#         StrictInt,
#     )
# except ImportError:
#     from pydantic import (
#         BaseModel,
#         Field,
#         PrivateAttr,
#         StrictBool,
#         StrictFloat,
#         StrictInt,
#     )

from typing_extensions import Literal


class DataType(str, Enum):
    """Enum for dataset data types."""

    kv = "kv"
    llm = "llm"
    chat = "chat"


class DatasetBase(BaseModel):
    """Dataset base model."""

    name: str
    description: Optional[str] = None
    data_type: Optional[DataType] = None

    class Config:
        frozen = True


class DatasetCreate(DatasetBase):
    """Dataset create model."""

    id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Dataset(DatasetBase):
    """Dataset ORM model."""

    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)
    _host_url: Optional[str] = PrivateAttr(default=None)

    def __init__(self, _host_url: Optional[str] = None, **kwargs: Any) -> None:
        """Initialize a Run object."""
        super().__init__(**kwargs)
        self._host_url = _host_url

    @property
    def url(self) -> Optional[str]:
        """URL of this run within the app."""
        if self._host_url:
            return f"{self._host_url}/data/{self.id}"
        return None

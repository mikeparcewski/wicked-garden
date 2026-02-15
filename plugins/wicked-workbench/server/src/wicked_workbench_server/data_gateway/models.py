"""Pydantic models for Data Gateway request/response shapes.

These models define the standard envelope that all gateway responses follow,
enabling consuming services to deserialize any response with:

    response = GatewayResponse(**raw_json)
"""
from typing import Any, Optional, Union

from pydantic import BaseModel


class ResponseMeta(BaseModel):
    """Metadata envelope for all gateway responses."""
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    source: str = ""
    plugin: str = ""
    timestamp: str = ""
    verb: Optional[str] = None
    item_id: Optional[str] = None


class GatewayResponse(BaseModel):
    """Standard response envelope for all data gateway operations."""
    data: Union[dict, list]
    meta: ResponseMeta


class GatewayError(BaseModel):
    """Standard error response from the data gateway."""
    error: str
    code: str
    details: Optional[dict] = None

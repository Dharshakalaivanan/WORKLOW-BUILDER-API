from pydantic import BaseModel, Field
from typing import List, Any, Optional


class WorkflowBase(BaseModel):
	name: str = Field(..., min_length=1)
	nodes: List[Any] = Field(default_factory=list)
	edges: List[Any] = Field(default_factory=list)


class WorkflowCreate(WorkflowBase):
	pass


class WorkflowUpdate(BaseModel):
	name: Optional[str] = None
	nodes: Optional[List[Any]] = None
	edges: Optional[List[Any]] = None


class WorkflowOut(WorkflowBase):
	id: int

	class Config:
		from_attributes = True

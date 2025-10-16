from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from .database import Base


class Workflow(Base):
	__tablename__ = "workflows"

	id = Column(Integer, primary_key=True, index=True)
	name = Column(String(255), nullable=False)
	nodes = Column(Text, nullable=False, default="[]")  # JSON string
	edges = Column(Text, nullable=False, default="[]")  # JSON string
	created_at = Column(DateTime(timezone=True), server_default=func.now())
	updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

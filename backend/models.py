from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text,
    DateTime, ForeignKey, func,
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=False, default="")
    is_active = Column(Integer, default=1)  # 1=active, 0=disabled
    created_at = Column(DateTime, default=func.now())

    reports = relationship("Report", back_populates="creator", cascade="all, delete")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False, default="Untitled Analysis")
    tender_snippet = Column(Text, nullable=False, default="")  # first 300 chars for preview
    vendor_snippet = Column(Text, nullable=False, default="")
    overall_score = Column(Float, nullable=False, default=0.0)
    count_compliant = Column(Integer, default=0)
    count_partial = Column(Integer, default=0)
    count_non_compliant = Column(Integer, default=0)
    total_clauses = Column(Integer, default=0)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())

    creator = relationship("User", back_populates="reports")
    clauses = relationship(
        "Clause", back_populates="report",
        cascade="all, delete", order_by="Clause.clause_number",
    )


class Clause(Base):
    __tablename__ = "clauses"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    clause_number = Column(Integer, nullable=False)
    clause_text = Column(Text, nullable=False)
    score = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="non-compliant")
    matched_terms = Column(Text, default="")   # JSON array string
    missing_terms = Column(Text, default="")   # JSON array string
    best_vendor_match = Column(Text, default="")  # most semantically similar vendor sentence

    report = relationship("Report", back_populates="clauses")

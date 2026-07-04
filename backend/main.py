"""
TenderCheck — FastAPI Backend
Provides REST API for authentication, analysis, and report persistence.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import (
    Depends, FastAPI, File, Form, HTTPException,
    UploadFile, status,
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    verify_password,
)
from .database import Base, engine, get_db
from .models import Clause, Report, User
from .nlp import extract_requirements, score_clauses
from .pdf_extract import extract_text
from .seed import seed_users

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TenderCheck API",
    description="BDL Tender Compliance Analyzer — FastAPI backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in local dev
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # Create all tables
    Base.metadata.create_all(bind=engine)
    # Seed default users
    db = next(get_db())
    try:
        seed_users(db)
    finally:
        db.close()


# ── Pydantic schemas ─────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str

    model_config = {"from_attributes": True}


class ClauseOut(BaseModel):
    id: int
    clause_number: int
    clause_text: str
    score: float
    status: str
    matched_terms: list[str]
    missing_terms: list[str]
    best_vendor_match: str

    model_config = {"from_attributes": True}


class ReportSummary(BaseModel):
    id: int
    title: str
    overall_score: float
    count_compliant: int
    count_partial: int
    count_non_compliant: int
    total_clauses: int
    created_at: str
    creator_name: str

    model_config = {"from_attributes": True}


class ReportDetail(ReportSummary):
    tender_snippet: str
    vendor_snippet: str
    clauses: list[ClauseOut]


# ── Helpers ───────────────────────────────────────────────────────────────────
def _report_summary(r: Report) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "overall_score": r.overall_score,
        "count_compliant": r.count_compliant,
        "count_partial": r.count_partial,
        "count_non_compliant": r.count_non_compliant,
        "total_clauses": r.total_clauses,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "creator_name": r.creator.full_name if r.creator else "",
    }


def _clause_out(c: Clause) -> dict:
    return {
        "id": c.id,
        "clause_number": c.clause_number,
        "clause_text": c.clause_text,
        "score": c.score,
        "status": c.status,
        "matched_terms": json.loads(c.matched_terms) if c.matched_terms else [],
        "missing_terms": json.loads(c.missing_terms) if c.missing_terms else [],
        "best_vendor_match": c.best_vendor_match or "",
    }


# ── Routes: Auth ─────────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token({"sub": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "full_name": user.full_name},
    }


@app.get("/auth/me", tags=["auth"])
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
    }


# ── Routes: Analysis ─────────────────────────────────────────────────────────
@app.post("/analyze", tags=["analysis"])
async def analyze(
    title: str = Form("Untitled Analysis"),
    tender_file: Optional[UploadFile] = File(None),
    vendor_file: Optional[UploadFile] = File(None),
    tender_text: Optional[str] = Form(None),
    vendor_text: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Resolve tender text
    t_text = ""
    if tender_file and tender_file.filename:
        raw = await tender_file.read()
        t_text = extract_text(raw, tender_file.filename)
    elif tender_text:
        t_text = tender_text

    # Resolve vendor text
    v_text = ""
    if vendor_file and vendor_file.filename:
        raw = await vendor_file.read()
        v_text = extract_text(raw, vendor_file.filename)
    elif vendor_text:
        v_text = vendor_text

    if not t_text.strip() or not v_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Both tender and vendor documents are required.",
        )

    # Run semantic NLP
    clauses_raw = extract_requirements(t_text)
    if not clauses_raw:
        raise HTTPException(status_code=400, detail="No requirements could be extracted from the tender document.")

    clause_results = score_clauses(clauses_raw, v_text)

    # Compute summary stats
    count_c = sum(1 for c in clause_results if c["status"] == "compliant")
    count_p = sum(1 for c in clause_results if c["status"] == "partial")
    count_n = sum(1 for c in clause_results if c["status"] == "non-compliant")
    total = len(clause_results)
    overall = round((count_c * 100 + count_p * 50) / total) if total else 0

    # Persist report
    report = Report(
        title=title,
        tender_snippet=t_text[:300],
        vendor_snippet=v_text[:300],
        overall_score=overall,
        count_compliant=count_c,
        count_partial=count_p,
        count_non_compliant=count_n,
        total_clauses=total,
        created_by_id=current_user.id,
    )
    db.add(report)
    db.flush()  # get report.id

    for cr in clause_results:
        clause = Clause(
            report_id=report.id,
            clause_number=cr["id"],
            clause_text=cr["text"],
            score=cr["score"],
            status=cr["status"],
            matched_terms=json.dumps(cr["matched_terms"]),
            missing_terms=json.dumps(cr["missing_terms"]),
            best_vendor_match=cr["best_vendor_match"],
        )
        db.add(clause)

    db.commit()
    db.refresh(report)

    return {
        **_report_summary(report),
        "tender_snippet": report.tender_snippet,
        "vendor_snippet": report.vendor_snippet,
        "clauses": [_clause_out(c) for c in report.clauses],
    }


# ── Routes: Reports ──────────────────────────────────────────────────────────
@app.get("/reports", tags=["reports"])
def list_reports(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reports = (
        db.query(Report)
        .order_by(Report.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(Report).count()
    return {"total": total, "reports": [_report_summary(r) for r in reports]}


@app.get("/reports/{report_id}", tags=["reports"])
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        **_report_summary(report),
        "tender_snippet": report.tender_snippet,
        "vendor_snippet": report.vendor_snippet,
        "clauses": [_clause_out(c) for c in report.clauses],
    }


@app.delete("/reports/{report_id}", tags=["reports"])
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(report)
    db.commit()
    return {"detail": f"Report {report_id} deleted."}


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "TenderCheck API v1.0"}


# ── Static frontend files — mount AFTER all API routes ───────────────────────
# Access the UI at: http://127.0.0.1:8000/app/index.html
import os as _os
_frontend_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "frontend")
if _os.path.isdir(_frontend_dir):
    app.mount("/app", StaticFiles(directory=_frontend_dir, html=True), name="frontend")

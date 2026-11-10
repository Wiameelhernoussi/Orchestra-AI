from __future__ import annotations

import hmac
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictInt, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.api.deps import (
    get_completion_provider,
    get_current_user,
    get_db,
    get_evidence_fact_checker,
    get_settings,
)
from app.config import Settings
from app.models import (
    AcceptanceCriterion,
    Agreement,
    Approval,
    AuditLog,
    Evidence,
    Invoice,
    Milestone,
    Organization,
    User,
    WebhookEvent,
)
from app.services.groq_agents import (
    AgentResult,
    CompletionProvider,
    EvidenceAgent,
    GroqAPIError,
    GroqRateLimitError,
    IntentAgent,
)
from app.services.evidence_facts import EvidenceFactChecker
from app.services.image_evidence import prepare_images_for_analysis
from app.services.evidence_storage import (
    MAX_EVIDENCE_FILE_BYTES,
    MAX_EVIDENCE_FILES,
    MAX_EVIDENCE_TOTAL_BYTES,
    remove_evidence_files,
    resolve_evidence_file,
    safe_display_filename,
    store_evidence_files,
    validate_evidence_file,
)
from app.services.payment_readiness import calculate_payment_readiness
from app.state_machine.agreement_fsm import (
    AgreementStatus,
    validate_agreement_transition,
)
from app.state_machine.exceptions import (
    InvalidTransitionError,
    RoleError,
    SequentialMilestoneError,
)
from app.state_machine.milestone_fsm import (
    MilestoneStatus,
    validate_milestone_transition,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["workflow"])
client_router = APIRouter(prefix="/client", tags=["client"])
provider_router = APIRouter(prefix="/provider", tags=["provider"])


class CriterionQualityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: str
    objectively_verifiable: bool
    reason: str
    rewritten_criterion: str = ""


class MilestoneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    amount_cents: StrictInt = Field(gt=0)
    deliverables: list[str] = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    criteria_quality: list[CriterionQualityInput] = Field(default_factory=list)


class IntentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_type: str = Field(min_length=1, max_length=200)
    requirements: list[str] = Field(default_factory=list)
    budget_cents: StrictInt = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    deadline: str = ""
    missing_information: list[str] = Field(default_factory=list)
    milestones: list[MilestoneInput] = Field(min_length=1)


class ParseIntentRequest(BaseModel):
    request: str = Field(min_length=1, max_length=6000)


class CreateAgreementRequest(BaseModel):
    intent: IntentPayload


class DecisionNotes(BaseModel):
    notes: str = Field(default="", max_length=2000)


class ApprovalDecision(BaseModel):
    acknowledge_unverified: bool = False


class EvidenceSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(default="", max_length=6000)
    links: list[HttpUrl] = Field(default_factory=list, max_length=10)
    criterion_ids: list[str] = Field(default_factory=list, max_length=20)


def _record_audit(
    db: Session,
    agreement: Agreement,
    action: str,
    *,
    user: User | None,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            agreement_id=agreement.id,
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details or {}, separators=(",", ":"), sort_keys=True),
        )
    )


def _agreement_for_member(
    db: Session,
    agreement_id: str,
    user: User,
    *,
    required_role: str | None = None,
) -> Agreement:
    agreement = db.get(Agreement, agreement_id)
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found.")
    if user.organization_id not in {agreement.client_org_id, agreement.provider_org_id}:
        raise HTTPException(status_code=404, detail="Agreement not found.")
    if required_role == "client" and (
        user.role != "client" or user.organization_id != agreement.client_org_id
    ):
        raise HTTPException(status_code=403, detail="Only the agreement client can perform this action.")
    if required_role == "provider" and (
        user.role != "provider" or user.organization_id != agreement.provider_org_id
    ):
        raise HTTPException(status_code=403, detail="Only the agreement provider can perform this action.")
    return agreement


def _milestone_for_agreement(
    db: Session,
    agreement: Agreement,
    milestone_id: str,
) -> Milestone:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None or milestone.agreement_id != agreement.id:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    return milestone


@router.get("/milestones/{milestone_id}/payment-readiness")
def get_milestone_payment_readiness(
    milestone_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    milestone = db.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    agreement = _agreement_for_member(db, milestone.agreement_id, user)
    milestone = _milestone_for_agreement(db, agreement, milestone_id)
    return calculate_payment_readiness(db, milestone)


@router.get("/evidence/{evidence_id}/attachments/{attachment_id}")
def download_evidence_attachment(
    evidence_id: str,
    attachment_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    evidence = db.get(Evidence, evidence_id)
    if evidence is None or not evidence.file_path:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    milestone = db.get(Milestone, evidence.milestone_id)
    agreement = (
        db.get(Agreement, milestone.agreement_id)
        if milestone is not None
        else None
    )
    if agreement is None:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    _agreement_for_member(db, agreement.id, user)
    try:
        evidence_data = json.loads(evidence.content or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=404, detail="Attachment not found.") from None
    attachments = (
        evidence_data.get("attachments")
        if isinstance(evidence_data, dict)
        else None
    )
    metadata = next(
        (
            item
            for item in attachments
            if isinstance(item, dict) and item.get("id") == attachment_id
        ),
        None,
    ) if isinstance(attachments, list) else None
    if metadata is None:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    path = resolve_evidence_file(settings.MEDIA_DIR, evidence.id, attachment_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    content_type = metadata.get("content_type")
    if content_type not in {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
    }:
        raise HTTPException(status_code=404, detail="Attachment not found.")
    return FileResponse(
        path,
        media_type=content_type,
        filename=safe_display_filename(str(metadata.get("name", "evidence-file"))),
        headers={"X-Content-Type-Options": "nosniff"},
    )


def _transition_milestone(
    milestone: Milestone,
    target: MilestoneStatus,
    *,
    role: str | None,
    evidence_count: int = 0,
    previous_status: str | None = None,
) -> None:
    try:
        validate_milestone_transition(
            MilestoneStatus(milestone.status),
            target,
            user_role=role,
            evidence_count=evidence_count,
            milestone_order=milestone.order - 1,
            previous_milestone_status=previous_status,
        )
    except RoleError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (InvalidTransitionError, SequentialMilestoneError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    milestone.status = target.value


def _milestone_summary(db: Session, milestone: Milestone) -> dict[str, Any]:
    invoices = (
        db.query(Invoice)
        .filter(Invoice.milestone_id == milestone.id)
        .order_by(Invoice.created_at.desc())
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.milestone_id == milestone.id)
        .order_by(Evidence.created_at.asc())
        .all()
    )
    return {
        "id": milestone.id,
        "title": milestone.title,
        "description": milestone.description,
        "order": milestone.order,
        "status": milestone.status,
        "amount_cents": milestone.amount_cents,
        "acceptance_criteria": [
            item.description
            for item in sorted(milestone.criteria, key=lambda criterion: criterion.id)
        ],
        "criteria": [
            {"id": item.id, "description": item.description}
            for item in sorted(milestone.criteria, key=lambda criterion: criterion.id)
        ],
        "evidence": [
            {
                "id": item.id,
                "type": item.evidence_type,
                "content": item.content,
                "submission_status": "SUBMITTED",
                "verification_status": "ADVISORY",
                "ai_report": json.loads(item.ai_report) if item.ai_report else None,
                "link_checks": json.loads(item.link_checks) if item.link_checks else [],
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in evidence
        ],
        "invoices": [
            {
                "id": invoice.id,
                "paypal_invoice_id": invoice.paypal_invoice_id,
                "status": invoice.status,
                "amount_cents": invoice.amount_cents,
                "currency": invoice.currency,
                "payer_view_url": invoice.paypal_invoice_url,
            }
            for invoice in invoices
        ],
        "payment_readiness": calculate_payment_readiness(db, milestone),
    }


def _agreement_summary(db: Session, agreement: Agreement) -> dict[str, Any]:
    return {
        "id": agreement.id,
        "title": agreement.title,
        "description": agreement.description,
        "status": agreement.status,
        "total_amount_cents": agreement.total_amount_cents,
        "currency": agreement.currency,
        "client_org_id": agreement.client_org_id,
        "provider_org_id": agreement.provider_org_id,
        "created_at": agreement.created_at.isoformat() if agreement.created_at else None,
        "milestones": [
            _milestone_summary(db, milestone)
            for milestone in sorted(agreement.milestones, key=lambda item: item.order)
        ],
    }


def _intent_data(result: AgentResult) -> dict[str, Any]:
    return result.data


@client_router.post("/intents/parse")
def parse_intent(
    request: ParseIntentRequest,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    provider: CompletionProvider = Depends(get_completion_provider),
) -> dict[str, Any]:
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only a client can parse an intent.")
    try:
        result = IntentAgent(
            provider,
            model=settings.GROQ_INTENT_MODEL,
            max_completion_tokens=settings.GROQ_INTENT_MAX_COMPLETION_TOKENS,
            reasoning_effort=settings.GROQ_REASONING_EFFORT,
        ).parse(request.request)
    except GroqRateLimitError as exc:
        logger.warning("intent_parse_rate_limited")
        raise HTTPException(
            status_code=429,
            detail="The AI service is busy. Please retry in a moment.",
        ) from exc
    except (ValueError, RuntimeError) as exc:
        logger.warning("intent_parse_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Intent parsing failed.") from exc
    return _intent_data(result)


@client_router.post("/agreements", status_code=201)
def create_agreement(
    request: CreateAgreementRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Only a client can create an agreement.")
    provider = (
        db.query(User)
        .filter(User.role == "provider")
        .order_by(User.created_at.asc(), User.id.asc())
        .first()
    )
    if provider is None:
        raise HTTPException(status_code=409, detail="No demo provider is seeded.")

    intent = request.intent
    total = sum(milestone.amount_cents for milestone in intent.milestones)
    if total != intent.budget_cents:
        raise HTTPException(
            status_code=422,
            detail="Milestone amounts must sum exactly to the agreement budget.",
        )
    if intent.currency.upper() != "USD":
        raise HTTPException(status_code=422, detail="The demo supports USD agreements only.")

    agreement = Agreement(
        id=str(uuid4()),
        title=intent.project_type,
        description=json.dumps(
            {
                "requirements": intent.requirements,
                "deadline": intent.deadline,
                "missing_information": intent.missing_information,
            },
            separators=(",", ":"),
        ),
        status=AgreementStatus.DRAFT.value,
        total_amount_cents=intent.budget_cents,
        currency=intent.currency.upper(),
        client_org_id=user.organization_id,
        provider_org_id=provider.organization_id,
        created_by=user.id,
    )
    db.add(agreement)
    db.flush()
    for order, item in enumerate(intent.milestones, start=1):
        milestone = Milestone(
            id=str(uuid4()),
            agreement_id=agreement.id,
            title=item.title,
            description="; ".join(item.deliverables),
            order=order,
            status=MilestoneStatus.PENDING.value,
            amount_cents=item.amount_cents,
        )
        db.add(milestone)
        db.flush()
        db.add_all(
            [
                AcceptanceCriterion(
                    id=str(uuid4()),
                    milestone_id=milestone.id,
                    description=criterion,
                )
                for criterion in item.acceptance_criteria
            ]
        )
    _record_audit(
        db,
        agreement,
        "agreement_created",
        user=user,
        entity_type="agreement",
        entity_id=agreement.id,
        details={"total_amount_cents": agreement.total_amount_cents},
    )
    db.commit()
    db.refresh(agreement)
    return _agreement_summary(db, agreement)


@client_router.post("/agreements/{agreement_id}/publish")
def publish_agreement(
    agreement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="client")
    milestone_guards = [
        {
            "title": milestone.title,
            "amount_cents": milestone.amount_cents,
            "criteria_count": len(milestone.criteria),
            "status": milestone.status,
        }
        for milestone in agreement.milestones
    ]
    try:
        validate_agreement_transition(
            AgreementStatus(agreement.status),
            AgreementStatus.PROPOSED,
            user_role=user.role,
            milestones=milestone_guards,
            total_amount_cents=agreement.total_amount_cents,
        )
    except (InvalidTransitionError, RoleError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    agreement.status = AgreementStatus.PROPOSED.value
    _record_audit(
        db, agreement, "agreement_published", user=user,
        entity_type="agreement", entity_id=agreement.id,
    )
    db.commit()
    db.refresh(agreement)
    return _agreement_summary(db, agreement)


@client_router.get("/agreements")
def list_client_agreements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    if user.role != "client":
        raise HTTPException(status_code=403, detail="Client role is required.")
    agreements = (
        db.query(Agreement)
        .filter(Agreement.client_org_id == user.organization_id)
        .order_by(Agreement.created_at.desc())
        .all()
    )
    return [_agreement_summary(db, agreement) for agreement in agreements]


@client_router.get("/agreements/{agreement_id}")
def get_client_agreement(
    agreement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="client")
    return _agreement_summary(db, agreement)


@client_router.post("/agreements/{agreement_id}/milestones/{milestone_id}/approve")
def approve_milestone(
    agreement_id: str,
    milestone_id: str,
    request: ApprovalDecision = Body(default=ApprovalDecision()),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="client")
    milestone = _milestone_for_agreement(db, agreement, milestone_id)
    readiness = calculate_payment_readiness(db, milestone)
    if not readiness["client_approval_allowed"]:
        reasons = " ".join(readiness["blocking_reasons"])
        raise HTTPException(
            status_code=409,
            detail=reasons or "Evidence must be submitted for client review before approval.",
        )
    unverified_criteria = readiness["criteria_summary"]["criteria"]
    unverified_criteria = [
        item
        for item in unverified_criteria
        if item["status"] != "verified"
    ]
    advisory_verdict = readiness["advisory_verdict"]
    acknowledgement_required = (
        advisory_verdict != "sufficient" or bool(unverified_criteria)
    )
    if acknowledgement_required and not request.acknowledge_unverified:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Client acknowledgement is required because the AI advisory "
                    "is not sufficient or some criteria are unverified."
                ),
                "advisory_verdict": advisory_verdict,
                "unverified_criteria": unverified_criteria,
                "acknowledge_unverified_required": True,
            },
        )

    approved_at = datetime.now(timezone.utc)
    _transition_milestone(
        milestone,
        MilestoneStatus.APPROVED,
        role=user.role,
    )
    approval = Approval(
        id=str(uuid4()),
        milestone_id=milestone.id,
        approved_by=user.id,
        decision="approved",
        notes=json.dumps(
            {
                "acknowledged_unverified": acknowledgement_required,
                "unverified_criteria": unverified_criteria,
                "advisory_verdict": advisory_verdict,
                "approved_at": approved_at.isoformat(),
            },
            ensure_ascii=True,
            separators=(",", ":"),
        ),
        created_at=approved_at,
    )
    db.add(approval)
    db.flush()
    readiness = calculate_payment_readiness(db, milestone)
    if readiness["status"] == "READY_FOR_PAYMENT":
        _record_audit(
            db,
            agreement,
            "payment_unlocked",
            user=user,
            entity_type="milestone",
            entity_id=milestone.id,
            details={"actor": "CLIENT", "readiness_status": readiness["status"]},
        )
    _record_audit(
        db, agreement, "milestone_approved", user=user,
        entity_type="milestone", entity_id=milestone.id,
    )
    if acknowledgement_required:
        _record_audit(
            db,
            agreement,
            "milestone_approved_with_unverified_criteria",
            user=user,
            entity_type="milestone",
            entity_id=milestone.id,
            details={
                "unverified_criteria": unverified_criteria,
                "advisory_verdict": advisory_verdict,
                "user_id": user.id,
                "approved_at": approved_at.isoformat(),
            },
        )
    db.commit()
    db.refresh(milestone)
    return _milestone_summary(db, milestone)


@client_router.post("/agreements/{agreement_id}/milestones/{milestone_id}/revision")
def request_milestone_revision(
    agreement_id: str,
    milestone_id: str,
    request: DecisionNotes,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="client")
    milestone = _milestone_for_agreement(db, agreement, milestone_id)
    _transition_milestone(
        milestone,
        MilestoneStatus.REVISION_REQUESTED,
        role=user.role,
    )
    db.add(
        Approval(
            id=str(uuid4()),
            milestone_id=milestone.id,
            approved_by=user.id,
            decision="rejected",
            notes=request.notes,
            created_at=datetime.now(timezone.utc),
        )
    )
    _record_audit(
        db, agreement, "milestone_revision_requested", user=user,
        entity_type="milestone", entity_id=milestone.id,
        details={"notes": request.notes},
    )
    db.commit()
    db.refresh(milestone)
    return _milestone_summary(db, milestone)


@provider_router.get("/agreements")
def list_provider_agreements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    if user.role != "provider":
        raise HTTPException(status_code=403, detail="Provider role is required.")
    agreements = (
        db.query(Agreement)
        .filter(Agreement.provider_org_id == user.organization_id)
        .order_by(Agreement.created_at.desc())
        .all()
    )
    return [_agreement_summary(db, agreement) for agreement in agreements]


@provider_router.get("/agreements/{agreement_id}")
def get_provider_agreement(
    agreement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="provider")
    return _agreement_summary(db, agreement)


@provider_router.post("/agreements/{agreement_id}/accept")
def accept_agreement(
    agreement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="provider")
    try:
        validate_agreement_transition(
            AgreementStatus(agreement.status),
            AgreementStatus.ACTIVE,
            user_role=user.role,
        )
    except (InvalidTransitionError, RoleError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    agreement.status = AgreementStatus.ACTIVE.value
    _record_audit(
        db, agreement, "agreement_accepted", user=user,
        entity_type="agreement", entity_id=agreement.id,
    )
    db.commit()
    db.refresh(agreement)
    return _agreement_summary(db, agreement)


@provider_router.post("/agreements/{agreement_id}/refuse")
def refuse_agreement(
    agreement_id: str,
    request: DecisionNotes,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="provider")
    try:
        validate_agreement_transition(
            AgreementStatus(agreement.status),
            AgreementStatus.REJECTED,
            user_role=user.role,
        )
    except (InvalidTransitionError, RoleError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    agreement.status = AgreementStatus.REJECTED.value
    _record_audit(
        db, agreement, "agreement_refused", user=user,
        entity_type="agreement", entity_id=agreement.id,
        details={"notes": request.notes},
    )
    db.commit()
    db.refresh(agreement)
    return _agreement_summary(db, agreement)


@provider_router.post("/agreements/{agreement_id}/milestones/{milestone_id}/start")
def start_milestone(
    agreement_id: str,
    milestone_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="provider")
    if agreement.status != AgreementStatus.ACTIVE.value:
        raise HTTPException(status_code=409, detail="Agreement must be active.")
    milestone = _milestone_for_agreement(db, agreement, milestone_id)
    previous = (
        db.query(Milestone)
        .filter(
            Milestone.agreement_id == agreement.id,
            Milestone.order < milestone.order,
        )
        .order_by(Milestone.order.desc())
        .first()
    )
    _transition_milestone(
        milestone,
        MilestoneStatus.IN_PROGRESS,
        role=user.role,
        previous_status=previous.status if previous else None,
    )
    _record_audit(
        db, agreement, "milestone_started", user=user,
        entity_type="milestone", entity_id=milestone.id,
    )
    db.commit()
    db.refresh(milestone)
    return _milestone_summary(db, milestone)


@provider_router.post("/agreements/{agreement_id}/milestones/{milestone_id}/evidence")
async def submit_evidence(
    agreement_id: str,
    milestone_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    provider: CompletionProvider = Depends(get_completion_provider),
    fact_checker: EvidenceFactChecker = Depends(get_evidence_fact_checker),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="provider")
    milestone = _milestone_for_agreement(db, agreement, milestone_id)
    if milestone.status != MilestoneStatus.IN_PROGRESS.value:
        raise HTTPException(status_code=409, detail="Milestone must be in progress.")
    content_type = request.headers.get("content-type", "").casefold()
    prepared_attachments: list[dict[str, Any]] = []
    try:
        if content_type.startswith("application/json"):
            submission = EvidenceSubmission.model_validate(await request.json())
        elif content_type.startswith("multipart/form-data"):
            async with request.form(
                max_files=MAX_EVIDENCE_FILES + 1,
                max_fields=40,
                max_part_size=32768,
            ) as form:
                form_links = [
                    line.strip()
                    for value in form.getlist("links")
                    if isinstance(value, str)
                    for line in value.splitlines()
                    if line.strip()
                ]
                submission = EvidenceSubmission.model_validate(
                    {
                        "text": form.get("text", ""),
                        "links": form_links,
                        "criterion_ids": [
                            value
                            for value in form.getlist("criterion_ids")
                            if isinstance(value, str)
                        ],
                    }
                )
                uploads = [
                    value
                    for value in form.getlist("files")
                    if isinstance(value, StarletteUploadFile)
                    and bool(value.filename)
                ]
                if len(uploads) > MAX_EVIDENCE_FILES:
                    raise HTTPException(status_code=413, detail="Attach no more than 5 files.")
                total_file_bytes = 0
                for upload in uploads:
                    if upload.size is not None and upload.size > MAX_EVIDENCE_FILE_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail="Each attachment must be 10 MB or smaller.",
                        )
                    data = await upload.read(MAX_EVIDENCE_FILE_BYTES + 1)
                    total_file_bytes += len(data)
                    if total_file_bytes > MAX_EVIDENCE_TOTAL_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail="Attachments must total 20 MB or less.",
                        )
                    prepared_attachments.append(
                        validate_evidence_file(
                            upload.filename or "",
                            upload.content_type,
                            data,
                        )
                    )
        else:
            raise HTTPException(
                status_code=415,
                detail="Submit evidence as JSON or multipart form data.",
            )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_input=False),
        ) from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Evidence submission is invalid.") from exc

    content = submission.text.strip()
    links = [str(link) for link in submission.links]
    criterion_ids = list(dict.fromkeys(submission.criterion_ids))
    if not content:
        raise HTTPException(
            status_code=422,
            detail="An evidence description is required.",
        )
    milestone_criterion_ids = {criterion.id for criterion in milestone.criteria}
    if any(item not in milestone_criterion_ids for item in criterion_ids):
        raise HTTPException(
            status_code=422,
            detail="Selected acceptance criteria must belong to this milestone.",
        )
    attachment_metadata = [
        {key: value for key, value in item.items() if key != "_data"}
        for item in prepared_attachments
    ]
    link_checks = fact_checker.check_links(links)
    criteria = [criterion.description for criterion in milestone.criteria]
    evidence_agent = EvidenceAgent(
        provider,
        model=settings.GROQ_EVIDENCE_MODEL,
        fallback_model=settings.GROQ_EVIDENCE_FALLBACK_MODEL,
        max_completion_tokens=settings.GROQ_EVIDENCE_MAX_COMPLETION_TOKENS,
        reasoning_effort=settings.GROQ_REASONING_EFFORT,
    )
    evidence_content = json.dumps(
        {
            "text": content,
            "links": links,
            "criterion_ids": criterion_ids,
            "attachments": attachment_metadata,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    try:
        assessment = evidence_agent.assess(
            criteria,
            evidence_content,
            trusted_facts=link_checks,
            uninspected_attachments=attachment_metadata,
            non_text_evidence_only=not content and bool(links or prepared_attachments),
            has_external_links=bool(links),
        )
    except GroqRateLimitError as exc:
        logger.warning("evidence_assessment_rate_limited")
        raise HTTPException(
            status_code=429,
            detail="The AI service is busy. Please retry in a moment.",
        ) from exc
    except RuntimeError as exc:
        logger.warning("evidence_assessment_failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Evidence assessment failed.") from exc

    image_attachments = [
        item
        for item in prepared_attachments
        if item.get("content_type") in {"image/png", "image/jpeg"}
    ]
    image_inputs, skipped_images = prepare_images_for_analysis(prepared_attachments)
    image_analysis: dict[str, Any] | None = None
    image_status_by_id: dict[str, str] = {}
    if attachment_metadata:
        image_results: list[dict[str, Any]] = []
        is_mock = settings.DEMO_MODE == "mock"
        image_analysis_enabled = (
            settings.EVIDENCE_IMAGE_ANALYSIS
            if settings.EVIDENCE_IMAGE_ANALYSIS is not None
            else settings.DEMO_MODE != "mock"
        )
        if not image_attachments:
            image_status = "not_analyzed"
            message = "No PNG/JPEG images were attached; other file types were not inspected."
        elif not image_inputs:
            image_status = "not_analyzed"
            message = "Image decoding failed; image not analyzed."
        elif is_mock:
            image_status = "mock"
            message = (
                "Mock mode canned analysis only; image pixels were not analyzed "
                "and this is not a real visual assessment."
            )
            image_results = [
                {
                    "criterion": criterion,
                    "status": "cannot_tell",
                    "observation": "Mock mode canned output; image pixels were not analyzed.",
                    "missing_element": "Real visual inspection is unavailable in mock mode.",
                }
                for criterion in criteria
            ]
            for image in image_inputs:
                image_status_by_id[image["id"]] = "mock_canned"
        elif not image_analysis_enabled:
            image_status = "not_analyzed"
            message = "Image analysis is disabled by EVIDENCE_IMAGE_ANALYSIS."
        elif image_inputs:
            try:
                image_results = evidence_agent.analyze_images(criteria, image_inputs)[
                    "criteria_results"
                ]
                image_status = "analyzed"
                message = (
                    "Visual observations are advisory only; they do not prove "
                    "authenticity or functionality. Linked page contents are not inspected."
                )
                for image in image_inputs:
                    image_status_by_id[image["id"]] = "analyzed"
                assessment.data["report"] = assessment.data["report"].replace(
                    "uploaded file contents, including images and PDFs",
                    "PDF contents or unsupported files",
                ).replace(
                    "uploaded file contents",
                    "PDF contents or unsupported files",
                )
            except (GroqAPIError, RuntimeError, ValueError, TypeError, KeyError) as exc:
                image_status = "not_analyzed"
                message = (
                    "Image analysis failed; the text-only advisory is shown instead. "
                    "Image not analyzed."
                )
                logger.warning(
                    "evidence_image_analysis_failed error_type=%s status_code=%s",
                    type(exc).__name__,
                    getattr(exc, "status_code", None) or "none",
                )
        else:
            image_status = "not_analyzed"
            message = "No supported PNG/JPEG image could be analyzed. Image not analyzed."

        attachment_results: list[dict[str, str]] = []
        for item in prepared_attachments:
            attachment_id = str(item.get("id", ""))
            current_status = image_status_by_id.get(attachment_id)
            if current_status is None:
                skipped = next(
                    (entry for entry in skipped_images if entry["id"] == attachment_id),
                    None,
                )
                current_status = "not_analyzed"
                attachment_message = (
                    skipped["message"]
                    if skipped
                    else "Only PNG/JPEG images are analyzed; this attachment was not inspected."
                )
            elif current_status == "mock_canned":
                attachment_message = "Mock canned analysis; image pixels were not inspected."
            elif current_status == "analyzed":
                attachment_message = "Image pixels were visually analyzed for advisory observations."
            else:
                attachment_message = message
            item["inspection_status"] = current_status
            attachment_results.append(
                {
                    "id": attachment_id,
                    "name": str(item.get("name", "attachment")),
                    "content_type": str(item.get("content_type", "application/octet-stream")),
                    "status": current_status,
                    "message": attachment_message,
                }
            )
        image_analysis = {
            "status": image_status,
            "message": message,
            "attachments": attachment_results,
            "criteria_results": image_results,
        }
        for item in attachment_metadata:
            item["inspection_status"] = image_status_by_id.get(
                str(item.get("id", "")), "not_analyzed"
            )

    evidence_content = json.dumps(
        {
            "text": content,
            "links": links,
            "criterion_ids": criterion_ids,
            "attachments": attachment_metadata,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    if image_analysis is not None:
        assessment.data["image_analysis"] = image_analysis

    evidence_id = str(uuid4())
    try:
        stored_file_path = store_evidence_files(
            settings.MEDIA_DIR,
            evidence_id,
            prepared_attachments,
        )
    except OSError as exc:
        logger.error("evidence_storage_failed error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Attachments could not be stored securely. Please retry.",
        ) from exc

    evidence = Evidence(
        id=evidence_id,
        milestone_id=milestone.id,
        submitted_by=user.id,
        evidence_type="submission",
        content=evidence_content,
        file_path=stored_file_path,
        ai_report=json.dumps(assessment.data, ensure_ascii=False, separators=(",", ":")),
        link_checks=json.dumps(
            link_checks,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )
    db.add(evidence)
    _record_audit(
        db,
        agreement,
        "evidence_submitted",
        user=user,
        entity_type="milestone",
        entity_id=milestone.id,
        details={
            "evidence_id": evidence.id,
            "criterion_ids": criterion_ids,
            "attachment_count": len(attachment_metadata),
        },
    )
    _record_audit(
        db,
        agreement,
        "ai_advisory_generated",
        user=None,
        entity_type="milestone",
        entity_id=milestone.id,
        details={
            "evidence_id": evidence.id,
            "verdict": assessment.data["overall_verdict"],
            "advisory_only": True,
        },
    )
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        if stored_file_path:
            try:
                remove_evidence_files(settings.MEDIA_DIR, evidence_id)
            except OSError as cleanup_error:
                logger.error(
                    "evidence_storage_cleanup_failed error_type=%s",
                    type(cleanup_error).__name__,
                )
        logger.error("evidence_save_failed error_type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Evidence could not be saved. Please retry.",
        ) from exc
    db.refresh(evidence)
    return {
        "evidence_id": evidence.id,
        "milestone_id": milestone.id,
        "submission_status": "SUBMITTED",
        "verification_status": "ADVISORY",
        "attachments": attachment_metadata,
        "ai_report": assessment.data,
        "link_checks": link_checks,
        "milestone_status": milestone.status,
    }


@provider_router.post("/agreements/{agreement_id}/milestones/{milestone_id}/submit")
def submit_milestone_for_review(
    agreement_id: str,
    milestone_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    agreement = _agreement_for_member(db, agreement_id, user, required_role="provider")
    milestone = _milestone_for_agreement(db, agreement, milestone_id)
    evidence_count = (
        db.query(Evidence)
        .filter(Evidence.milestone_id == milestone.id)
        .count()
    )
    _transition_milestone(
        milestone,
        MilestoneStatus.IN_REVIEW,
        role=user.role,
        evidence_count=evidence_count,
    )
    _record_audit(
        db, agreement, "milestone_submitted_for_review", user=user,
        entity_type="milestone", entity_id=milestone.id,
        details={"evidence_count": evidence_count},
    )
    db.commit()
    db.refresh(milestone)
    return _milestone_summary(db, milestone)


@router.get("/agreements/{agreement_id}/audit-logs")
def get_agreement_audit_logs(
    agreement_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    agreement = _agreement_for_member(db, agreement_id, user)
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.agreement_id == agreement.id)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        .all()
    )
    return [
        {
            "id": item.id,
            "user_id": item.user_id,
            "action": item.action,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "details": json.loads(item.details) if item.details else {},
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in rows
    ]


@router.post("/demo/seed")
def seed_demo(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    seed_token: str | None = Header(default=None, alias="X-Demo-Seed-Token"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> dict[str, Any]:
    token_authorized = bool(
        settings.DEMO_SEED_TOKEN
        and seed_token
        and hmac.compare_digest(seed_token, settings.DEMO_SEED_TOKEN)
    )
    demo_client = db.get(User, x_user_id) if x_user_id else None
    demo_client_authorized = bool(
        demo_client
        and demo_client.id == "demo-client"
        and demo_client.role == "client"
        and demo_client.organization_id == "demo-client-org"
    )
    mock_mode = settings.DEMO_MODE == "mock"
    if not token_authorized and not demo_client_authorized and not (
        mock_mode and not settings.DEMO_SEED_TOKEN
    ):
        if not settings.DEMO_SEED_TOKEN:
            raise HTTPException(status_code=503, detail="Demo seed token is not configured.")
        raise HTTPException(status_code=401, detail="Valid demo seed token is required.")
    if not settings.DEMO_CLIENT_PAYPAL_EMAIL.strip() and not mock_mode:
        raise HTTPException(status_code=503, detail="Demo client PayPal email is not configured.")

    demo_agreement_ids = db.query(Agreement.id).filter(
        (Agreement.client_org_id == "demo-client-org")
        | (Agreement.provider_org_id == "demo-provider-org")
    )
    demo_milestone_ids = db.query(Milestone.id).filter(
        Milestone.agreement_id.in_(demo_agreement_ids)
    )
    uploaded_demo_evidence_ids = [
        item.id
        for item in db.query(Evidence)
        .filter(Evidence.milestone_id.in_(demo_milestone_ids))
        .filter(Evidence.file_path.is_not(None))
        .all()
    ]
    db.query(WebhookEvent).filter(
        WebhookEvent.resource_id.in_(
            db.query(Invoice.paypal_invoice_id).filter(
                Invoice.milestone_id.in_(demo_milestone_ids)
            )
        )
    ).delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.agreement_id.in_(demo_agreement_ids)).delete(
        synchronize_session=False
    )
    db.query(Invoice).filter(Invoice.milestone_id.in_(demo_milestone_ids)).delete(
        synchronize_session=False
    )
    db.query(Approval).filter(Approval.milestone_id.in_(demo_milestone_ids)).delete(
        synchronize_session=False
    )
    db.query(Evidence).filter(Evidence.milestone_id.in_(demo_milestone_ids)).delete(
        synchronize_session=False
    )
    db.query(AcceptanceCriterion).filter(
        AcceptanceCriterion.milestone_id.in_(demo_milestone_ids)
    ).delete(synchronize_session=False)
    db.query(Milestone).filter(Milestone.agreement_id.in_(demo_agreement_ids)).delete(
        synchronize_session=False
    )
    db.query(Agreement).filter(
        (Agreement.client_org_id == "demo-client-org")
        | (Agreement.provider_org_id == "demo-provider-org")
    ).delete(synchronize_session=False)
    db.query(User).filter(User.organization_id.in_(
        ["demo-client-org", "demo-provider-org"]
    )).delete(synchronize_session=False)
    db.query(Organization).filter(
        Organization.id.in_(["demo-client-org", "demo-provider-org"])
    ).delete(synchronize_session=False)
    db.flush()
    db.expunge_all()

    client_org = Organization(id="demo-client-org", name="ShopFlow Inc")
    provider_org = Organization(id="demo-provider-org", name="DevStudio Agency")
    db.add_all([client_org, provider_org])
    db.flush()
    client_user = User(
        id="demo-client",
        name="Demo Client",
        email=(
            settings.DEMO_CLIENT_PAYPAL_EMAIL.strip()
            or "mock-client@orchestra.local"
        ),
        role="client",
        organization_id=client_org.id,
    )
    provider_user = User(
        id="demo-provider",
        name="Demo Provider",
        email="demo-provider@orchestra.local",
        role="provider",
        organization_id=provider_org.id,
    )
    db.add_all([client_user, provider_user])
    db.flush()

    agreement = Agreement(
        id=str(uuid4()),
        title="E-commerce website",
        description="Seeded $600 Phase 4 demo scenario.",
        status=AgreementStatus.DRAFT.value,
        total_amount_cents=60000,
        currency="USD",
        client_org_id=client_org.id,
        provider_org_id=provider_org.id,
        created_by=client_user.id,
    )
    db.add(agreement)
    db.flush()
    demo_milestones = (
        (
            "Design",
            15000,
            [
                "Mockups for Home, Catalog, Product, Cart, and Account pages",
                "Style guide",
            ],
            [
                "Mockups for the Home, Catalog, Product, Cart, and Account pages are included in the submitted files.",
                "A style guide is included in the submitted files.",
            ],
        ),
        (
            "Development",
            35000,
            ["Responsive website deployed to public staging"],
            [
                "A public HTTPS staging URL is provided and returns HTTP 2xx.",
                "The staging layout is responsive at mobile (375 px) and desktop (1280 px) widths.",
            ],
        ),
        (
            "Final Handover",
            10000,
            ["Project documentation and source repository"],
            [
                "A project documentation file is included in the handover package.",
                "A source repository URL is provided and returns HTTP 2xx.",
            ],
        ),
    )
    for order, (title, amount, deliverables, criteria) in enumerate(demo_milestones, 1):
        milestone = Milestone(
            id=f"demo-milestone-{order}",
            agreement_id=agreement.id,
            title=title,
            description="; ".join(deliverables),
            order=order,
            status=MilestoneStatus.PENDING.value,
            amount_cents=amount,
        )
        db.add(milestone)
        db.flush()
        db.add_all(
            [
                AcceptanceCriterion(
                    id=str(uuid4()),
                    milestone_id=milestone.id,
                    description=criterion,
                )
                for criterion in criteria
            ]
        )
    validate_agreement_transition(
        AgreementStatus.DRAFT,
        AgreementStatus.PROPOSED,
        user_role="client",
        milestones=[
            {"title": title, "amount_cents": amount, "criteria_count": len(criteria)}
            for title, amount, _, criteria in demo_milestones
        ],
        total_amount_cents=60000,
    )
    agreement.status = AgreementStatus.PROPOSED.value
    _record_audit(
        db,
        agreement,
        "demo_seeded",
        user=client_user,
        entity_type="agreement",
        entity_id=agreement.id,
        details={"scenario": "e-commerce", "total_amount_cents": 60000},
    )
    db.commit()
    for evidence_id in uploaded_demo_evidence_ids:
        try:
            remove_evidence_files(settings.MEDIA_DIR, evidence_id)
        except OSError as exc:
            logger.error(
                "demo_evidence_cleanup_failed error_type=%s",
                type(exc).__name__,
            )
    return {
        "status": "seeded",
        "client_user_id": client_user.id,
        "provider_user_id": provider_user.id,
        "agreement_id": agreement.id,
        "milestone_ids": [f"demo-milestone-{index}" for index in range(1, 4)],
    }

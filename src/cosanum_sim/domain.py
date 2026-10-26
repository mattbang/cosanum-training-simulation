"""Typed synthetic inputs, phase work and request outcomes."""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Topic:
    topic_id: str
    priority: int
    theory_required: bool
    practice_required: bool
    theory_group_possible: bool
    practice_group_possible: bool
    open_records: int


@dataclass(frozen=True)
class Request:
    request_id: str
    person_id: str
    topic_id: str
    noticed_at: float
    arrival_event_id: str
    batch_id: str
    cycle_id: str = "synthetic-cycle-1"
    cohort_id: str = "synthetic-demonstration"
    phase: str = "theory"
    synthetic: bool = True
    case_kind: str = "training_needed"
    need_arises_at: Optional[float] = None
    baseline_delivery: Optional[str] = None


@dataclass(frozen=True)
class Resource:
    resource_id: str
    role: str
    topic_ids: Tuple[str, ...]
    intervals: Tuple[Tuple[float, float], ...]
    phases: Tuple[str, ...] = ("theory", "practice", "proof")


@dataclass(frozen=True)
class Session:
    session_id: str
    topic_id: str
    phase: str
    request_ids: Tuple[str, ...]
    person_ids: Tuple[str, ...]
    reason: str
    release_at: float
    reservation_at: float
    start: float
    end: float
    trainer_id: str
    room_id: str
    preparation_start: Optional[float] = None
    work_end: Optional[float] = None
    cancelled_at: Optional[float] = None
    work_item_ids: Tuple[str, ...] = ()


@dataclass
class Outcome:
    request: Request
    deadline_at: Optional[float]
    state: str = "not_arrived"
    first_start: Optional[float] = None
    phase_completed_at: Optional[float] = None
    planned_start: Optional[float] = None
    session_id: Optional[str] = None
    escalated: bool = False
    training_completed_at: Optional[float] = None
    proof_completed_at: Optional[float] = None
    proof_due_at: Optional[float] = None


@dataclass
class WorkItem:
    work_item_id: str
    request: Request
    phase: str
    ready_at: float
    deadline_at: Optional[float]
    state: str = 'waiting'
    attempt: int = 0
    session_id: Optional[str] = None
    first_start: Optional[float] = None
    completed_at: Optional[float] = None
    planned_start: Optional[float] = None
    review_count: int = 0
    urgent_release: bool = False
    eligible_at: float = 0
    learning_fallback: bool = False
    prerequisite_session_id: Optional[str] = None
    learning_attempt: int = 1

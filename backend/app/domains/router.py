from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Domain
from app.schemas import DomainCreate, DomainOut, MonitoringToggle
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/domains", tags=["domains"])


@router.post("", response_model=DomainOut, status_code=status.HTTP_201_CREATED)
def create_domain(
    payload: DomainCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Prevent the same user from adding a duplicate domain
    existing = (
        db.query(Domain)
        .filter(Domain.owner_id == current_user.id, Domain.url == payload.url)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Domain already added")

    domain = Domain(url=payload.url, owner_id=current_user.id)
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


@router.get("", response_model=list[DomainOut])
def list_domains(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Domain)
        .filter(Domain.owner_id == current_user.id)
        .order_by(Domain.created_at.desc())
        .all()
    )


@router.get("/{domain_id}", response_model=DomainOut)
def get_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = (
        db.query(Domain)
        .filter(Domain.id == domain_id, Domain.owner_id == current_user.id)
        .first()
    )
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = (
        db.query(Domain)
        .filter(Domain.id == domain_id, Domain.owner_id == current_user.id)
        .first()
    )
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    db.delete(domain)
    db.commit()
    return None

@router.patch("/{domain_id}/monitoring", response_model=DomainOut)
def toggle_monitoring(
    domain_id: int,
    payload: MonitoringToggle,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    domain = (
        db.query(Domain)
        .filter(Domain.id == domain_id, Domain.owner_id == current_user.id)
        .first()
    )
    if domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    domain.monitoring_enabled = payload.enabled
    db.commit()
    db.refresh(domain)
    return domain
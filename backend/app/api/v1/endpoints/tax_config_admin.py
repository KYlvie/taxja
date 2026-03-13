"""Admin endpoints for tax configuration management.

Allows CRUD operations on yearly tax configurations so new years
can be added without code changes.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.tax_configuration import TaxConfiguration

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TaxBracket(BaseModel):
    lower: float
    upper: Optional[float] = None
    rate: float


class VATRates(BaseModel):
    standard: float = 0.20
    residential: float = 0.10
    small_business_threshold: float = 55000.00
    tolerance_threshold: float = 60500.00


class SVSRates(BaseModel):
    pension: float = 0.185
    health: float = 0.068
    accident_fixed: float = 12.95
    supplementary_pension: float = 0.0153
    gsvg_min_base_monthly: float = 551.10
    gsvg_min_income_yearly: float = 6613.20
    neue_min_monthly: float = 160.81
    max_base_monthly: float = 8085.00


class SelfEmployedConfig(BaseModel):
    grundfreibetrag_profit_limit: float = 33000.00
    grundfreibetrag_rate: float = 0.15
    grundfreibetrag_max: float = 4950.00
    max_total_freibetrag: float = 46400.00
    flat_rate_turnover_limit: float = 320000.00
    flat_rate_general: float = 0.135
    flat_rate_consulting: float = 0.06
    kleinunternehmer_threshold: float = 55000.00
    kleinunternehmer_tolerance: float = 60500.00
    ust_voranmeldung_monthly_threshold: float = 100000.00


class DeductionConfig(BaseModel):
    home_office: float = 300.00
    child_deduction_monthly: float = 58.40
    single_parent_deduction: float = 494.00
    commuting_brackets: Optional[dict] = None
    pendler_euro_per_km: float = 6.00
    basic_exemption_rate: float = 0.15
    basic_exemption_max: float = 4950.00
    self_employed: Optional[SelfEmployedConfig] = None


class TaxConfigCreate(BaseModel):
    """Schema for creating/updating a tax year configuration."""
    tax_year: int = Field(..., ge=2020, le=2099)
    tax_brackets: List[TaxBracket]
    exemption_amount: float
    vat_rates: VATRates
    svs_rates: SVSRates
    deduction_config: DeductionConfig


class TaxConfigResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    tax_year: int
    tax_brackets: list
    exemption_amount: float
    vat_rates: dict
    svs_rates: dict
    deduction_config: dict
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SupportedYearsResponse(BaseModel):
    years: List[int]
    default_year: int


# ---------------------------------------------------------------------------
# Public endpoint — no auth required
# ---------------------------------------------------------------------------

@router.get("/supported-years", response_model=SupportedYearsResponse)
def get_supported_years(db: Session = Depends(get_db)):
    """Return the list of tax years that have configurations in the database."""
    rows = (
        db.query(TaxConfiguration.tax_year)
        .order_by(TaxConfiguration.tax_year.desc())
        .all()
    )
    years = [r[0] for r in rows]
    default_year = years[0] if years else 2026
    return SupportedYearsResponse(years=sorted(years), default_year=default_year)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[TaxConfigResponse])
def list_tax_configs(db: Session = Depends(get_db)):
    """List all tax year configurations."""
    configs = (
        db.query(TaxConfiguration)
        .order_by(TaxConfiguration.tax_year.desc())
        .all()
    )
    return [_to_response(c) for c in configs]


@router.get("/{tax_year}", response_model=TaxConfigResponse)
def get_tax_config(tax_year: int, db: Session = Depends(get_db)):
    """Get a specific tax year configuration."""
    config = db.query(TaxConfiguration).filter(
        TaxConfiguration.tax_year == tax_year
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"No config for year {tax_year}")
    return _to_response(config)


@router.post("/", response_model=TaxConfigResponse, status_code=201)
def create_tax_config(payload: TaxConfigCreate, db: Session = Depends(get_db)):
    """Create a new tax year configuration."""
    existing = db.query(TaxConfiguration).filter(
        TaxConfiguration.tax_year == payload.tax_year
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Config for year {payload.tax_year} already exists. Use PUT to update.",
        )

    config = TaxConfiguration(
        tax_year=payload.tax_year,
        tax_brackets=[b.model_dump() for b in payload.tax_brackets],
        exemption_amount=payload.exemption_amount,
        vat_rates=payload.vat_rates.model_dump(),
        svs_rates=payload.svs_rates.model_dump(),
        deduction_config=payload.deduction_config.model_dump(),
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    logger.info("Created tax config for year %d", payload.tax_year)
    return _to_response(config)


@router.put("/{tax_year}", response_model=TaxConfigResponse)
def update_tax_config(
    tax_year: int, payload: TaxConfigCreate, db: Session = Depends(get_db)
):
    """Update an existing tax year configuration."""
    config = db.query(TaxConfiguration).filter(
        TaxConfiguration.tax_year == tax_year
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"No config for year {tax_year}")

    config.tax_brackets = [b.model_dump() for b in payload.tax_brackets]
    config.exemption_amount = payload.exemption_amount
    config.vat_rates = payload.vat_rates.model_dump()
    config.svs_rates = payload.svs_rates.model_dump()
    config.deduction_config = payload.deduction_config.model_dump()
    db.commit()
    db.refresh(config)
    logger.info("Updated tax config for year %d", tax_year)
    return _to_response(config)


@router.delete("/{tax_year}", status_code=204)
def delete_tax_config(tax_year: int, db: Session = Depends(get_db)):
    """Delete a tax year configuration."""
    config = db.query(TaxConfiguration).filter(
        TaxConfiguration.tax_year == tax_year
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"No config for year {tax_year}")
    db.delete(config)
    db.commit()
    logger.info("Deleted tax config for year %d", tax_year)


@router.post("/{tax_year}/clone", response_model=TaxConfigResponse, status_code=201)
def clone_tax_config(
    tax_year: int,
    target_year: int = Query(..., description="The new year to clone into"),
    db: Session = Depends(get_db),
):
    """Clone an existing year's config to a new year (useful for annual rollover)."""
    source = db.query(TaxConfiguration).filter(
        TaxConfiguration.tax_year == tax_year
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail=f"No config for year {tax_year}")

    existing = db.query(TaxConfiguration).filter(
        TaxConfiguration.tax_year == target_year
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Config for year {target_year} already exists.",
        )

    new_config = TaxConfiguration(
        tax_year=target_year,
        tax_brackets=source.tax_brackets,
        exemption_amount=source.exemption_amount,
        vat_rates=source.vat_rates,
        svs_rates=source.svs_rates,
        deduction_config=source.deduction_config,
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    logger.info("Cloned tax config %d → %d", tax_year, target_year)
    return _to_response(new_config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(config: TaxConfiguration) -> TaxConfigResponse:
    return TaxConfigResponse(
        id=config.id,
        tax_year=config.tax_year,
        tax_brackets=config.tax_brackets,
        exemption_amount=float(config.exemption_amount),
        vat_rates=config.vat_rates,
        svs_rates=config.svs_rates,
        deduction_config=config.deduction_config,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )

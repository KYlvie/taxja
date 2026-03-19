"""Tax configuration model for yearly tax rates"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, Numeric, JSON, DateTime, UniqueConstraint
from app.db.base import Base


class TaxConfiguration(Base):
    """Tax configuration model for storing yearly tax rates and rules"""
    __tablename__ = "tax_configurations"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Tax year (unique)
    tax_year = Column(Integer, unique=True, nullable=False, index=True)
    
    # Income tax configuration
    tax_brackets = Column(JSON, nullable=False)
    # Example structure:
    # [
    #   {"lower": 0, "upper": 13539, "rate": 0.00},
    #   {"lower": 13539, "upper": 21992, "rate": 0.20},
    #   {"lower": 21992, "upper": 36458, "rate": 0.30},
    #   {"lower": 36458, "upper": 70365, "rate": 0.40},
    #   {"lower": 70365, "upper": 104859, "rate": 0.48},
    #   {"lower": 104859, "upper": 1000000, "rate": 0.50},
    #   {"lower": 1000000, "upper": null, "rate": 0.55}
    # ]
    
    # Exemption amount (Freibetrag)
    exemption_amount = Column(Numeric(12, 2), nullable=False)  # e.g., 13539.00 for 2026
    
    # VAT configuration
    vat_rates = Column(JSON, nullable=False)
    # Example structure:
    # {
    #   "standard": 0.20,
    #   "residential": 0.10,
    #   "small_business_threshold": 55000.00,
    #   "tolerance_threshold": 60500.00
    # }
    
    # SVS (social insurance) configuration
    svs_rates = Column(JSON, nullable=False)
    # Steuerjahr 2025 (Veranlagung 2026). Source: SVS/WKO.
    # Percentage rates confirmed by GSVG §§ 27–27a.
    # Fixed amounts (accident, min/max bases) adjusted annually via Aufwertungszahl.
    # Example structure:
    # {
    #   "pension": 0.185,                  # 18.5% Pensionsversicherung
    #   "health": 0.068,                   # 6.8% Krankenversicherung
    #   "accident_fixed": 12.95,           # €12.95/month Unfallversicherung (fixed)
    #   "supplementary_pension": 0.0153,   # 1.53% Selbständigenvorsorge
    #   "gsvg_min_base_monthly": 551.10,   # Mindestbeitragsgrundlage
    #   "gsvg_min_income_yearly": 6613.20, # = 12 × 551.10
    #   "neue_min_monthly": 160.81,        # Neue Selbständige Mindestbeitrag
    #   "max_base_monthly": 8085.00        # Höchstbeitragsgrundlage
    # }
    
    # Deduction configuration
    deduction_config = Column(JSON, nullable=False)
    # Example structure:
    # {
    #   "home_office": 300.00,
    #   "child_deduction_monthly": 58.40,
    #   "single_parent_deduction": 494.00,
    #   "commuting_brackets": {
    #     "small": {
    #       "20": 58.00,
    #       "40": 113.00,
    #       "60": 168.00
    #     },
    #     "large": {
    #       "2": 31.00,
    #       "20": 123.00,
    #       "40": 214.00,
    #       "60": 306.00
    #     }
    #   },
    #   "pendler_euro_per_km": 6.00,
    #   "basic_exemption_rate": 0.15,
    #   "basic_exemption_max": 4950.00
    # }
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<TaxConfiguration(tax_year={self.tax_year}, exemption={self.exemption_amount})>"


def get_2026_tax_config() -> dict:
    """
    Get the official 2026 tax configuration based on USP tables
    
    Returns:
        Dictionary with 2026 tax configuration
    """
    return {
        "tax_year": 2026,
        "tax_brackets": [
            {"lower": 0, "upper": 13539, "rate": 0.00},
            {"lower": 13539, "upper": 21992, "rate": 0.20},
            {"lower": 21992, "upper": 36458, "rate": 0.30},
            {"lower": 36458, "upper": 70365, "rate": 0.40},
            {"lower": 70365, "upper": 104859, "rate": 0.48},
            {"lower": 104859, "upper": 1000000, "rate": 0.50},
            {"lower": 1000000, "upper": None, "rate": 0.55}
        ],
        "exemption_amount": 13539.00,
        "vat_rates": {
            "standard": 0.20,
            "residential": 0.10,
            "small_business_threshold": 55000.00,
            "tolerance_threshold": 60500.00
        },
        # SVS rates – Beitragsjahr 2026 (Veranlagung 2026)
        # Percentage rates: GSVG §§ 27–27a, confirmed by WKO/SVS
        # Fixed amounts: adjusted by Aufwertungszahl 2026 = 1.073
        # Source: WKO, SVS.at, Voice of Vienna
        "svs_rates": {
            "pension": 0.185,                  # 18.5% Pensionsversicherung
            "health": 0.068,                   # 6.8% Krankenversicherung
            "accident_fixed": 12.95,           # €12.95/month Unfallversicherung (WKO 2026)
            "supplementary_pension": 0.0153,   # 1.53% Selbständigenvorsorge (BMSVG)
            "gsvg_min_base_monthly": 551.10,   # Mindestbeitragsgrundlage (= Geringfügigkeitsgrenze)
            "gsvg_min_income_yearly": 6613.20, # = 12 × 551.10
            "neue_min_monthly": 160.81,        # Neue Selbständige Mindestbeitrag
            "max_base_monthly": 8085.00        # Höchstbeitragsgrundlage GSVG 2026 (WKO)
        },
        "deduction_config": {
            "home_office": 300.00,
            "child_deduction_monthly": 70.90,
            "single_parent_deduction": 612.00,
            "verkehrsabsetzbetrag": 496.00,
            "werbungskostenpauschale": 132.00,
            "familienbonus_under_18": 2000.16,
            "familienbonus_18_24": 700.08,
            "alleinverdiener_base": 612.00,
            "alleinverdiener_2_children": 828.00,
            "alleinverdiener_per_extra_child": 273.00,
            "commuting_brackets": {
                "small": {
                    "20": 58.00,
                    "40": 113.00,
                    "60": 168.00
                },
                "large": {
                    "2": 31.00,
                    "20": 123.00,
                    "40": 214.00,
                    "60": 306.00
                }
            },
            "pendler_euro_per_km": 6.00,
            "basic_exemption_rate": 0.15,
            "basic_exemption_max": 4950.00,
            "self_employed": {
                "grundfreibetrag_profit_limit": 33000.00,
                "grundfreibetrag_rate": 0.15,
                "grundfreibetrag_max": 4950.00,
                "max_total_freibetrag": 46400.00,
                "flat_rate_turnover_limit": 420000.00,
                "flat_rate_general": 0.15,
                "flat_rate_consulting": 0.06,
                "kleinunternehmer_threshold": 55000.00,
                "kleinunternehmer_tolerance": 60500.00,
                "ust_voranmeldung_monthly_threshold": 100000.00
            },
            "kindermehrbetrag": 700.00,
            "unterhaltsabsetzbetrag": {
                "first_child_monthly": 38.00,
                "second_child_monthly": 56.00,
                "third_plus_child_monthly": 75.00
            },
            # 2026: cold-progression adjusted (BMF 2026)
            "zuschlag_verkehrsabsetzbetrag": 804.00,
            "zuschlag_income_lower": 19761.00,
            "zuschlag_income_upper": 30259.00,
            "erhoehter_verkehrsabsetzbetrag": 853.00,
            "pensionisten_absetzbetrag": 1020.00,
            "pensionisten_income_lower": 21614.00,
            "pensionisten_income_upper": 31494.00,
            "erhoehter_pensionisten": 1502.00,
            "erhoehter_pensionisten_income_lower": 24616.00,
            "erhoehter_pensionisten_income_upper": 31494.00,
            "sonderausgabenpauschale": 60.00
        }
    }


def get_2025_tax_config() -> dict:
    """
    Get the 2025 tax configuration based on official USP tables.

    Source: https://www.usp.gv.at/en/.../tarifstufen.html
    Inflation rate 5.0% → brackets adjusted by 3.8333% (first–fifth levels).
    Kleinunternehmer threshold raised to €55,000 gross from 2025.

    Returns:
        Dictionary with 2025 tax configuration
    """
    return {
        "tax_year": 2025,
        "tax_brackets": [
            {"lower": 0, "upper": 13308, "rate": 0.00},
            {"lower": 13308, "upper": 21617, "rate": 0.20},
            {"lower": 21617, "upper": 35836, "rate": 0.30},
            {"lower": 35836, "upper": 69166, "rate": 0.40},
            {"lower": 69166, "upper": 103072, "rate": 0.48},
            {"lower": 103072, "upper": 1000000, "rate": 0.50},
            {"lower": 1000000, "upper": None, "rate": 0.55}
        ],
        "exemption_amount": 13308.00,
        "vat_rates": {
            "standard": 0.20,
            "residential": 0.10,
            "small_business_threshold": 55000.00,
            "tolerance_threshold": 60500.00
        },
        # SVS rates – Beitragsjahr 2025. Percentage rates stable (GSVG §§ 27–27a).
        # Fixed amounts adjusted via Aufwertungszahl 2025.
        "svs_rates": {
            "pension": 0.185,
            "health": 0.068,
            "accident_fixed": 11.35,
            "supplementary_pension": 0.0153,
            "gsvg_min_base_monthly": 500.91,
            "gsvg_min_income_yearly": 6010.92,
            "neue_min_monthly": 146.18,
            "max_base_monthly": 7525.00        # Höchstbeitragsgrundlage GSVG 2025 (WKO)
        },
        "deduction_config": {
            "home_office": 300.00,
            "child_deduction_monthly": 70.90,
            "single_parent_deduction": 601.00,
            "verkehrsabsetzbetrag": 487.00,
            "werbungskostenpauschale": 132.00,
            "familienbonus_under_18": 2000.16,
            "familienbonus_18_24": 700.08,
            "alleinverdiener_base": 601.00,
            "alleinverdiener_2_children": 813.00,
            "alleinverdiener_per_extra_child": 268.00,
            "commuting_brackets": {
                "small": {
                    "20": 58.00,
                    "40": 113.00,
                    "60": 168.00
                },
                "large": {
                    "2": 31.00,
                    "20": 123.00,
                    "40": 214.00,
                    "60": 306.00
                }
            },
            "pendler_euro_per_km": 2.00,
            "basic_exemption_rate": 0.15,
            "basic_exemption_max": 4950.00,
            "self_employed": {
                "grundfreibetrag_profit_limit": 33000.00,
                "grundfreibetrag_rate": 0.15,
                "grundfreibetrag_max": 4950.00,
                "max_total_freibetrag": 46400.00,
                "flat_rate_turnover_limit": 320000.00,
                "flat_rate_general": 0.135,
                "flat_rate_consulting": 0.06,
                "kleinunternehmer_threshold": 55000.00,
                "kleinunternehmer_tolerance": 60500.00,
                "ust_voranmeldung_monthly_threshold": 100000.00
            },
            "kindermehrbetrag": 700.00,
            "unterhaltsabsetzbetrag": {
                "first_child_monthly": 37.00,
                "second_child_monthly": 55.00,
                "third_plus_child_monthly": 73.00
            },
            # 2025: cold-progression adjusted (BMF/AK/finanz.at verified)
            "zuschlag_verkehrsabsetzbetrag": 790.00,
            "zuschlag_income_lower": 19424.00,
            "zuschlag_income_upper": 29743.00,
            "erhoehter_verkehrsabsetzbetrag": 838.00,
            "pensionisten_absetzbetrag": 1002.00,
            "pensionisten_income_lower": 21245.00,
            "pensionisten_income_upper": 30957.00,
            "erhoehter_pensionisten": 1476.00,
            "erhoehter_pensionisten_income_lower": 24196.00,
            "erhoehter_pensionisten_income_upper": 30957.00,
            "sonderausgabenpauschale": 60.00
        }
    }


def get_2024_tax_config() -> dict:
    """
    Get the 2024 tax configuration based on official USP tables.

    Source: https://www.usp.gv.at/en/.../tarifstufen.html
    Inflation rate 9.9% → brackets increased beyond 2/3 adjustment:
      1st level +9.6%, 2nd +8.8%, 3rd +7.6%, 4th +7.3%.
    Third bracket rate reduced from 41% to 40%.
    Kleinunternehmer threshold: €35,000 net (pre-2025 rules).

    Returns:
        Dictionary with 2024 tax configuration
    """
    return {
        "tax_year": 2024,
        "tax_brackets": [
            {"lower": 0, "upper": 12816, "rate": 0.00},
            {"lower": 12816, "upper": 20818, "rate": 0.20},
            {"lower": 20818, "upper": 34513, "rate": 0.30},
            {"lower": 34513, "upper": 66612, "rate": 0.40},
            {"lower": 66612, "upper": 99266, "rate": 0.48},
            {"lower": 99266, "upper": 1000000, "rate": 0.50},
            {"lower": 1000000, "upper": None, "rate": 0.55}
        ],
        "exemption_amount": 12816.00,
        "vat_rates": {
            "standard": 0.20,
            "residential": 0.10,
            # Pre-2025: Kleinunternehmer threshold was €35,000 net
            # Mid-2024 (July 20): raised to €42,000 for previous-year check,
            # but the main threshold remained €35,000 for the calendar year.
            "small_business_threshold": 35000.00,
            "tolerance_threshold": 38500.00
        },
        # SVS rates – Beitragsjahr 2024. Percentage rates stable (GSVG §§ 27–27a).
        # Fixed amounts adjusted via Aufwertungszahl 2024.
        "svs_rates": {
            "pension": 0.185,
            "health": 0.068,
            "accident_fixed": 10.97,
            "supplementary_pension": 0.0153,
            "gsvg_min_base_monthly": 500.91,
            "gsvg_min_income_yearly": 6010.92,
            "neue_min_monthly": 146.18,
            "max_base_monthly": 6825.00
        },
        "deduction_config": {
            "home_office": 300.00,
            "child_deduction_monthly": 67.80,
            "single_parent_deduction": 572.00,
            "verkehrsabsetzbetrag": 463.00,
            "werbungskostenpauschale": 132.00,
            "familienbonus_under_18": 2000.16,
            "familienbonus_18_24": 700.08,
            "alleinverdiener_base": 572.00,
            "alleinverdiener_2_children": 774.00,
            "alleinverdiener_per_extra_child": 255.00,
            "commuting_brackets": {
                "small": {
                    "20": 58.00,
                    "40": 113.00,
                    "60": 168.00
                },
                "large": {
                    "2": 31.00,
                    "20": 123.00,
                    "40": 214.00,
                    "60": 306.00
                }
            },
            "pendler_euro_per_km": 2.00,
            "basic_exemption_rate": 0.15,
            "basic_exemption_max": 4950.00,
            "self_employed": {
                "grundfreibetrag_profit_limit": 33000.00,
                "grundfreibetrag_rate": 0.15,
                "grundfreibetrag_max": 4950.00,
                "max_total_freibetrag": 46400.00,
                "flat_rate_turnover_limit": 220000.00,
                "flat_rate_general": 0.12,
                "flat_rate_consulting": 0.06,
                "kleinunternehmer_threshold": 35000.00,
                "kleinunternehmer_tolerance": 38500.00,
                "ust_voranmeldung_monthly_threshold": 100000.00
            },
            "kindermehrbetrag": 700.00,
            "unterhaltsabsetzbetrag": {
                "first_child_monthly": 35.00,
                "second_child_monthly": 52.00,
                "third_plus_child_monthly": 69.00
            },
            # 2024: cold-progression adjusted (BMF 2024)
            "zuschlag_verkehrsabsetzbetrag": 752.00,
            "zuschlag_income_lower": 18499.00,
            "zuschlag_income_upper": 28326.00,
            "erhoehter_verkehrsabsetzbetrag": 798.00,
            "pensionisten_absetzbetrag": 954.00,
            "pensionisten_income_lower": 20233.00,
            "pensionisten_income_upper": 29482.00,
            "erhoehter_pensionisten": 1405.00,
            "erhoehter_pensionisten_income_lower": 23043.00,
            "erhoehter_pensionisten_income_upper": 29482.00,
            "sonderausgabenpauschale": 60.00
        }
    }


def get_2022_tax_config() -> dict:
    """
    Get the 2022 tax configuration.

    Steuerjahr 2022 / Veranlagung 2023.
    Second bracket rate reduced from 35% to 30% (Öko-soziale Steuerreform).
    Third bracket rate: 42% (reduced to 41% in 2023, then 40% in 2024).
    Familienbonus Plus raised to €2,000.16.
    Kleinunternehmer threshold: €35,000 net.

    Returns:
        Dictionary with 2022 tax configuration
    """
    return {
        "tax_year": 2022,
        "tax_brackets": [
            {"lower": 0, "upper": 11000, "rate": 0.00},
            {"lower": 11000, "upper": 18000, "rate": 0.20},
            {"lower": 18000, "upper": 31000, "rate": 0.325},
            {"lower": 31000, "upper": 60000, "rate": 0.42},
            {"lower": 60000, "upper": 90000, "rate": 0.48},
            {"lower": 90000, "upper": 1000000, "rate": 0.50},
            {"lower": 1000000, "upper": None, "rate": 0.55}
        ],
        "exemption_amount": 11000.00,
        "vat_rates": {
            "standard": 0.20,
            "residential": 0.10,
            "small_business_threshold": 35000.00,
            "tolerance_threshold": 38500.00
        },
        # SVS rates – Beitragsjahr 2022
        "svs_rates": {
            "pension": 0.185,
            "health": 0.068,
            "accident_fixed": 10.09,
            "supplementary_pension": 0.0153,
            "gsvg_min_base_monthly": 485.85,
            "gsvg_min_income_yearly": 5830.20,
            "neue_min_monthly": 141.79,
            "max_base_monthly": 6615.00
        },
        "deduction_config": {
            "home_office": 300.00,
            "child_deduction_monthly": 58.40,
            "single_parent_deduction": 494.00,
            "verkehrsabsetzbetrag": 400.00,
            "werbungskostenpauschale": 132.00,
            "familienbonus_under_18": 2000.16,
            "familienbonus_18_24": 650.16,
            "alleinverdiener_base": 494.00,
            "alleinverdiener_2_children": 669.00,
            "alleinverdiener_per_extra_child": 220.00,
            "commuting_brackets": {
                "small": {
                    "20": 58.00,
                    "40": 113.00,
                    "60": 168.00
                },
                "large": {
                    "2": 31.00,
                    "20": 123.00,
                    "40": 214.00,
                    "60": 306.00
                }
            },
            # Pendlereuro: Regelwert 2.00 €/km/Jahr.
            # Temporäre Erhöhung 2022.05–2023.06: 8.00 €/km + Pauschale +50% (nicht modelliert).
            "pendler_euro_per_km": 2.00,
            "basic_exemption_rate": 0.15,
            "basic_exemption_max": 4950.00,
            "self_employed": {
                "grundfreibetrag_profit_limit": 33000.00,
                "grundfreibetrag_rate": 0.15,
                "grundfreibetrag_max": 4950.00,
                "max_total_freibetrag": 46400.00,
                "flat_rate_turnover_limit": 220000.00,
                "flat_rate_general": 0.12,
                "flat_rate_consulting": 0.06,
                "kleinunternehmer_threshold": 35000.00,
                "kleinunternehmer_tolerance": 38500.00,
                "ust_voranmeldung_monthly_threshold": 100000.00
            },
            "kindermehrbetrag": 550.00,
            "unterhaltsabsetzbetrag": {
                "first_child_monthly": 29.20,
                "second_child_monthly": 43.80,
                "third_plus_child_monthly": 58.40
            },
            # 2022: Zuschlag and Pensionistenabsetzbetrag (pre cold-progression)
            "zuschlag_verkehrsabsetzbetrag": 684.00,
            "zuschlag_income_lower": 15500.00,
            "zuschlag_income_upper": 24500.00,
            "pensionisten_absetzbetrag": 868.00,
            "pensionisten_income_lower": 17000.00,
            "pensionisten_income_upper": 25000.00,
            "erhoehter_pensionisten": 1214.00,
            "erhoehter_pensionisten_income_lower": 19930.00,
            "erhoehter_pensionisten_income_upper": 25250.00,
            "sonderausgabenpauschale": 60.00
        }
    }


def get_2023_tax_config() -> dict:
    """
    Get the 2023 tax configuration based on official USP tables.

    Source: https://www.usp.gv.at/en/.../tarifstufen.html
    First year of cold-progression adjustment. Inflation rate 5.2%.
    First two levels raised by 6.3%; remaining by 3.47%.
    Third bracket rate: 41% (reduced from 42%, will become 40% in 2024).
    Kleinunternehmer threshold: €35,000 net.

    Returns:
        Dictionary with 2023 tax configuration
    """
    return {
        "tax_year": 2023,
        "tax_brackets": [
            {"lower": 0, "upper": 11693, "rate": 0.00},
            {"lower": 11693, "upper": 19134, "rate": 0.20},
            {"lower": 19134, "upper": 32075, "rate": 0.30},
            {"lower": 32075, "upper": 62080, "rate": 0.41},
            {"lower": 62080, "upper": 93120, "rate": 0.48},
            {"lower": 93120, "upper": 1000000, "rate": 0.50},
            {"lower": 1000000, "upper": None, "rate": 0.55}
        ],
        "exemption_amount": 11693.00,
        "vat_rates": {
            "standard": 0.20,
            "residential": 0.10,
            "small_business_threshold": 35000.00,
            "tolerance_threshold": 38500.00
        },
        # SVS rates – Beitragsjahr 2023. Percentage rates stable (GSVG §§ 27–27a).
        # Fixed amounts adjusted via Aufwertungszahl 2023.
        "svs_rates": {
            "pension": 0.185,
            "health": 0.068,
            "accident_fixed": 10.42,
            "supplementary_pension": 0.0153,
            "gsvg_min_base_monthly": 485.85,
            "gsvg_min_income_yearly": 5830.20,
            "neue_min_monthly": 141.79,
            "max_base_monthly": 6615.00
        },
        "deduction_config": {
            "home_office": 300.00,
            "child_deduction_monthly": 61.80,
            "single_parent_deduction": 520.00,
            "verkehrsabsetzbetrag": 421.00,
            "werbungskostenpauschale": 132.00,
            "familienbonus_under_18": 2000.16,
            "familienbonus_18_24": 650.16,
            "alleinverdiener_base": 520.00,
            "alleinverdiener_2_children": 704.00,
            "alleinverdiener_per_extra_child": 232.00,
            "commuting_brackets": {
                "small": {
                    "20": 58.00,
                    "40": 113.00,
                    "60": 168.00
                },
                "large": {
                    "2": 31.00,
                    "20": 123.00,
                    "40": 214.00,
                    "60": 306.00
                }
            },
            # Pendlereuro: Regelwert 2.00 €/km/Jahr.
            # Temporäre Erhöhung 2022.05–2023.06: 8.00 €/km + Pauschale +50% (nicht modelliert).
            "pendler_euro_per_km": 2.00,
            "basic_exemption_rate": 0.15,
            "basic_exemption_max": 4950.00,
            "self_employed": {
                "grundfreibetrag_profit_limit": 33000.00,
                "grundfreibetrag_rate": 0.15,
                "grundfreibetrag_max": 4950.00,
                "max_total_freibetrag": 46400.00,
                "flat_rate_turnover_limit": 220000.00,
                "flat_rate_general": 0.12,
                "flat_rate_consulting": 0.06,
                "kleinunternehmer_threshold": 35000.00,
                "kleinunternehmer_tolerance": 38500.00,
                "ust_voranmeldung_monthly_threshold": 100000.00
            },
            "kindermehrbetrag": 550.00,
            "unterhaltsabsetzbetrag": {
                "first_child_monthly": 31.00,
                "second_child_monthly": 47.00,
                "third_plus_child_monthly": 62.00
            },
            # 2023: First year of cold-progression adjustment (Findok/BMF verified)
            "zuschlag_verkehrsabsetzbetrag": 684.00,
            "zuschlag_income_lower": 16832.00,
            "zuschlag_income_upper": 25774.00,
            "pensionisten_absetzbetrag": 868.00,
            "pensionisten_income_lower": 18410.00,
            "pensionisten_income_upper": 26826.00,
            "erhoehter_pensionisten": 1278.00,
            "erhoehter_pensionisten_income_lower": 20967.00,
            "erhoehter_pensionisten_income_upper": 26826.00,
            "sonderausgabenpauschale": 60.00
        }
    }

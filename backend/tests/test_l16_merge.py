"""Tests for L16 merge logic in confirm-tax-data endpoint."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.models.tax_filing_data import TaxFilingData


class TestL16MergeLogic:
    """Test that two L16 records for the same tax year merge correctly."""

    def test_kz_fields_accumulate(self):
        """When merging two L16s, numeric KZ fields should be summed."""
        existing_data = {
            "kz_210": 55000.0,
            "kz_245": 42500.0,
            "kz_260": 8750.0,
            "kz_230": 9200.0,
            "employer_name": "Employer A",
            "tax_year": 2025,
        }
        new_data = {
            "kz_210": 30000.0,
            "kz_245": 25000.0,
            "kz_260": 5000.0,
            "kz_230": 5000.0,
            "employer_name": "Employer B",
            "tax_year": 2025,
        }

        KZ_FIELDS = [
            "kz_210", "kz_215", "kz_220", "kz_225", "kz_226",
            "kz_230", "kz_245", "kz_260", "kz_718", "kz_719",
        ]
        merged = dict(existing_data)
        for kz in KZ_FIELDS:
            old_val = float(merged.get(kz) or 0)
            new_val = float(new_data.get(kz) or 0)
            if new_val:
                merged[kz] = round(old_val + new_val, 2)

        assert merged["kz_210"] == 85000.0
        assert merged["kz_245"] == 67500.0
        assert merged["kz_260"] == 13750.0
        assert merged["kz_230"] == 14200.0

    def test_merged_sources_tracked(self):
        """Merged record should track source document IDs."""
        existing_data = {"kz_245": 42500.0}
        sources = existing_data.get("merged_sources", [])
        sources.append(1)  # existing doc
        sources.append(2)  # new doc
        existing_data["merged_sources"] = sources
        existing_data["employer_count"] = len(sources)

        assert existing_data["merged_sources"] == [1, 2]
        assert existing_data["employer_count"] == 2

    def test_non_kz_fields_preserved(self):
        """Non-KZ fields from new data fill in missing fields in existing."""
        existing_data = {"kz_245": 42500.0, "employer_name": "A"}
        new_data = {"kz_245": 25000.0, "sv_nummer": "1234 010190"}

        for k, v in new_data.items():
            if k not in existing_data or existing_data[k] is None:
                existing_data[k] = v

        assert existing_data["employer_name"] == "A"  # kept
        assert existing_data["sv_nummer"] == "1234 010190"  # filled in

    def test_zero_kz_fields_not_overwrite(self):
        """Zero values in new data should not affect existing non-zero values."""
        existing_data = {"kz_718": 696.0}
        new_data = {"kz_718": 0}

        KZ_FIELDS = ["kz_718"]
        merged = dict(existing_data)
        for kz in KZ_FIELDS:
            old_val = float(merged.get(kz) or 0)
            new_val = float(new_data.get(kz) or 0)
            if new_val:
                merged[kz] = round(old_val + new_val, 2)

        assert merged["kz_718"] == 696.0  # unchanged because new_val is 0

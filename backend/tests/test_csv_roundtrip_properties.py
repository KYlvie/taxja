"""Property-based tests for CSV export/import roundtrip consistency"""
import pytest
from hypothesis import given, strategies as st
from decimal import Decimal
from datetime import date, datetime
import csv
from io import StringIO

from app.services.csv_generator import CSVGenerator


# Strategy for generating valid transactions
@st.composite
def transaction_strategy(draw):
    """Generate valid transaction data"""
    transaction_type = draw(st.sampled_from(['income', 'expense']))
    
    # Generate appropriate category based on type
    if transaction_type == 'income':
        category = draw(st.sampled_from(['employment', 'rental', 'self_employment', 'capital_gains']))
    else:
        category = draw(st.sampled_from([
            'office_supplies', 'equipment', 'travel', 'marketing',
            'professional_services', 'insurance', 'maintenance',
            'property_tax', 'loan_interest', 'groceries', 'utilities', 'other'
        ]))
    
    return {
        'id': draw(st.integers(min_value=1, max_value=1000000)),
        'date': draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))),
        'type': transaction_type,
        'amount': float(draw(st.decimals(min_value=0.01, max_value=100000, places=2))),
        'description': draw(st.text(min_size=1, max_size=200, alphabet=st.characters(blacklist_characters='\x00\n\r,'))),
        'category': category,
        'is_deductible': draw(st.booleans()),
        'deduction_reason': draw(st.one_of(
            st.none(),
            st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_characters='\x00\n\r,'))
        )),
        'vat_rate': draw(st.one_of(st.none(), st.decimals(min_value=0, max_value=0.25, places=4).map(float))),
        'vat_amount': draw(st.one_of(st.none(), st.decimals(min_value=0, max_value=10000, places=2).map(float))),
        'document_id': draw(st.one_of(st.none(), st.integers(min_value=1, max_value=100000))),
        'classification_confidence': draw(st.one_of(st.none(), st.decimals(min_value=0, max_value=1, places=2).map(float))),
        'import_source': draw(st.sampled_from(['manual', 'csv', 'psd2', 'ocr'])),
        'created_at': draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)))
    }


class TestCSVRoundtripConsistency:
    """
    Property 14: CSV export/import roundtrip consistency
    
    **Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5**
    
    For all valid transaction data sets:
    - Export to CSV → Import from CSV → Export to CSV should produce identical data
    - All transaction fields must be preserved
    - Data types must be correctly maintained
    - No data loss or corruption during roundtrip
    """
    
    @given(transactions=st.lists(transaction_strategy(), min_size=1, max_size=20))
    def test_csv_export_import_roundtrip_preserves_data(self, transactions):
        """
        Property: CSV export → import → export produces identical data.
        
        For any list of valid transactions:
        - Export to CSV
        - Parse CSV back to transactions
        - Export again to CSV
        - Both CSV outputs should be identical
        """
        generator = CSVGenerator()
        
        # First export
        csv1 = generator.generate_transactions_csv(transactions, include_headers=True)
        
        # Parse CSV back to transactions
        imported_transactions = self._parse_csv(csv1)
        
        # Second export
        csv2 = generator.generate_transactions_csv(imported_transactions, include_headers=True)
        
        # Both CSVs should be identical
        assert csv1 == csv2, "CSV roundtrip should produce identical output"
    
    @given(transactions=st.lists(transaction_strategy(), min_size=1, max_size=20))
    def test_csv_export_preserves_all_fields(self, transactions):
        """
        Property: CSV export preserves all transaction fields.
        
        For any list of transactions:
        - All fields must be present in CSV
        - No fields should be lost
        """
        generator = CSVGenerator()
        
        # Export to CSV
        csv_string = generator.generate_transactions_csv(transactions, include_headers=True)
        
        # Parse CSV
        imported_transactions = self._parse_csv(csv_string)
        
        # Check that we have the same number of transactions
        assert len(imported_transactions) == len(transactions)
        
        # Check that all fields are preserved
        for original, imported in zip(transactions, imported_transactions):
            # ID should match
            assert imported['id'] == original['id']
            
            # Date should match
            assert imported['date'] == original['date']
            
            # Type should match
            assert imported['type'] == original['type']
            
            # Amount should match (within floating point precision)
            assert abs(float(imported['amount']) - float(original['amount'])) < 0.01
            
            # Description should match
            assert imported['description'] == original['description']
            
            # Category should match
            assert imported['category'] == original['category']
            
            # is_deductible should match
            assert imported['is_deductible'] == original['is_deductible']
    
    @given(transactions=st.lists(transaction_strategy(), min_size=1, max_size=20))
    def test_csv_export_handles_none_values(self, transactions):
        """
        Property: CSV export correctly handles None/null values.
        
        For any transactions with None values:
        - None values should be exported as empty strings
        - Import should handle empty strings correctly
        """
        generator = CSVGenerator()
        
        # Export to CSV
        csv_string = generator.generate_transactions_csv(transactions, include_headers=True)
        
        # CSV should not contain the word "None"
        assert 'None' not in csv_string
        
        # Parse CSV
        imported_transactions = self._parse_csv(csv_string)
        
        # Check that None values are handled
        for original, imported in zip(transactions, imported_transactions):
            # If original had None for optional fields, imported should have empty string or None
            if original.get('deduction_reason') is None:
                assert imported.get('deduction_reason') in [None, '']
            
            if original.get('vat_rate') is None:
                assert imported.get('vat_rate') in [None, '']
            
            if original.get('document_id') is None:
                assert imported.get('document_id') in [None, '']
    
    @given(transactions=st.lists(transaction_strategy(), min_size=1, max_size=20))
    def test_csv_export_maintains_data_types(self, transactions):
        """
        Property: CSV export maintains correct data types after import.
        
        For any transactions:
        - Dates should remain dates
        - Numbers should remain numbers
        - Booleans should remain booleans
        - Strings should remain strings
        """
        generator = CSVGenerator()
        
        # Export to CSV
        csv_string = generator.generate_transactions_csv(transactions, include_headers=True)
        
        # Parse CSV
        imported_transactions = self._parse_csv(csv_string)
        
        # Check data types
        for imported in imported_transactions:
            # ID should be integer
            assert isinstance(imported['id'], int)
            
            # Date should be date object
            assert isinstance(imported['date'], date)
            
            # Amount should be numeric
            assert isinstance(imported['amount'], (int, float, Decimal))
            
            # is_deductible should be boolean
            assert isinstance(imported['is_deductible'], bool)
    
    @given(transactions=st.lists(transaction_strategy(), min_size=1, max_size=20))
    def test_csv_export_is_parseable(self, transactions):
        """
        Property: Exported CSV is always parseable.
        
        For any transactions:
        - CSV should be valid and parseable
        - No syntax errors
        """
        generator = CSVGenerator()
        
        # Export to CSV
        csv_string = generator.generate_transactions_csv(transactions, include_headers=True)
        
        # Should be able to parse without errors
        try:
            imported_transactions = self._parse_csv(csv_string)
            assert len(imported_transactions) > 0
        except Exception as e:
            pytest.fail(f"CSV parsing failed: {e}")
    
    def _parse_csv(self, csv_string: str) -> list:
        """
        Parse CSV string back to transaction dictionaries.
        
        Args:
            csv_string: CSV string to parse
            
        Returns:
            List of transaction dictionaries
        """
        input_stream = StringIO(csv_string)
        reader = csv.DictReader(input_stream)
        
        transactions = []
        for row in reader:
            # Convert types back
            transaction = {
                'id': int(row['id']) if row['id'] else None,
                'date': date.fromisoformat(row['date']) if row['date'] else None,
                'type': row['type'] if row['type'] else None,
                'amount': float(row['amount']) if row['amount'] else None,
                'description': row['description'] if row['description'] else None,
                'category': row['category'] if row['category'] else None,
                'is_deductible': row['is_deductible'].lower() == 'true' if row['is_deductible'] else False,
                'deduction_reason': row['deduction_reason'] if row['deduction_reason'] else None,
                'vat_rate': float(row['vat_rate']) if row['vat_rate'] else None,
                'vat_amount': float(row['vat_amount']) if row['vat_amount'] else None,
                'document_id': int(row['document_id']) if row['document_id'] else None,
                'classification_confidence': float(row['classification_confidence']) if row['classification_confidence'] else None,
                'import_source': row['import_source'] if row['import_source'] else None,
                'created_at': datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            }
            transactions.append(transaction)
        
        return transactions

# Test suite to validate init.sql produces a correct database
# Run with: pytest tests/test_init_sql.py -v
import subprocess
import pytest

CONTAINER = "taxja-postgres"
TEST_DB = "taxja_init_test"
DB_USER = "taxja"


def _psql(db, sql):
    result = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", DB_USER, "-d", db, "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def _psql_postgres(sql):
    return _psql("postgres", sql)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    _psql_postgres(f"DROP DATABASE IF EXISTS {TEST_DB};")
    _psql_postgres(f"CREATE DATABASE {TEST_DB};")
    subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", DB_USER, "-d", TEST_DB, "-f", "/tmp/init.sql"],
        capture_output=True, text=True, timeout=60,
    )
    yield
    _psql_postgres(f"DROP DATABASE IF EXISTS {TEST_DB};")


class TestSchemaCompleteness:
    def test_table_count_matches_production(self):
        prod = int(_psql("taxja", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"))
        test = int(_psql(TEST_DB, "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"))
        assert test == prod, f"Table count mismatch: prod={prod}, test={test}"

    def test_all_expected_tables_exist(self):
        expected = [
            "users", "transactions", "documents", "plans",
            "subscriptions", "tax_configurations", "tax_reports",
            "credit_balances", "credit_cost_configs", "credit_ledger",
            "credit_topup_packages", "topup_purchases",
            "properties", "property_loans", "liabilities",
            "recurring_transactions", "loan_installments",
            "bank_statement_imports", "bank_statement_lines",
            "audit_logs", "chat_messages", "notifications",
            "classification_corrections", "alembic_version",
        ]
        tables = _psql(TEST_DB, "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
        table_set = set(tables.split("\n"))
        for t in expected:
            assert t in table_set, f"Missing table: {t}"

    def test_enum_types_exist(self):
        expected_enums = [
            "plantype", "usertype", "transactiontype",
            "documenttype", "subscriptionstatus",
            "creditoperation", "creditsource",
        ]
        enums = _psql(TEST_DB, "SELECT typname FROM pg_type WHERE typtype='e';")
        enum_set = set(enums.split("\n"))
        for e in expected_enums:
            assert e in enum_set, f"Missing enum: {e}"

    def test_index_count_reasonable(self):
        count = int(_psql(TEST_DB, "SELECT count(*) FROM pg_indexes WHERE schemaname='public';"))
        assert count >= 30, f"Too few indexes: {count}"


class TestSeedData:
    def test_plans_count(self):
        assert _psql(TEST_DB, "SELECT count(*) FROM plans;") == "3"

    def test_plans_types(self):
        types = _psql(TEST_DB, "SELECT plan_type FROM plans ORDER BY id;")
        assert types == "free\nplus\npro"

    def test_pro_plan_credits(self):
        credits = _psql(TEST_DB, "SELECT monthly_credits FROM plans WHERE plan_type='pro';")
        assert credits == "2000"

    def test_plus_plan_credits(self):
        credits = _psql(TEST_DB, "SELECT monthly_credits FROM plans WHERE plan_type='plus';")
        assert credits == "500"

    def test_free_plan_credits(self):
        credits = _psql(TEST_DB, "SELECT monthly_credits FROM plans WHERE plan_type='free';")
        assert credits == "100"

    def test_tax_configurations_count(self):
        assert _psql(TEST_DB, "SELECT count(*) FROM tax_configurations;") == "5"

    def test_tax_years_covered(self):
        years = _psql(TEST_DB, "SELECT tax_year FROM tax_configurations ORDER BY tax_year;")
        assert years == "2022\n2023\n2024\n2025\n2026"

    def test_2026_tax_exemption(self):
        val = _psql(TEST_DB, "SELECT exemption_amount FROM tax_configurations WHERE tax_year=2026;")
        assert val == "13539.00"

    def test_credit_cost_configs_count(self):
        assert _psql(TEST_DB, "SELECT count(*) FROM credit_cost_configs;") == "6"

    def test_credit_cost_operations(self):
        ops = _psql(TEST_DB, "SELECT operation FROM credit_cost_configs ORDER BY id;")
        expected = "ocr_scan\nai_conversation\ntransaction_entry\nbank_import\ne1_generation\ntax_calc"
        assert ops == expected

    def test_credit_topup_packages_count(self):
        assert _psql(TEST_DB, "SELECT count(*) FROM credit_topup_packages;") == "3"


class TestAlembicVersion:
    def test_alembic_version_set(self):
        ver = _psql(TEST_DB, "SELECT version_num FROM alembic_version;")
        assert ver == "068_resync_doctypes"


class TestForeignKeys:
    def test_transactions_user_fk(self):
        count = int(_psql(TEST_DB,
            "SELECT count(*) FROM information_schema.table_constraints "
            "WHERE table_name='transactions' AND constraint_type='FOREIGN KEY';"))
        assert count >= 2, f"transactions should have at least 2 FKs, got {count}"

    def test_documents_user_fk(self):
        count = int(_psql(TEST_DB,
            "SELECT count(*) FROM information_schema.table_constraints "
            "WHERE table_name='documents' AND constraint_type='FOREIGN KEY';"))
        assert count >= 1, f"documents should have at least 1 FK, got {count}"

    def test_subscriptions_fks(self):
        count = int(_psql(TEST_DB,
            "SELECT count(*) FROM information_schema.table_constraints "
            "WHERE table_name='subscriptions' AND constraint_type='FOREIGN KEY';"))
        assert count >= 2, f"subscriptions should have at least 2 FKs, got {count}"

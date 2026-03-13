"""Unit tests for historical import API endpoints"""
import pytest
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from io import BytesIO
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User, UserType
from app.models.historical_import import (
    HistoricalImportSession,
    HistoricalImportUpload,
    HistoricalDocumentType,
    ImportStatus,
    ImportSessionStatus,
    ImportConflict,
)
from app.core.security import get_password_hash, create_access_token


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        password_hash=get_password_hash("TestPassword123"),
        name="Test User",
        user_type=UserType.EMPLOYEE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers with JWT token"""
    access_token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def client() -> TestClient:
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def test_session(db: Session, test_user: User) -> HistoricalImportSession:
    """Create a test import session"""
    session = HistoricalImportSession(
        user_id=test_user.id,
        status=ImportSessionStatus.ACTIVE,
        tax_years=[2021, 2022, 2023],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@pytest.fixture
def test_upload(db: Session, test_user: User) -> HistoricalImportUpload:
    """Create a test upload"""
    upload = HistoricalImportUpload(
        user_id=test_user.id,
        document_id=1,
        document_type=HistoricalDocumentType.E1_FORM,
        tax_year=2023,
        status=ImportStatus.EXTRACTED,
        extraction_confidence=Decimal("0.85"),
        extracted_data={"kz_245": "50000.00"},
        requires_review=False,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


class TestUploadEndpoint:
    """Tests for POST /api/v1/historical-import/upload endpoint"""

    def test_upload_valid_pdf(self, client: TestClient, auth_headers: dict, db: Session):
        """Test uploading a valid PDF document"""
        # Create fake PDF file
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {"document_type": "e1_form", "tax_year": 2023}

        with pytest.mock.patch("app.tasks.ocr_tasks.process_historical_import_ocr") as mock_task:
            mock_task.delay.return_value.id = "test-task-id"

            response = client.post(
                "/api/v1/historical-import/upload",
                files=files,
                data=data,
                headers=auth_headers,
            )

        assert response.status_code == 201
        result = response.json()
        assert "upload_id" in result
        assert result["status"] == "uploaded"
        assert "task_id" in result
        assert "estimated_completion" in result

    def test_upload_with_session_id(
        self, client: TestClient, auth_headers: dict, test_session: HistoricalImportSession, db: Session
    ):
        """Test uploading a document with session ID"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {
            "document_type": "bescheid",
            "tax_year": 2022,
            "session_id": str(test_session.id),
        }

        with pytest.mock.patch("app.tasks.ocr_tasks.process_historical_import_ocr") as mock_task:
            mock_task.delay.return_value.id = "test-task-id"

            response = client.post(
                "/api/v1/historical-import/upload",
                files=files,
                data=data,
                headers=auth_headers,
            )

        assert response.status_code == 201
        result = response.json()
        assert "upload_id" in result

        # Verify session was updated
        db.refresh(test_session)
        assert test_session.total_documents == 1

    def test_upload_csv_for_saldenliste(self, client: TestClient, auth_headers: dict):
        """Test uploading CSV file for Saldenliste"""
        csv_content = b"account,balance\n1000,5000.00\n2000,3000.00"
        files = {"file": ("saldenliste.csv", BytesIO(csv_content), "text/csv")}
        data = {"document_type": "saldenliste", "tax_year": 2023}

        with pytest.mock.patch("app.tasks.ocr_tasks.process_historical_import_ocr") as mock_task:
            mock_task.delay.return_value.id = "test-task-id"

            response = client.post(
                "/api/v1/historical-import/upload",
                files=files,
                data=data,
                headers=auth_headers,
            )

        assert response.status_code == 201

    def test_upload_pdf_for_saldenliste_fails(self, client: TestClient, auth_headers: dict):
        """Test that PDF upload for Saldenliste is rejected"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {"document_type": "saldenliste", "tax_year": 2023}

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Saldenliste must be CSV or Excel" in response.json()["detail"]

    def test_upload_invalid_file_type(self, client: TestClient, auth_headers: dict):
        """Test uploading invalid file type"""
        txt_content = b"plain text file"
        files = {"file": ("test.txt", BytesIO(txt_content), "text/plain")}
        data = {"document_type": "e1_form", "tax_year": 2023}

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid file format" in response.json()["detail"]

    def test_upload_missing_document_type(self, client: TestClient, auth_headers: dict):
        """Test upload without document_type fails"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {"tax_year": 2023}

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "document_type is required" in response.json()["detail"]

    def test_upload_missing_tax_year(self, client: TestClient, auth_headers: dict):
        """Test upload without tax_year fails"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {"document_type": "e1_form"}

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "tax_year is required" in response.json()["detail"]

    def test_upload_invalid_document_type(self, client: TestClient, auth_headers: dict):
        """Test upload with invalid document_type"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {"document_type": "invalid_type", "tax_year": 2023}

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid document_type" in response.json()["detail"]

    def test_upload_future_tax_year(self, client: TestClient, auth_headers: dict):
        """Test upload with future tax year fails"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        future_year = date.today().year + 1
        data = {"document_type": "e1_form", "tax_year": future_year}

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "cannot be in the future" in response.json()["detail"]

    def test_upload_too_old_tax_year(self, client: TestClient, auth_headers: dict):
        """Test upload with tax year more than 10 years old fails"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        old_year = date.today().year - 11
        data = {"document_type": "e1_form", "tax_year": old_year}

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "too old" in response.json()["detail"]

    def test_upload_invalid_session_id(self, client: TestClient, auth_headers: dict):
        """Test upload with invalid session_id format"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {
            "document_type": "e1_form",
            "tax_year": 2023,
            "session_id": "invalid-uuid",
        }

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid session_id format" in response.json()["detail"]

    def test_upload_nonexistent_session(self, client: TestClient, auth_headers: dict):
        """Test upload with non-existent session_id"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {
            "document_type": "e1_form",
            "tax_year": 2023,
            "session_id": str(uuid4()),
        }

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    def test_upload_requires_authentication(self, client: TestClient):
        """Test that upload endpoint requires authentication"""
        pdf_content = b"%PDF-1.4 fake pdf content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {"document_type": "e1_form", "tax_year": 2023}

        response = client.post(
            "/api/v1/historical-import/upload",
            files=files,
            data=data,
        )

        assert response.status_code == 401


class TestStatusEndpoint:
    """Tests for GET /api/v1/historical-import/status/{upload_id} endpoint"""

    def test_get_status_success(
        self, client: TestClient, auth_headers: dict, test_upload: HistoricalImportUpload
    ):
        """Test getting upload status"""
        response = client.get(
            f"/api/v1/historical-import/status/{test_upload.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["upload_id"] == str(test_upload.id)
        assert result["status"] == "extracted"
        assert result["progress"] == 80
        assert result["confidence"] == 0.85
        assert result["extraction_data"] == {"kz_245": "50000.00"}
        assert result["requires_review"] is False

    def test_get_status_with_edited_data(
        self, client: TestClient, auth_headers: dict, test_upload: HistoricalImportUpload, db: Session
    ):
        """Test that edited_data takes precedence over extracted_data"""
        test_upload.edited_data = {"kz_245": "55000.00"}
        db.commit()

        response = client.get(
            f"/api/v1/historical-import/status/{test_upload.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["extraction_data"] == {"kz_245": "55000.00"}

    def test_get_status_various_states(
        self, client: TestClient, auth_headers: dict, test_upload: HistoricalImportUpload, db: Session
    ):
        """Test status endpoint with various upload states"""
        states_and_progress = [
            (ImportStatus.UPLOADED, 10),
            (ImportStatus.PROCESSING, 50),
            (ImportStatus.EXTRACTED, 80),
            (ImportStatus.REVIEW_REQUIRED, 90),
            (ImportStatus.APPROVED, 100),
            (ImportStatus.REJECTED, 100),
            (ImportStatus.FAILED, 0),
        ]

        for status, expected_progress in states_and_progress:
            test_upload.status = status
            db.commit()

            response = client.get(
                f"/api/v1/historical-import/status/{test_upload.id}",
                headers=auth_headers,
            )

            assert response.status_code == 200
            result = response.json()
            assert result["status"] == status.value
            assert result["progress"] == expected_progress

    def test_get_status_invalid_upload_id(self, client: TestClient, auth_headers: dict):
        """Test getting status with invalid upload_id format"""
        response = client.get(
            "/api/v1/historical-import/status/invalid-uuid",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid upload_id format" in response.json()["detail"]

    def test_get_status_nonexistent_upload(self, client: TestClient, auth_headers: dict):
        """Test getting status for non-existent upload"""
        response = client.get(
            f"/api/v1/historical-import/status/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Upload not found" in response.json()["detail"]

    def test_get_status_user_isolation(
        self, client: TestClient, test_upload: HistoricalImportUpload, db: Session
    ):
        """Test that users can only access their own uploads"""
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash=get_password_hash("Password123"),
            name="Other User",
            user_type=UserType.EMPLOYEE,
        )
        db.add(other_user)
        db.commit()

        # Create token for other user
        token = create_access_token(data={"sub": other_user.email})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            f"/api/v1/historical-import/status/{test_upload.id}",
            headers=headers,
        )

        assert response.status_code == 404

    def test_get_status_requires_authentication(
        self, client: TestClient, test_upload: HistoricalImportUpload
    ):
        """Test that status endpoint requires authentication"""
        response = client.get(f"/api/v1/historical-import/status/{test_upload.id}")
        assert response.status_code == 401


class TestSessionEndpoint:
    """Tests for POST /api/v1/historical-import/session endpoint"""

    def test_create_session_success(self, client: TestClient, auth_headers: dict):
        """Test creating a new import session"""
        data = {
            "tax_years": [2021, 2022, 2023],
            "document_types": ["e1_form", "bescheid"],
        }

        response = client.post(
            "/api/v1/historical-import/session",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        result = response.json()
        assert "session_id" in result
        assert result["status"] == "active"
        assert result["tax_years"] == [2021, 2022, 2023]
        assert result["expected_documents"] == 6  # 3 years * 2 doc types
        assert result["uploaded_documents"] == 0

    def test_create_session_without_document_types(self, client: TestClient, auth_headers: dict):
        """Test creating session without document types"""
        data = {"tax_years": [2023]}

        response = client.post(
            "/api/v1/historical-import/session",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        result = response.json()
        assert result["expected_documents"] == 0

    def test_create_session_empty_tax_years(self, client: TestClient, auth_headers: dict):
        """Test creating session with empty tax_years fails"""
        data = {"tax_years": [], "document_types": ["e1_form"]}

        response = client.post(
            "/api/v1/historical-import/session",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "At least one tax year is required" in response.json()["detail"]

    def test_create_session_invalid_tax_year(self, client: TestClient, auth_headers: dict):
        """Test creating session with invalid tax year"""
        future_year = date.today().year + 1
        data = {"tax_years": [2023, future_year], "document_types": ["e1_form"]}

        response = client.post(
            "/api/v1/historical-import/session",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "cannot be in the future" in response.json()["detail"]

    def test_create_session_invalid_document_type(self, client: TestClient, auth_headers: dict):
        """Test creating session with invalid document type"""
        data = {"tax_years": [2023], "document_types": ["invalid_type"]}

        response = client.post(
            "/api/v1/historical-import/session",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid document_type" in response.json()["detail"]

    def test_create_session_requires_authentication(self, client: TestClient):
        """Test that session creation requires authentication"""
        data = {"tax_years": [2023], "document_types": ["e1_form"]}

        response = client.post("/api/v1/historical-import/session", json=data)
        assert response.status_code == 401


class TestGetSessionEndpoint:
    """Tests for GET /api/v1/historical-import/session/{session_id} endpoint"""

    def test_get_session_success(
        self,
        client: TestClient,
        auth_headers: dict,
        test_session: HistoricalImportSession,
        test_upload: HistoricalImportUpload,
        db: Session,
    ):
        """Test getting session status"""
        # Link upload to session
        test_upload.session_id = test_session.id
        db.commit()

        response = client.get(
            f"/api/v1/historical-import/session/{test_session.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["session_id"] == str(test_session.id)
        assert result["status"] == "active"
        assert result["tax_years"] == [2021, 2022, 2023]
        assert len(result["documents"]) == 1
        assert result["documents"][0]["upload_id"] == str(test_upload.id)
        assert "summary" in result

    def test_get_session_with_conflicts(
        self,
        client: TestClient,
        auth_headers: dict,
        test_session: HistoricalImportSession,
        test_upload: HistoricalImportUpload,
        db: Session,
    ):
        """Test getting session with conflicts"""
        # Create another upload
        upload2 = HistoricalImportUpload(
            session_id=test_session.id,
            user_id=test_session.user_id,
            document_id=2,
            document_type=HistoricalDocumentType.BESCHEID,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
        )
        db.add(upload2)
        db.commit()

        # Create a conflict
        conflict = ImportConflict(
            session_id=test_session.id,
            upload_id_1=test_upload.id,
            upload_id_2=upload2.id,
            conflict_type="conflicting_amount",
            field_name="employment_income",
            value_1="50000.00",
            value_2="51000.00",
        )
        db.add(conflict)
        db.commit()

        response = client.get(
            f"/api/v1/historical-import/session/{test_session.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["conflict_type"] == "conflicting_amount"
        assert result["summary"]["conflicts_detected"] == 1

    def test_get_session_invalid_id(self, client: TestClient, auth_headers: dict):
        """Test getting session with invalid ID format"""
        response = client.get(
            "/api/v1/historical-import/session/invalid-uuid",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid session_id format" in response.json()["detail"]

    def test_get_session_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting non-existent session"""
        response = client.get(
            f"/api/v1/historical-import/session/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    def test_get_session_user_isolation(
        self, client: TestClient, test_session: HistoricalImportSession, db: Session
    ):
        """Test that users can only access their own sessions"""
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash=get_password_hash("Password123"),
            name="Other User",
            user_type=UserType.EMPLOYEE,
        )
        db.add(other_user)
        db.commit()

        # Create token for other user
        token = create_access_token(data={"sub": other_user.email})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            f"/api/v1/historical-import/session/{test_session.id}",
            headers=headers,
        )

        assert response.status_code == 404

    def test_get_session_requires_authentication(
        self, client: TestClient, test_session: HistoricalImportSession
    ):
        """Test that get session endpoint requires authentication"""
        response = client.get(f"/api/v1/historical-import/session/{test_session.id}")
        assert response.status_code == 401


class TestReviewEndpoint:
    """Tests for POST /api/v1/historical-import/review/{upload_id} endpoint"""

    def test_approve_upload_success(
        self, client: TestClient, auth_headers: dict, test_upload: HistoricalImportUpload, db: Session
    ):
        """Test approving an upload"""
        data = {"approved": True, "notes": "Data looks correct"}

        response = client.post(
            f"/api/v1/historical-import/review/{test_upload.id}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert "import_id" in result
        assert result["summary"]["status"] == "approved"

        # Verify upload status was updated
        db.refresh(test_upload)
        assert test_upload.status == ImportStatus.APPROVED
        assert test_upload.reviewed_at is not None
        assert test_upload.approval_notes == "Data looks correct"

    def test_approve_with_edited_data(
        self, client: TestClient, auth_headers: dict, test_upload: HistoricalImportUpload, db: Session
    ):
        """Test approving with edited data"""
        data = {
            "approved": True,
            "edited_data": {"kz_245": "55000.00"},
            "notes": "Corrected employment income",
        }

        response = client.post(
            f"/api/v1/historical-import/review/{test_upload.id}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify edited data was stored
        db.refresh(test_upload)
        assert test_upload.edited_data == {"kz_245": "55000.00"}
        assert test_upload.approval_notes == "Corrected employment income"

    def test_reject_upload_success(
        self, client: TestClient, auth_headers: dict, test_upload: HistoricalImportUpload, db: Session
    ):
        """Test rejecting an upload"""
        data = {"approved": False, "notes": "Incorrect data extracted"}

        response = client.post(
            f"/api/v1/historical-import/review/{test_upload.id}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["summary"]["status"] == "rejected"

        # Verify upload status was updated
        db.refresh(test_upload)
        assert test_upload.status == ImportStatus.REJECTED
        assert test_upload.reviewed_at is not None
        assert test_upload.approval_notes == "Incorrect data extracted"

    def test_approve_updates_session_metrics(
        self,
        client: TestClient,
        auth_headers: dict,
        test_upload: HistoricalImportUpload,
        test_session: HistoricalImportSession,
        db: Session,
    ):
        """Test that approval updates session metrics"""
        test_upload.session_id = test_session.id
        db.commit()

        data = {"approved": True}

        response = client.post(
            f"/api/v1/historical-import/review/{test_upload.id}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify session metrics were updated
        db.refresh(test_session)
        assert test_session.successful_imports == 1

    def test_reject_updates_session_metrics(
        self,
        client: TestClient,
        auth_headers: dict,
        test_upload: HistoricalImportUpload,
        test_session: HistoricalImportSession,
        db: Session,
    ):
        """Test that rejection updates session metrics"""
        test_upload.session_id = test_session.id
        db.commit()

        data = {"approved": False, "notes": "Incorrect data"}

        response = client.post(
            f"/api/v1/historical-import/review/{test_upload.id}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify session metrics were updated
        db.refresh(test_session)
        assert test_session.failed_imports == 1

    def test_review_invalid_upload_id(self, client: TestClient, auth_headers: dict):
        """Test review with invalid upload_id format"""
        data = {"approved": True}

        response = client.post(
            "/api/v1/historical-import/review/invalid-uuid",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "Invalid upload_id format" in response.json()["detail"]

    def test_review_nonexistent_upload(self, client: TestClient, auth_headers: dict):
        """Test review of non-existent upload"""
        data = {"approved": True}

        response = client.post(
            f"/api/v1/historical-import/review/{uuid4()}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Upload not found" in response.json()["detail"]

    def test_review_wrong_status(
        self, client: TestClient, auth_headers: dict, test_upload: HistoricalImportUpload, db: Session
    ):
        """Test that review fails if upload is not in reviewable state"""
        test_upload.status = ImportStatus.UPLOADED
        db.commit()

        data = {"approved": True}

        response = client.post(
            f"/api/v1/historical-import/review/{test_upload.id}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "cannot be reviewed in current status" in response.json()["detail"]

    def test_review_user_isolation(
        self, client: TestClient, test_upload: HistoricalImportUpload, db: Session
    ):
        """Test that users can only review their own uploads"""
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash=get_password_hash("Password123"),
            name="Other User",
            user_type=UserType.EMPLOYEE,
        )
        db.add(other_user)
        db.commit()

        # Create token for other user
        token = create_access_token(data={"sub": other_user.email})
        headers = {"Authorization": f"Bearer {token}"}

        data = {"approved": True}

        response = client.post(
            f"/api/v1/historical-import/review/{test_upload.id}",
            json=data,
            headers=headers,
        )

        assert response.status_code == 404

    def test_review_requires_authentication(
        self, client: TestClient, test_upload: HistoricalImportUpload
    ):
        """Test that review endpoint requires authentication"""
        data = {"approved": True}

        response = client.post(
            f"/api/v1/historical-import/review/{test_upload.id}",
            json=data,
        )

        assert response.status_code == 401


class TestAuthorizationAndSecurity:
    """Tests for authentication and authorization across all endpoints"""

    def test_all_endpoints_require_authentication(self, client: TestClient):
        """Test that all endpoints require authentication"""
        endpoints = [
            ("POST", "/api/v1/historical-import/upload", {"files": {}, "data": {}}),
            ("GET", f"/api/v1/historical-import/status/{uuid4()}", {}),
            ("POST", "/api/v1/historical-import/session", {"json": {}}),
            ("GET", f"/api/v1/historical-import/session/{uuid4()}", {}),
            ("POST", f"/api/v1/historical-import/review/{uuid4()}", {"json": {}}),
        ]

        for method, url, kwargs in endpoints:
            if method == "POST":
                response = client.post(url, **kwargs)
            else:
                response = client.get(url)

            assert response.status_code == 401, f"Endpoint {method} {url} should require auth"

    def test_user_cannot_access_other_users_data(self, client: TestClient, db: Session):
        """Test comprehensive user isolation across all endpoints"""
        # Create two users
        user1 = User(
            email="user1@example.com",
            password_hash=get_password_hash("Password123"),
            name="User 1",
            user_type=UserType.EMPLOYEE,
        )
        user2 = User(
            email="user2@example.com",
            password_hash=get_password_hash("Password123"),
            name="User 2",
            user_type=UserType.EMPLOYEE,
        )
        db.add(user1)
        db.add(user2)
        db.commit()

        # Create session and upload for user2
        session = HistoricalImportSession(
            user_id=user2.id,
            status=ImportSessionStatus.ACTIVE,
            tax_years=[2023],
        )
        db.add(session)
        db.commit()

        upload = HistoricalImportUpload(
            user_id=user2.id,
            document_id=1,
            document_type=HistoricalDocumentType.E1_FORM,
            tax_year=2023,
            status=ImportStatus.EXTRACTED,
        )
        db.add(upload)
        db.commit()

        # Try to access user2's data as user1
        token = create_access_token(data={"sub": user1.email})
        headers = {"Authorization": f"Bearer {token}"}

        # Test status endpoint
        response = client.get(
            f"/api/v1/historical-import/status/{upload.id}",
            headers=headers,
        )
        assert response.status_code == 404

        # Test session endpoint
        response = client.get(
            f"/api/v1/historical-import/session/{session.id}",
            headers=headers,
        )
        assert response.status_code == 404

        # Test review endpoint
        response = client.post(
            f"/api/v1/historical-import/review/{upload.id}",
            json={"approved": True},
            headers=headers,
        )
        assert response.status_code == 404

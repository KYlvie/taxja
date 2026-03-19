"""Shared helpers for pipeline tests."""


class FakeDocument:
    """Lightweight document stand-in for pipeline unit tests.

    Unlike MagicMock(spec=Document), this has real dict attributes so
    json.dumps(doc.ocr_result) works and flag_modified doesn't crash.
    """

    def __init__(self, id=1, ocr_result=None, **kwargs):
        self.id = id
        self.user_id = kwargs.get("user_id", 1)
        self.document_type = kwargs.get("document_type", None)
        self.file_name = kwargs.get("file_name", "test.pdf")
        self.mime_type = kwargs.get("mime_type", "application/pdf")
        self.ocr_result = ocr_result or {}
        self.raw_text = kwargs.get("raw_text", "")
        self.confidence_score = kwargs.get("confidence_score", None)
        self.processed_at = None

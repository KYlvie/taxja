from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import KeepInFrame, Paragraph, Spacer
from reportlab.pdfgen import canvas


PAGE_SIZE = landscape(A4)
OUTPUT_PATH = Path("output/pdf/taxja-app-summary.pdf")

REFS = {
    "R1": "README.md",
    "R2": "QUICK_START.md",
    "R3": "start-dev.ps1",
    "R4": "start-services.ps1",
    "R5": "frontend/src/routes/index.tsx",
    "R6": "frontend/package.json",
    "R7": "frontend/public/manifest.webmanifest",
    "R8": "frontend/src/components/dashboard/README.md",
    "R9": "frontend/src/components/documents/README.md",
    "R10": "frontend/src/components/ai/README.md",
    "R11": "frontend/src/components/reports/README.md",
    "R12": "frontend/src/components/transactions/README.md",
    "R13": "frontend/src/pages/PropertiesPage.tsx",
    "R14": "backend/app/main.py",
    "R15": "backend/app/api/v1/router.py",
    "R16": "backend/app/api/v1/endpoints/documents.py",
    "R17": "backend/app/services/document_pipeline_orchestrator.py",
    "R18": "backend/app/services/storage_service.py",
    "R19": "backend/app/db/session.py",
    "R20": "backend/app/celery_app.py",
    "R21": "docker-compose.yml",
    "R22": "backend/app/api/v1/recurring_transactions.py",
    "R23": "backend/app/api/v1/endpoints/properties.py",
}

TITLE = "Taxja App Summary"
SUBTITLE = "One-page summary based only on repo evidence"

WHAT_IT_IS = (
    "Taxja is an Austrian tax management app that combines transaction tracking, "
    "document OCR, reporting, and filing helpers in one product. The repo implements "
    "it as a React/Vite frontend backed by a FastAPI API, background workers, and "
    "local infrastructure services. [R1,R6,R14,R21]"
)

WHO_ITS_FOR = (
    "Primary persona appears to be Austrian taxpayers - especially employees, "
    "landlords/property owners, self-employed users, and small business owners. [R1]"
)

FEATURES = [
    "Dashboard for YTD income/expense, estimated tax, deadlines, savings ideas, what-if simulation, and refund estimate. [R8]",
    "Document upload for images/PDFs with OCR review, confidence checks, search, download, and mobile camera capture. [R9,R16]",
    "Transaction management with create/edit/filter/detail views and CSV import. [R12]",
    "Property and asset management with portfolio, detail views, depreciation, and property reports. [R5,R13,R23]",
    "Recurring transaction workflows for rent, loan interest, manual templates, and due-entry generation. [R22]",
    "Tax report and form workflows including PDF/XML exports, audit checklist, and GDPR data export. [R11]",
    "AI assistant with page-aware questions and document/tax guidance. [R10]",
]

ARCHITECTURE = [
    "Frontend: React + TypeScript app with routed pages, Zustand state, axios API access, and PWA/mobile packaging. [R5,R6,R7]",
    "API: FastAPI app mounts versioned routers for auth, dashboard, transactions, documents, properties, recurring flows, reports, AI, subscriptions, admin, health, and metrics. [R14,R15]",
    "Data: SQLAlchemy sessions connect app services to PostgreSQL; Redis is used for cache and task/rate-limit support. [R14,R19,R20,R21]",
    "Docs and OCR: document endpoints upload files to MinIO/S3, then the pipeline runs OCR, classification, extraction, validation, and auto-create suggestions; work is queued to Celery when available. [R16,R17,R18,R20]",
    "Local stack: Docker Compose wires frontend, backend, postgres, redis, minio, and a celery-worker. [R21]",
]

RUN_STEPS = [
    "Install Docker Desktop, Python 3.11+, and Node.js 20+. [R2]",
    "From the repo root, run .\\start-dev.ps1 to start infra, create the backend venv, install deps, copy .env, and run migrations. [R2,R3]",
    "Run .\\start-services.ps1 to launch backend and frontend in new PowerShell windows. [R2,R4]",
    "Open http://localhost:5173 for the app and http://localhost:8000/docs for the API docs. [R2,R4]",
]


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def section(title: str, body_items: list[str], body_style: ParagraphStyle, title_style: ParagraphStyle):
    flowables = [Paragraph(escape(title), title_style), Spacer(1, 2)]
    for item in body_items:
        flowables.append(Paragraph(escape(item), body_style))
        flowables.append(Spacer(1, 4))
    flowables.append(Spacer(1, 2))
    return flowables


def bullet_section(title: str, bullets: list[str], bullet_style: ParagraphStyle, title_style: ParagraphStyle):
    flowables = [Paragraph(escape(title), title_style), Spacer(1, 2)]
    for bullet in bullets:
        flowables.append(Paragraph(escape(bullet), bullet_style, bulletText="-"))
        flowables.append(Spacer(1, 4))
    flowables.append(Spacer(1, 2))
    return flowables


def build_pdf():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT_PATH), pagesize=PAGE_SIZE)
    page_w, page_h = PAGE_SIZE

    margin = 26
    gutter = 16
    header_h = 64
    refs_h = 134
    gap = 12
    col_w = (page_w - (2 * margin) - gutter) / 2
    col_h = page_h - margin - header_h - refs_h - gap - 10
    top_y = page_h - margin - header_h

    styles = {
        "section": ParagraphStyle(
            "section",
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=13,
            textColor=colors.HexColor("#11344c"),
            spaceAfter=0,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.4,
            textColor=colors.HexColor("#1d2a33"),
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName="Helvetica",
            fontSize=8.3,
            leading=10.1,
            leftIndent=10,
            firstLineIndent=-7,
            textColor=colors.HexColor("#1d2a33"),
        ),
        "ref_title": ParagraphStyle(
            "ref_title",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=10,
            textColor=colors.HexColor("#11344c"),
        ),
        "ref": ParagraphStyle(
            "ref",
            fontName="Helvetica",
            fontSize=6.6,
            leading=7.8,
            textColor=colors.HexColor("#42525d"),
        ),
    }

    c.setFillColor(colors.HexColor("#133c55"))
    c.roundRect(margin, page_h - margin - header_h, page_w - (2 * margin), header_h, 10, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin + 16, page_h - margin - 24, TITLE)
    c.setFont("Helvetica", 9.2)
    c.drawString(margin + 16, page_h - margin - 40, SUBTITLE)
    c.setFont("Helvetica", 7.6)
    c.drawRightString(page_w - margin - 16, page_h - margin - 40, "Generated 2026-03-18")

    left_items = []
    left_items.extend(section("What it is", [WHAT_IT_IS], styles["body"], styles["section"]))
    left_items.extend(section("Who it's for", [WHO_ITS_FOR], styles["body"], styles["section"]))
    left_items.extend(bullet_section("What it does", FEATURES, styles["bullet"], styles["section"]))

    right_items = []
    right_items.extend(bullet_section("How it works", ARCHITECTURE, styles["bullet"], styles["section"]))
    right_items.extend(bullet_section("How to run", RUN_STEPS, styles["bullet"], styles["section"]))

    left_box = KeepInFrame(col_w, col_h, left_items, mode="shrink")
    right_box = KeepInFrame(col_w, col_h, right_items, mode="shrink")
    _, left_h = left_box.wrapOn(c, col_w, col_h)
    _, right_h = right_box.wrapOn(c, col_w, col_h)
    left_box.drawOn(c, margin, top_y - left_h)
    right_box.drawOn(c, margin + col_w + gutter, top_y - right_h)

    refs_y = margin
    c.setFillColor(colors.HexColor("#f4f7f9"))
    c.roundRect(margin, refs_y, page_w - (2 * margin), refs_h, 8, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#11344c"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 12, refs_y + refs_h - 16, "Repo evidence index")

    ref_keys = list(REFS.keys())
    midpoint = (len(ref_keys) + 1) // 2
    left_refs = ref_keys[:midpoint]
    right_refs = ref_keys[midpoint:]

    ref_col_w = (page_w - (2 * margin) - 32 - gutter) / 2
    ref_col_h = refs_h - 28

    def ref_flow(keys: list[str]):
        items = []
        for key in keys:
            items.append(Paragraph(escape(f"{key}  {REFS[key]}"), styles["ref"]))
            items.append(Spacer(1, 2))
        return KeepInFrame(ref_col_w, ref_col_h, items, mode="shrink")

    left_ref_box = ref_flow(left_refs)
    right_ref_box = ref_flow(right_refs)
    _, left_ref_h = left_ref_box.wrapOn(c, ref_col_w, ref_col_h)
    _, right_ref_h = right_ref_box.wrapOn(c, ref_col_w, ref_col_h)
    left_ref_box.drawOn(c, margin + 12, refs_y + ref_col_h - left_ref_h + 8)
    right_ref_box.drawOn(c, margin + 12 + ref_col_w + gutter, refs_y + ref_col_h - right_ref_h + 8)

    c.save()


if __name__ == "__main__":
    build_pdf()

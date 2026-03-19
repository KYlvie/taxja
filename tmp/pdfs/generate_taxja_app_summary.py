from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(r"C:\Users\yk1e25\OneDrive - University of Southampton\Documents\kiro")
OUTPUT_PDF = ROOT / "output" / "pdf" / "taxja_app_summary.pdf"

PAGE_SIZE = landscape(A4)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
MARGIN_X = 34
MARGIN_TOP = 30
MARGIN_BOTTOM = 28
COLUMN_GAP = 18
HEADER_HEIGHT = 68
FOOTER_HEIGHT = 38

LEFT_COLUMN_X = MARGIN_X
INNER_WIDTH = PAGE_WIDTH - (MARGIN_X * 2)
COLUMN_WIDTH = (INNER_WIDTH - COLUMN_GAP) / 2
RIGHT_COLUMN_X = LEFT_COLUMN_X + COLUMN_WIDTH + COLUMN_GAP
COLUMN_TOP_Y = PAGE_HEIGHT - MARGIN_TOP - HEADER_HEIGHT
COLUMN_BOTTOM_Y = MARGIN_BOTTOM + FOOTER_HEIGHT

TITLE = "Taxja App Summary"
SUBTITLE = "One-page snapshot built from repo evidence only"

WHAT_IT_IS = (
    "Taxja is a full-stack Austrian tax management app with a React/Vite frontend "
    "and FastAPI backend. Repo evidence shows workflows for transactions, document "
    "OCR, properties/assets, tax calculations, reports, subscriptions, and an AI assistant."
)

WHO_ITS_FOR = (
    "Primary persona: Austrian taxpayers who want one place to manage receipts, "
    "transactions, documents, and tax outputs. README/HomePage explicitly call out "
    "employees, landlords, self-employed users, and small business owners."
)

FEATURES = [
    "Secure account flow with login/register, password reset, email verification, 2FA, profile, and admin pages.",
    "Dashboard with income/expense totals, estimated tax or refund, VAT signals, charts, quick actions, and suggestions.",
    "Transaction management with recurring items, recurring suggestions, and user classification rules.",
    "Document intake for JPG/PNG/PDF with OCR review/corrections, deduction tagging, and suggestion/auto-create flows.",
    "Property plus asset management with detail pages, portfolio/comparison views, recurring rent support, and tax-linked data.",
    "Reports and tax tools for EA, Bilanz, tax-form preview, trial balances, audit checklist, refund estimate, and what-if tools.",
    "Multilingual web/mobile-ready experience with subscription management and an AI assistant.",
]

ARCHITECTURE = [
    "React 18 + TypeScript frontend uses React Router, Zustand, Axios, i18next, and a Capacitor-aware mobile runtime.",
    "FastAPI exposes /api/v1 routes for auth, users, employer, transactions, properties, documents, dashboard, tax, reports, subscriptions, usage, admin, AI, and credits.",
    "PostgreSQL is the system of record via SQLAlchemy/Alembic; Redis supports cache, rate limiting, and Celery broker/backend; MinIO stores uploaded documents.",
    "Upload flow: frontend sends files to document endpoints; backend validates/deduplicates, stores bytes in MinIO, persists Document rows, and schedules OCR/pipeline work.",
    "Processing flow: the document pipeline downloads files, runs OCR/classification/extraction/validation, persists results, and can auto-create transactions, properties, assets, or recurring items.",
    "Optional AI flow: ChromaDB + SentenceTransformers RAG feeds provider-based assistant responses using OpenAI/Anthropic/local settings.",
]

RUN_STEPS = [
    "Install Docker Desktop, Python 3.11+, and Node.js 20+.",
    "From repo root run .\\start-dev.ps1 to start Postgres/Redis/MinIO, create the backend venv, install dependencies, and run Alembic migrations.",
    "Run .\\start-services.ps1 to launch backend (uvicorn) and frontend (npm run dev) with hot reload.",
    "Open http://localhost:5173 for the app and http://localhost:8000/docs for API docs.",
]

EVIDENCE = (
    "Evidence sampled: README.md; QUICK_START.md; docker-compose.yml; start-dev.ps1; "
    "start-services.ps1; backend/app/main.py; backend/app/api/v1/router.py; "
    "backend/app/api/v1/endpoints/documents.py; backend/app/services/document_pipeline_orchestrator.py; "
    "backend/app/services/storage_service.py; frontend/src/routes/index.tsx; "
    "frontend/src/mobile/runtime.ts; frontend/src/pages/HomePage.tsx."
)


PALETTE = {
    "ink": colors.HexColor("#0F172A"),
    "muted": colors.HexColor("#475569"),
    "accent": colors.HexColor("#1D4ED8"),
    "accent_fill": colors.HexColor("#EFF6FF"),
    "panel_fill": colors.HexColor("#F8FAFC"),
    "panel_border": colors.HexColor("#CBD5E1"),
    "rule": colors.HexColor("#DCE3EE"),
    "white": colors.white,
}


def wrap_lines(text: str, font_name: str, font_size: float, width: float) -> list[str]:
    return simpleSplit(text, font_name, font_size, width)


def box_height_for_paragraph(text: str, font_name: str, font_size: float, width: float, leading: float) -> float:
    return len(wrap_lines(text, font_name, font_size, width)) * leading


def box_height_for_bullets(items: list[str], font_name: str, font_size: float, width: float, leading: float, bullet_gap: float) -> float:
    total = 0.0
    bullet_width = 12
    for item in items:
        lines = wrap_lines(item, font_name, font_size, width - bullet_width)
        total += max(len(lines), 1) * leading + bullet_gap
    return total - bullet_gap if items else 0.0


def section_total_height(kind: str, content, scale: dict) -> float:
    heading_h = scale["section_heading"] + 8
    inner_w = COLUMN_WIDTH - 26
    if kind == "paragraph":
        body_h = box_height_for_paragraph(content, "Helvetica", scale["body"], inner_w, scale["leading"])
    else:
        body_h = box_height_for_bullets(content, "Helvetica", scale["body"], inner_w, scale["leading"], scale["bullet_gap"])
    return 14 + heading_h + body_h + 16


def layout_fits(scale: dict) -> bool:
    left_total = (
        section_total_height("paragraph", WHAT_IT_IS, scale)
        + section_total_height("paragraph", WHO_ITS_FOR, scale)
        + section_total_height("bullets", FEATURES, scale)
        + 18
    )
    right_total = (
        section_total_height("bullets", ARCHITECTURE, scale)
        + section_total_height("bullets", RUN_STEPS, scale)
        + 10
    )
    usable = COLUMN_TOP_Y - COLUMN_BOTTOM_Y
    return left_total <= usable and right_total <= usable


def pick_scale() -> dict:
    candidates = [
        {"body": 8.9, "leading": 11.0, "section_heading": 11.8, "bullet_gap": 2.4, "footer": 7.0},
        {"body": 8.7, "leading": 10.7, "section_heading": 11.5, "bullet_gap": 2.2, "footer": 6.8},
        {"body": 8.5, "leading": 10.4, "section_heading": 11.2, "bullet_gap": 2.0, "footer": 6.6},
        {"body": 8.3, "leading": 10.1, "section_heading": 11.0, "bullet_gap": 1.8, "footer": 6.4},
    ]
    for scale in candidates:
        if layout_fits(scale):
            return scale
    return candidates[-1]


def draw_header(pdf: canvas.Canvas) -> None:
    pdf.setFillColor(PALETTE["ink"])
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(MARGIN_X, PAGE_HEIGHT - MARGIN_TOP - 8, TITLE)

    pdf.setFillColor(PALETTE["muted"])
    pdf.setFont("Helvetica", 9.5)
    pdf.drawString(MARGIN_X, PAGE_HEIGHT - MARGIN_TOP - 28, SUBTITLE)

    pill_text = "Repo evidence only"
    pill_font = 8.8
    pill_padding_x = 8
    pill_w = stringWidth(pill_text, "Helvetica-Bold", pill_font) + pill_padding_x * 2
    pill_h = 20
    pill_x = PAGE_WIDTH - MARGIN_X - pill_w
    pill_y = PAGE_HEIGHT - MARGIN_TOP - 22
    pdf.setFillColor(PALETTE["accent_fill"])
    pdf.setStrokeColor(PALETTE["accent"])
    pdf.roundRect(pill_x, pill_y, pill_w, pill_h, 10, fill=1, stroke=0)
    pdf.setFillColor(PALETTE["accent"])
    pdf.setFont("Helvetica-Bold", pill_font)
    pdf.drawCentredString(pill_x + pill_w / 2, pill_y + 6.2, pill_text)

    rule_y = PAGE_HEIGHT - MARGIN_TOP - HEADER_HEIGHT + 8
    pdf.setStrokeColor(PALETTE["rule"])
    pdf.setLineWidth(1)
    pdf.line(MARGIN_X, rule_y, PAGE_WIDTH - MARGIN_X, rule_y)


def draw_section_box(pdf: canvas.Canvas, x: float, y_top: float, width: float, title: str, kind: str, content, scale: dict) -> float:
    inner_x = x + 13
    inner_w = width - 26
    heading_h = scale["section_heading"] + 8
    if kind == "paragraph":
        body_h = box_height_for_paragraph(content, "Helvetica", scale["body"], inner_w, scale["leading"])
    else:
        body_h = box_height_for_bullets(content, "Helvetica", scale["body"], inner_w, scale["leading"], scale["bullet_gap"])
    box_h = 14 + heading_h + body_h + 16
    y_bottom = y_top - box_h

    pdf.setFillColor(PALETTE["panel_fill"])
    pdf.setStrokeColor(PALETTE["panel_border"])
    pdf.roundRect(x, y_bottom, width, box_h, 10, fill=1, stroke=1)

    pdf.setFillColor(PALETTE["accent"])
    pdf.roundRect(x + 12, y_top - 20, 4, 12, 2, fill=1, stroke=0)

    pdf.setFillColor(PALETTE["ink"])
    pdf.setFont("Helvetica-Bold", scale["section_heading"])
    pdf.drawString(inner_x + 10, y_top - 17, title)

    body_y = y_top - 31
    pdf.setFillColor(PALETTE["ink"])
    pdf.setFont("Helvetica", scale["body"])

    if kind == "paragraph":
        for line in wrap_lines(content, "Helvetica", scale["body"], inner_w):
            pdf.drawString(inner_x, body_y, line)
            body_y -= scale["leading"]
    else:
        bullet_x = inner_x
        text_x = inner_x + 12
        text_w = inner_w - 12
        for item in content:
            lines = wrap_lines(item, "Helvetica", scale["body"], text_w)
            pdf.setFillColor(PALETTE["accent"])
            pdf.circle(bullet_x + 3.5, body_y + 2.2, 1.6, fill=1, stroke=0)
            pdf.setFillColor(PALETTE["ink"])
            for line_index, line in enumerate(lines):
                pdf.drawString(text_x, body_y, line)
                body_y -= scale["leading"]
            body_y -= scale["bullet_gap"]

    return y_bottom - 10


def draw_footer(pdf: canvas.Canvas, scale: dict) -> None:
    footer_y = MARGIN_BOTTOM + FOOTER_HEIGHT - 4
    pdf.setStrokeColor(PALETTE["rule"])
    pdf.setLineWidth(1)
    pdf.line(MARGIN_X, footer_y + 10, PAGE_WIDTH - MARGIN_X, footer_y + 10)

    pdf.setFillColor(PALETTE["muted"])
    pdf.setFont("Helvetica", scale["footer"])
    lines = wrap_lines(EVIDENCE, "Helvetica", scale["footer"], PAGE_WIDTH - (MARGIN_X * 2))
    current_y = footer_y
    for line in lines[:3]:
        pdf.drawString(MARGIN_X, current_y, line)
        current_y -= scale["footer"] + 2.2


def build_pdf() -> Path:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    scale = pick_scale()
    pdf = canvas.Canvas(str(OUTPUT_PDF), pagesize=PAGE_SIZE)
    pdf.setTitle(TITLE)
    pdf.setAuthor("OpenAI Codex")
    pdf.setSubject("Repo-based one-page summary of the Taxja app")

    draw_header(pdf)

    left_y = COLUMN_TOP_Y
    right_y = COLUMN_TOP_Y

    left_y = draw_section_box(pdf, LEFT_COLUMN_X, left_y, COLUMN_WIDTH, "What It Is", "paragraph", WHAT_IT_IS, scale)
    left_y = draw_section_box(pdf, LEFT_COLUMN_X, left_y, COLUMN_WIDTH, "Who It's For", "paragraph", WHO_ITS_FOR, scale)
    left_y = draw_section_box(pdf, LEFT_COLUMN_X, left_y, COLUMN_WIDTH, "What It Does", "bullets", FEATURES, scale)

    right_y = draw_section_box(pdf, RIGHT_COLUMN_X, right_y, COLUMN_WIDTH, "How It Works", "bullets", ARCHITECTURE, scale)
    right_y = draw_section_box(pdf, RIGHT_COLUMN_X, right_y, COLUMN_WIDTH, "How To Run", "bullets", RUN_STEPS, scale)

    draw_footer(pdf, scale)
    pdf.showPage()
    pdf.save()
    return OUTPUT_PDF


if __name__ == "__main__":
    output = build_pdf()
    print(output)

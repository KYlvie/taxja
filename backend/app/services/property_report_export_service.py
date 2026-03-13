"""
Property Report Export Service

Exports property reports to PDF and CSV formats.
Supports income statements and depreciation schedules.
"""

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


class PropertyReportExportService:
    """Service for exporting property reports to PDF and CSV formats"""

    # Translation dictionaries for multi-language support
    TRANSLATIONS = {
        "de": {
            "income_statement": "Einnahmen-Ausgaben-Rechnung",
            "depreciation_schedule": "AfA-Plan",
            "property_details": "Immobiliendetails",
            "address": "Adresse",
            "purchase_date": "Kaufdatum",
            "building_value": "Gebäudewert",
            "depreciation_rate": "AfA-Satz",
            "report_period": "Berichtszeitraum",
            "from": "Von",
            "to": "Bis",
            "income": "Einnahmen",
            "rental_income": "Mieteinnahmen",
            "total_income": "Gesamteinnahmen",
            "expenses": "Ausgaben",
            "expenses_by_category": "Ausgaben nach Kategorie",
            "total_expenses": "Gesamtausgaben",
            "net_income": "Nettoeinkommen",
            "year": "Jahr",
            "annual_depreciation": "Jährliche AfA",
            "accumulated_depreciation": "Kumulierte AfA",
            "remaining_value": "Restwert",
            "summary": "Zusammenfassung",
            "total_years": "Gesamtjahre",
            "years_elapsed": "Vergangene Jahre",
            "years_projected": "Projizierte Jahre",
            "years_remaining": "Verbleibende Jahre",
            "fully_depreciated_year": "Vollständig abgeschrieben im Jahr",
            "generated_on": "Erstellt am",
            "page": "Seite",
            "projected": "Projiziert",
            "actual": "Tatsächlich",
            "status": "Status",
            "sale_date": "Verkaufsdatum",
        },
        "en": {
            "income_statement": "Income Statement",
            "depreciation_schedule": "Depreciation Schedule",
            "property_details": "Property Details",
            "address": "Address",
            "purchase_date": "Purchase Date",
            "building_value": "Building Value",
            "depreciation_rate": "Depreciation Rate",
            "report_period": "Report Period",
            "from": "From",
            "to": "To",
            "income": "Income",
            "rental_income": "Rental Income",
            "total_income": "Total Income",
            "expenses": "Expenses",
            "expenses_by_category": "Expenses by Category",
            "total_expenses": "Total Expenses",
            "net_income": "Net Income",
            "year": "Year",
            "annual_depreciation": "Annual Depreciation",
            "accumulated_depreciation": "Accumulated Depreciation",
            "remaining_value": "Remaining Value",
            "summary": "Summary",
            "total_years": "Total Years",
            "years_elapsed": "Years Elapsed",
            "years_projected": "Years Projected",
            "years_remaining": "Years Remaining",
            "fully_depreciated_year": "Fully Depreciated Year",
            "generated_on": "Generated on",
            "page": "Page",
            "projected": "Projected",
            "actual": "Actual",
            "status": "Status",
            "sale_date": "Sale Date",
        },
    }

    def __init__(self, language: str = "de"):
        """
        Initialize export service.

        Args:
            language: Language code for translations (de, en)
        """
        self.language = language
        self.t = self.TRANSLATIONS.get(language, self.TRANSLATIONS["de"])

    def export_income_statement_pdf(self, report_data: Dict[str, Any]) -> bytes:
        """
        Export income statement to PDF format.

        Args:
            report_data: Income statement data from PropertyReportService

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        # Build PDF content
        story = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#1a1a1a"),
            spaceAfter=20,
            alignment=TA_CENTER,
        )
        story.append(Paragraph(self.t["income_statement"], title_style))
        story.append(Spacer(1, 0.5 * cm))

        # Property Details Section
        story.append(Paragraph(self.t["property_details"], styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))

        property_info = report_data["property"]
        property_data = [
            [self.t["address"], property_info["address"]],
            [self.t["purchase_date"], property_info["purchase_date"]],
            [
                self.t["building_value"],
                f"€ {property_info['building_value']:,.2f}",
            ],
        ]

        property_table = Table(property_data, colWidths=[6 * cm, 11 * cm])
        property_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(property_table)
        story.append(Spacer(1, 0.5 * cm))

        # Report Period
        period = report_data["period"]
        period_text = f"{self.t['report_period']}: {period['start_date']} {self.t['to']} {period['end_date']}"
        story.append(Paragraph(period_text, styles["Normal"]))
        story.append(Spacer(1, 0.5 * cm))

        # Income Section
        story.append(Paragraph(self.t["income"], styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))

        income_data = report_data["income"]
        income_table_data = [
            [self.t["rental_income"], f"€ {income_data['rental_income']:,.2f}"],
            [
                self.t["total_income"],
                f"€ {income_data['total_income']:,.2f}",
            ],
        ]

        income_table = Table(income_table_data, colWidths=[12 * cm, 5 * cm])
        income_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f4f8")),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#d0e8f0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 1), (1, 1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(income_table)
        story.append(Spacer(1, 0.5 * cm))

        # Expenses Section
        story.append(Paragraph(self.t["expenses"], styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))

        expenses_data = report_data["expenses"]
        expense_table_data = [[self.t["expenses_by_category"], ""]]

        # Add each expense category
        for category, amount in expenses_data["by_category"].items():
            expense_table_data.append([f"  {category}", f"€ {amount:,.2f}"])

        expense_table_data.append(
            [
                self.t["total_expenses"],
                f"€ {expenses_data['total_expenses']:,.2f}",
            ]
        )

        expense_table = Table(expense_table_data, colWidths=[12 * cm, 5 * cm])
        expense_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                    (
                        "BACKGROUND",
                        (0, -1),
                        (-1, -1),
                        colors.HexColor("#ffe0e0"),
                    ),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(expense_table)
        story.append(Spacer(1, 0.5 * cm))

        # Net Income
        net_income = report_data["net_income"]
        net_income_color = (
            colors.HexColor("#d4edda")
            if net_income >= 0
            else colors.HexColor("#f8d7da")
        )
        net_income_table = Table(
            [[self.t["net_income"], f"€ {net_income:,.2f}"]],
            colWidths=[12 * cm, 5 * cm],
        )
        net_income_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), net_income_color),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(net_income_table)

        # Footer
        story.append(Spacer(1, 1 * cm))
        footer_text = f"{self.t['generated_on']}: {date.today().isoformat()}"
        story.append(Paragraph(footer_text, styles["Normal"]))

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def export_depreciation_schedule_pdf(
        self, report_data: Dict[str, Any]
    ) -> bytes:
        """
        Export depreciation schedule to PDF format.

        Args:
            report_data: Depreciation schedule data from PropertyReportService

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        story = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#1a1a1a"),
            spaceAfter=20,
            alignment=TA_CENTER,
        )
        story.append(Paragraph(self.t["depreciation_schedule"], title_style))
        story.append(Spacer(1, 0.5 * cm))

        # Property Details
        story.append(Paragraph(self.t["property_details"], styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))

        property_info = report_data["property"]
        property_data = [
            [self.t["address"], property_info["address"]],
            [self.t["purchase_date"], property_info["purchase_date"]],
            [
                self.t["building_value"],
                f"€ {property_info['building_value']:,.2f}",
            ],
            [
                self.t["depreciation_rate"],
                f"{property_info['depreciation_rate'] * 100:.2f}%",
            ],
            [self.t["status"], property_info["status"]],
        ]

        if property_info.get("sale_date"):
            property_data.append(
                [self.t["sale_date"], property_info["sale_date"]]
            )

        property_table = Table(property_data, colWidths=[6 * cm, 11 * cm])
        property_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(property_table)
        story.append(Spacer(1, 0.5 * cm))

        # Depreciation Schedule Table
        story.append(
            Paragraph(self.t["depreciation_schedule"], styles["Heading2"])
        )
        story.append(Spacer(1, 0.3 * cm))

        # Table header
        schedule_data = [
            [
                self.t["year"],
                self.t["annual_depreciation"],
                self.t["accumulated_depreciation"],
                self.t["remaining_value"],
            ]
        ]

        # Add schedule rows
        for year_data in report_data["schedule"]:
            year_label = str(year_data["year"])
            if year_data["is_projected"]:
                year_label += f" ({self.t['projected']})"

            schedule_data.append(
                [
                    year_label,
                    f"€ {year_data['annual_depreciation']:,.2f}",
                    f"€ {year_data['accumulated_depreciation']:,.2f}",
                    f"€ {year_data['remaining_value']:,.2f}",
                ]
            )

        schedule_table = Table(
            schedule_data, colWidths=[3 * cm, 4.5 * cm, 4.5 * cm, 5 * cm]
        )

        # Style with alternating row colors
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a90e2")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]

        # Alternate row colors
        for i in range(1, len(schedule_data)):
            if i % 2 == 0:
                table_style.append(
                    ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f9f9f9"))
                )

        schedule_table.setStyle(TableStyle(table_style))
        story.append(schedule_table)
        story.append(Spacer(1, 0.5 * cm))

        # Summary Section
        story.append(Paragraph(self.t["summary"], styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))

        summary = report_data["summary"]
        summary_data = [
            [self.t["total_years"], str(summary["total_years"])],
            [self.t["years_elapsed"], str(summary["years_elapsed"])],
            [self.t["years_projected"], str(summary["years_projected"])],
            [
                self.t["accumulated_depreciation"],
                f"€ {summary['accumulated_depreciation']:,.2f}",
            ],
            [
                self.t["remaining_value"],
                f"€ {summary['remaining_value']:,.2f}",
            ],
        ]

        if summary.get("years_remaining"):
            summary_data.append(
                [
                    self.t["years_remaining"],
                    f"{summary['years_remaining']:.1f}",
                ]
            )

        if summary.get("fully_depreciated_year"):
            summary_data.append(
                [
                    self.t["fully_depreciated_year"],
                    str(summary["fully_depreciated_year"]),
                ]
            )

        summary_table = Table(summary_data, colWidths=[10 * cm, 7 * cm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(summary_table)

        # Footer
        story.append(Spacer(1, 1 * cm))
        footer_text = f"{self.t['generated_on']}: {date.today().isoformat()}"
        story.append(Paragraph(footer_text, styles["Normal"]))

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def export_income_statement_csv(self, report_data: Dict[str, Any]) -> str:
        """
        Export income statement to CSV format.

        Args:
            report_data: Income statement data from PropertyReportService

        Returns:
            CSV content as string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Property Details Header
        writer.writerow([self.t["property_details"]])
        writer.writerow([self.t["address"], report_data["property"]["address"]])
        writer.writerow(
            [self.t["purchase_date"], report_data["property"]["purchase_date"]]
        )
        writer.writerow(
            [
                self.t["building_value"],
                f"{report_data['property']['building_value']:.2f}",
            ]
        )
        writer.writerow([])

        # Report Period
        period = report_data["period"]
        writer.writerow(
            [
                self.t["report_period"],
                f"{period['start_date']} {self.t['to']} {period['end_date']}",
            ]
        )
        writer.writerow([])

        # Income Section
        writer.writerow([self.t["income"]])
        income_data = report_data["income"]
        writer.writerow(
            [self.t["rental_income"], f"{income_data['rental_income']:.2f}"]
        )
        writer.writerow(
            [self.t["total_income"], f"{income_data['total_income']:.2f}"]
        )
        writer.writerow([])

        # Expenses Section
        writer.writerow([self.t["expenses"]])
        writer.writerow([self.t["expenses_by_category"]])
        expenses_data = report_data["expenses"]
        for category, amount in expenses_data["by_category"].items():
            writer.writerow([category, f"{amount:.2f}"])
        writer.writerow(
            [self.t["total_expenses"], f"{expenses_data['total_expenses']:.2f}"]
        )
        writer.writerow([])

        # Net Income
        writer.writerow(
            [self.t["net_income"], f"{report_data['net_income']:.2f}"]
        )
        writer.writerow([])

        # Footer
        writer.writerow(
            [self.t["generated_on"], date.today().isoformat()]
        )

        return output.getvalue()

    def export_depreciation_schedule_csv(
        self, report_data: Dict[str, Any]
    ) -> str:
        """
        Export depreciation schedule to CSV format.

        Args:
            report_data: Depreciation schedule data from PropertyReportService

        Returns:
            CSV content as string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Property Details Header
        writer.writerow([self.t["property_details"]])
        writer.writerow([self.t["address"], report_data["property"]["address"]])
        writer.writerow(
            [self.t["purchase_date"], report_data["property"]["purchase_date"]]
        )
        writer.writerow(
            [
                self.t["building_value"],
                f"{report_data['property']['building_value']:.2f}",
            ]
        )
        writer.writerow(
            [
                self.t["depreciation_rate"],
                f"{report_data['property']['depreciation_rate'] * 100:.2f}%",
            ]
        )
        writer.writerow([self.t["status"], report_data["property"]["status"]])
        if report_data["property"].get("sale_date"):
            writer.writerow(
                [self.t["sale_date"], report_data["property"]["sale_date"]]
            )
        writer.writerow([])

        # Depreciation Schedule
        writer.writerow([self.t["depreciation_schedule"]])
        writer.writerow(
            [
                self.t["year"],
                self.t["annual_depreciation"],
                self.t["accumulated_depreciation"],
                self.t["remaining_value"],
                "Type",
            ]
        )

        for year_data in report_data["schedule"]:
            year_type = (
                self.t["projected"]
                if year_data["is_projected"]
                else self.t["actual"]
            )
            writer.writerow(
                [
                    year_data["year"],
                    f"{year_data['annual_depreciation']:.2f}",
                    f"{year_data['accumulated_depreciation']:.2f}",
                    f"{year_data['remaining_value']:.2f}",
                    year_type,
                ]
            )
        writer.writerow([])

        # Summary
        writer.writerow([self.t["summary"]])
        summary = report_data["summary"]
        writer.writerow([self.t["total_years"], summary["total_years"]])
        writer.writerow([self.t["years_elapsed"], summary["years_elapsed"]])
        writer.writerow([self.t["years_projected"], summary["years_projected"]])
        writer.writerow(
            [
                self.t["accumulated_depreciation"],
                f"{summary['accumulated_depreciation']:.2f}",
            ]
        )
        writer.writerow(
            [self.t["remaining_value"], f"{summary['remaining_value']:.2f}"]
        )

        if summary.get("years_remaining"):
            writer.writerow(
                [self.t["years_remaining"], f"{summary['years_remaining']:.1f}"]
            )

        if summary.get("fully_depreciated_year"):
            writer.writerow(
                [
                    self.t["fully_depreciated_year"],
                    summary["fully_depreciated_year"],
                ]
            )

        writer.writerow([])
        writer.writerow([self.t["generated_on"], date.today().isoformat()])

        return output.getvalue()

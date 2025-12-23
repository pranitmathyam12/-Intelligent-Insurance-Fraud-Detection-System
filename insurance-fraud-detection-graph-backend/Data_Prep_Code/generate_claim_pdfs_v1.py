# -*- coding: utf-8 -*-
"""
Generate realistic, type-specific insurance claim PDFs (modern corporate style)
with automatic pagination (no overflow) using ReportLab Platypus.

Output: Claim_Documents/<TRANSACTION_ID>_<type>.pdf

Run:  python generate_real_claims_platypus_v1_fixed.py
"""

import os
from pathlib import Path
from datetime import datetime
import pandas as pd

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, PageBreak
)
from reportlab.graphics.barcode import code128
from reportlab.pdfgen import canvas

# ----------------------------
# Config
# ----------------------------
INPUT_CSV = "insurance_data_enriched.csv"  # falls back to insurance_data.csv if not found
OUTPUT_DIR = "Claim_Documents"
NUM_ROWS = 10  # <— change this to control how many rows to render

# ----------------------------
# Styles
# ----------------------------
SS = getSampleStyleSheet()
H1 = ParagraphStyle(
    "H1",
    parent=SS["Heading1"],
    fontName="Helvetica-Bold",
    fontSize=14,
    leading=17,
    spaceAfter=8
)
H2 = ParagraphStyle(
    "H2",
    parent=SS["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=14,
    spaceBefore=10,
    spaceAfter=6,
    textTransform="uppercase",
)
LABEL = ParagraphStyle(
    "LABEL",
    parent=SS["Normal"],
    fontName="Helvetica-Bold",
    fontSize=8,
    textColor=colors.black,
    wordWrap="CJK",
    splitLongWords=True,
)

BODY = ParagraphStyle(
    "BODY",
    parent=SS["Normal"],
    fontName="Helvetica",
    fontSize=9.5,
    leading=12,
    wordWrap="CJK",
    splitLongWords=True,
)
SMALL = ParagraphStyle(
    "SMALL",
    parent=SS["Normal"],
    fontName="Helvetica-Oblique",
    fontSize=8,
    textColor=colors.grey
)

# ----------------------------
# Utilities
# ----------------------------
def val(rec, key, default=""):
    v = rec.get(key, default)
    if pd.isna(v):
        return default
    return v

def masked_last_n(v, n=4, bullet="•"):
    s = "" if v is None or pd.isna(v) else str(v)
    return s if len(s) <= n else (bullet * (len(s) - n)) + s[-n:]

def money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return str(v) or ""

def labeled_box(label_txt, value_txt, width=2.4*inch):
    """
    Renders a label above a single bordered "value" box.
    No KeepTogether so it can split across pages if needed.
    """
    label_p = Paragraph(label_txt or "", LABEL)
    value_p = Paragraph((value_txt or ""), BODY)

    t = Table(
        [[label_p],
         [value_p]],
        colWidths=[width]
    )
    t.setStyle(TableStyle([
        # label row padding – tight
        ("LEFTPADDING", (0,0), (-1,0), 0),
        ("RIGHTPADDING",(0,0), (-1,0), 0),
        ("TOPPADDING",  (0,0), (-1,0), 0),
        ("BOTTOMPADDING",(0,0),(-1,0), 2),

        # value row box + padding
        ("BOX", (0,1), (-1,1), 0.7, colors.black),
        ("LEFTPADDING", (0,1), (-1,1), 6),
        ("RIGHTPADDING",(0,1), (-1,1), 6),
        ("TOPPADDING",  (0,1), (-1,1), 6),
        ("BOTTOMPADDING",(0,1),(-1,1), 6),

        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("WORDWRAP", (0,0), (-1,-1), "CJK"),
    ]))
    return t

def hr(space_before=6, space_after=6, color=colors.lightgrey):
    tbl = Table([[""]], colWidths=[6.9*inch], rowHeights=[0.25])
    tbl.setStyle(TableStyle([("LINEABOVE", (0,0), (-1,-1), 1, color)]))
    return KeepTogether([Spacer(1, space_before), tbl, Spacer(1, space_after)])


def clip(s, max_chars=1200):
    s = "" if s is None else str(s)
    return s if len(s) <= max_chars else (s[:max_chars-1] + "…")

# ----------------------------
# Header / Footer
# ----------------------------
def draw_header_footer(title, txn):
    def _on_page(c: canvas.Canvas, doc):
        # Border
        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(1)
        c.rect(0.4*inch, 0.4*inch, LETTER[0]-0.8*inch, LETTER[1]-0.8*inch)

        # Header content
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.black)
        c.drawString(0.7*inch, LETTER[1]-0.8*inch, "ACME INSURANCE COMPANY")
        c.setFont("Helvetica", 9)
        c.drawString(0.7*inch, LETTER[1]-0.98*inch,
                     "1234 Claim St, Suite 500, Boston, MA 02110  |  (800) 555-0199  |  claims@acmeinsure.com")

        # Barcode
        bval = f"TXN-{txn}"
        bc = code128.Code128(bval, barHeight=0.35*inch, barWidth=0.7)
        bc.drawOn(c, LETTER[0]-2.8*inch, LETTER[1]-1.9*inch)
        c.setFont("Helvetica", 8)
        c.drawCentredString(LETTER[0]-1.8*inch, LETTER[1]-2.05*inch, bval)

        # Title
        c.setFont("Helvetica-Bold", 14)
        c.drawString(0.7*inch, LETTER[1]-1.6*inch, title)
        c.setFont("Helvetica", 9)
        c.drawString(0.7*inch, LETTER[1]-1.75*inch, "Please complete all sections. Use BLOCK letters.")

        # Footer
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.grey)
        c.drawString(0.7*inch, 0.55*inch, f"Digitally generated from claim dataset (TXN: {txn}).")
        c.drawRightString(LETTER[0]-0.7*inch, 0.55*inch, f"Page {doc.page}")

    return _on_page

# ----------------------------
# Common Sections
# ----------------------------
def section_policyholder(rec):
    a = labeled_box("Policy Number", str(val(rec, "POLICY_NUMBER")))
    b = labeled_box("Insurance Type", str(val(rec, "INSURANCE_TYPE")))
    row1 = Table([[a, b]], colWidths=[3.45*inch, 3.45*inch])
    row1.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
    r = [
        Paragraph("Policyholder Details", H2), hr(),
        row1, Spacer(1, 6),
        Table([[
            labeled_box("Customer Name", str(val(rec, "CUSTOMER_NAME")), width=5.15*inch),
            labeled_box("Customer ID", str(val(rec, "CUSTOMER_ID")), width=1.75*inch),
        ]], colWidths=[5.15*inch, 1.75*inch]),
        Spacer(1, 6),
    ]

    addr = ", ".join([str(val(rec, "ADDRESS_LINE1", "")),
                      str(val(rec, "ADDRESS_LINE2", "")),
                      str(val(rec, "CITY", "")),
                      str(val(rec, "STATE", "")),
                      str(val(rec, "POSTAL_CODE", ""))]).replace(" ,", "")
    r += [
        labeled_box("Mailing Address", addr, width=6.9*inch),
        Spacer(1, 6),
        Table([[
            labeled_box("SSN (Last 4)", masked_last_n(val(rec, "SSN"))),
            labeled_box("Marital Status", str(val(rec, "MARITAL_STATUS"))),
            labeled_box("Employment", str(val(rec, "EMPLOYMENT_STATUS")), width=2.1*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 4)
    ]
    return r

def section_incident_core(rec):
    rows = []
    rows += [
        Paragraph("Incident Information", H2), hr(),
        Table([[
            labeled_box("Date of Loss", str(val(rec, "LOSS_DT"))),
            labeled_box("Report Date", str(val(rec, "REPORT_DT"))),
            labeled_box("Incident Hour (24h)", str(val(rec, "INCIDENT_HOUR_OF_THE_DAY")), width=2.3*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 6),
        Table([[
            labeled_box("Incident City", str(val(rec, "INCIDENT_CITY"))),
            labeled_box("Incident State", str(val(rec, "INCIDENT_STATE"))),
            labeled_box("Incident Severity", str(val(rec, "INCIDENT_SEVERITY")), width=2.3*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 6),
    ]

    any_injury = "Yes" if bool(val(rec, "ANY_INJURY", 0)) else "No"
    police = "Yes" if bool(val(rec, "POLICE_REPORT_AVAILABLE", 0)) else "No"
    auth = str(val(rec, "AUTHORITY_CONTACTED", "")) or "—"
    rows += [
        Table([[
            labeled_box("Any Injury", any_injury),
            labeled_box("Police Report Available", police),
            labeled_box("Authority Contacted", auth, width=2.3*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 6),
    ]

    desc = clip(
        f"On {val(rec,'LOSS_DT')} around {val(rec,'INCIDENT_HOUR_OF_THE_DAY')}:00 in "
        f"{val(rec,'INCIDENT_CITY')}, {val(rec,'INCIDENT_STATE')}. "
        f"Severity: {val(rec,'INCIDENT_SEVERITY')}. Authority: {val(rec,'AUTHORITY_CONTACTED','—')}. "
        f"Police report: {police}. Reported: {val(rec,'REPORT_DT')}. Claimed: {money(val(rec,'CLAIM_AMOUNT'))}."
    )
    rows += [
        Paragraph("Description of Loss", H2), hr(),
        Table([[Paragraph(desc, BODY)]], colWidths=[6.9*inch]),
        Spacer(1, 6)
    ]
    return rows

def section_declaration():
    txt = ("I hereby certify that the information provided is true and accurate to the best of my knowledge. "
           "I understand that providing false or misleading information may result in denial of the claim and/or legal action.")
    tbl = Table([[Paragraph(txt, BODY)]], colWidths=[6.9*inch])
    return [
        Paragraph("Declaration", H2), hr(),
        tbl, Spacer(1, 8),
        Table([
            ["", ""],
            [Paragraph("<font size=8>Signature of Policyholder</font>", BODY),
             Paragraph("<font size=8>Date</font>", BODY)]
        ], colWidths=[3.45*inch, 3.45*inch], style=TableStyle([
            ("LINEABOVE", (0,0), (0,0), 0.7, colors.black),
            ("LINEABOVE", (1,0), (1,0), 0.7, colors.black),
            ("VALIGN", (0,0), (-1,-1), "BOTTOM"),
        ]))
    ]

def section_life(rec):
    return [
        Paragraph("Deceased & Beneficiary Details", H2), hr(),
        Table([[
            labeled_box("Deceased Name", str(val(rec, "CUSTOMER_NAME"))),
            labeled_box("Date of Death", str(val(rec, "DATE_OF_DEATH", val(rec,"LOSS_DT")))),
            labeled_box("Cause of Death", str(val(rec, "CAUSE_OF_DEATH", val(rec,"INCIDENT_SEVERITY"))), width=2.3*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 6),
        Table([[
            labeled_box("Primary Beneficiary", str(val(rec, "BENEFICIARY_NAME","")) , width=4.6*inch),
            labeled_box("Relationship", str(val(rec, "BENEFICIARY_RELATION","")), width=2.3*inch),
        ]], colWidths=[4.6*inch, 2.3*inch]),
        Spacer(1, 6),
        Paragraph("Claim & Payment", H2), hr(),
        Table([[
            labeled_box("Claim Amount (USD)", money(val(rec, "CLAIM_AMOUNT"))),
            labeled_box("Payout Method", str(val(rec, "PAYOUT_METHOD","Bank Transfer"))),
            labeled_box("Account (Last4)", masked_last_n(val(rec, "ACCT_NUMBER")), width=2.3*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 6)
    ]

def section_travel(rec):
    return [
        Paragraph("Travel & Itinerary", H2), hr(),
        Table([[
            labeled_box("Trip Start Date", str(val(rec, "TRIP_START_DT", val(rec,"POLICY_EFF_DT")))),
            labeled_box("Trip End Date", str(val(rec, "TRIP_END_DT", val(rec,"LOSS_DT")))),
            labeled_box("Destination", str(val(rec, "DESTINATION", val(rec,"INCIDENT_CITY"))), width=2.3*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 6),
        Table([[
            labeled_box("Covered Perils", str(val(rec, "COVERED_PERILS",
                                                 "Trip Cancellation / Baggage Loss / Medical")), width=4.6*inch),
            labeled_box("Flight/Booking Ref", str(val(rec, "FLIGHT_REF","")), width=2.3*inch),
        ]], colWidths=[4.6*inch, 2.3*inch]),
        Spacer(1, 6),
        Paragraph("Incident & Claim", H2), hr(),
        Table([[
            labeled_box("Loss Type", str(val(rec, "LOSS_TYPE", val(rec,"INCIDENT_SEVERITY")))),
            labeled_box("Claim Amount (USD)", money(val(rec,"CLAIM_AMOUNT"))),
            labeled_box("Police Report Available", "Yes" if bool(val(rec,"POLICE_REPORT_AVAILABLE",0)) else "No", width=2.3*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 6)
    ]

def section_property(rec):
    prop_addr = val(rec, "PROPERTY_ADDRESS",
                    ", ".join([str(val(rec,"ADDRESS_LINE1","")), str(val(rec,"CITY","")), str(val(rec,"STATE",""))]).replace(" ,",""))
    return [
        Paragraph("Property Details", H2), hr(),
        Table([[
            labeled_box("Property Address", prop_addr, width=4.6*inch),
            labeled_box("Property Type", str(val(rec, "PROPERTY_TYPE","Residential")), width=2.3*inch),
        ]], colWidths=[4.6*inch, 2.3*inch]),
        Spacer(1, 6),
        Table([[
            labeled_box("Damage Type", str(val(rec, "DAMAGE_TYPE", val(rec,"INCIDENT_SEVERITY")))),
            labeled_box("Estimated Repair Cost (USD)", money(val(rec, "EST_REPAIR_COST", val(rec,"CLAIM_AMOUNT")))),
            labeled_box("Authority Contacted", str(val(rec,"AUTHORITY_CONTACTED","—")), width=2.3*inch),
        ]], colWidths=[2.3*inch, 2.3*inch, 2.3*inch]),
        Spacer(1, 6),
        Paragraph("Incident Description", H2), hr(),
        Table([[Paragraph(
            f"Incident at {prop_addr} on {val(rec,'LOSS_DT')}. "
            f"Damage: {val(rec,'DAMAGE_TYPE', val(rec,'INCIDENT_SEVERITY'))}. "
            f"Claimed: {money(val(rec,'CLAIM_AMOUNT'))}. "
            f"Police report: {'Yes' if bool(val(rec,'POLICE_REPORT_AVAILABLE',0)) else 'No'}.",
            BODY)]], colWidths=[6.9*inch]),
        Spacer(1, 6)
    ]

def section_mobile(rec):
    return [
        Paragraph("Device & Purchase Details", H2), hr(),
        Table([[
            labeled_box("Device Make/Model", str(val(rec, "DEVICE_MODEL", val(rec,"DEVICE",""))), width=4.6*inch),
            labeled_box("IMEI/Serial (Last4)", masked_last_n(val(rec, "IMEI")), width=2.3*inch),
        ]], colWidths=[4.6*inch, 2.3*inch]),
                Spacer(1, 6),
        Table([[
            labeled_box("Incident Type", str(val(rec, "LOSS_TYPE", val(rec, "INCIDENT_SEVERITY")))),
            labeled_box("Proof of Purchase", str(val(rec, "PROOF_OF_PURCHASE", "Receipt Attached"))),
            labeled_box("Claim Amount (USD)", money(val(rec, "CLAIM_AMOUNT")), width=2.3 * inch),
        ]], colWidths=[2.3 * inch, 2.3 * inch, 2.3 * inch]),
        Spacer(1, 6),
        Paragraph("Incident Description", H2), hr(),
        Table([[Paragraph(
            f"Device incident on {val(rec, 'LOSS_DT')} in {val(rec, 'INCIDENT_CITY')}. "
            f"Type: {val(rec, 'LOSS_TYPE', '')}. "
            f"Claimed: {money(val(rec, 'CLAIM_AMOUNT'))}. "
            f"Reported: {val(rec, 'REPORT_DT')}.", BODY)]], colWidths=[6.9 * inch]),
        Spacer(1, 6)
    ]

# ----------------------------
# Build story by type
# ----------------------------
def build_story(rec):
    ins_type = str(val(rec, "INSURANCE_TYPE", "General")).strip().title()
    story = []

    # Policyholder + incident core (consistent baseline)
    story += section_policyholder(rec)
    story += section_incident_core(rec)

    # Type-specific flavor
    if ins_type == "Life":
        story += section_life(rec)
    elif ins_type == "Travel":
        story += section_travel(rec)
    elif ins_type == "Property":
        story += section_property(rec)
    elif ins_type == "Mobile":
        story += section_mobile(rec)
    else:
        story.append(Paragraph("Additional Details", H2))
        story.append(hr())
        story.append(Paragraph("No additional type-specific fields available.", BODY))

    # Declaration at the end
    story += section_declaration()

    return story, f"{ins_type.upper()} CLAIM FORM"

# ----------------------------
# Main
# ----------------------------
def main(num_rows=NUM_ROWS):
    in_path = Path(INPUT_CSV)
    if not in_path.exists():
        alt = Path("insurance_data.csv")
        if alt.exists():
            in_path = alt
        else:
            raise FileNotFoundError(f"Could not find '{INPUT_CSV}' or 'insurance_data.csv'")

    df = pd.read_csv(in_path)
    if "INSURANCE_TYPE" in df.columns:
        df["INSURANCE_TYPE"] = df["INSURANCE_TYPE"].astype(str).str.title()

    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    for _, row in df.head(num_rows).iterrows():
        rec = row.to_dict()
        txn = val(rec, "TRANSACTION_ID", "UNKNOWN")
        story, title = build_story(rec)

        filename = f"{txn}_{str(val(rec, 'INSURANCE_TYPE', 'general')).lower()}.pdf"
        full_path = out_dir / filename

        doc = SimpleDocTemplate(
            str(full_path),
            pagesize=LETTER,
            leftMargin=0.7 * inch,
            rightMargin=0.7 * inch,
            topMargin=2.0 * inch,   # balanced header space
            bottomMargin=1.0 * inch # balanced footer space
        )

        onpage = draw_header_footer(title, txn)
        doc.build(story, onFirstPage=onpage, onLaterPages=onpage)
        print(f"✅ Wrote {full_path}")

if __name__ == "__main__":
    main()
    
    def generate_one_claim(txn_id):
    """Generate exactly one claim PDF by TRANSACTION_ID."""
    in_path = Path(INPUT_CSV)
    df = pd.read_csv(in_path)

    row = df[df["TRANSACTION_ID"] == txn_id]
    if row.empty:
        print(f"❌ No transaction found with ID {txn_id}")
        return

    rec = row.iloc[0].to_dict()
    story, title = build_story(rec)

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    pdf_path = Path(OUTPUT_DIR) / f"{txn_id}.pdf"

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=2.0 * inch,
        bottomMargin=1.0 * inch,
    )

    onpage = draw_header_footer(title, txn_id)
    doc.build(story, onFirstPage=onpage, onLaterPages=onpage)
    print(f"✅ Wrote {pdf_path}")
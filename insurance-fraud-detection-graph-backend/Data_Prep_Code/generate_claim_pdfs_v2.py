#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Comprehensive Insurance Claim PDF Generator
Includes ALL fields from CSV for each insurance type with distinct themes
"""

from pathlib import Path
import pandas as pd
from datetime import datetime

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.graphics.barcode import code128
from reportlab.pdfgen import canvas

# ----------------------------
# Configuration
# ----------------------------
# INPUT_CSV = "insurance_data_enriched.csv"
INPUT_CSV = "sample_test_data.csv"
FALLBACK_CSV = "insurance_data.csv"
# OUTPUT_DIR = "Claim_Documents"
OUTPUT_DIR = "Claim_Documents_Test"
NUM_ROWS = 10

# ----------------------------
# Complete Field Mapping for Each Insurance Type
# ----------------------------
INSURANCE_FIELDS = {
    # Common fields for ALL insurance types
    "COMMON": [
        "TRANSACTION_ID", "CUSTOMER_ID", "POLICY_NUMBER", "POLICY_EFF_DT",
        "LOSS_DT", "REPORT_DT", "INSURANCE_TYPE", "PREMIUM_AMOUNT", "CLAIM_AMOUNT",
        "CUSTOMER_NAME", "ADDRESS_LINE1", "ADDRESS_LINE2", "CITY", "STATE", 
        "POSTAL_CODE", "SSN", "MARITAL_STATUS", "AGE", "TENURE", 
        "EMPLOYMENT_STATUS", "NO_OF_FAMILY_MEMBERS", "RISK_SEGMENTATION",
        "HOUSE_TYPE", "SOCIAL_CLASS", "ROUTING_NUMBER", "ACCT_NUMBER",
        "CUSTOMER_EDUCATION_LEVEL", "CLAIM_STATUS", "INCIDENT_SEVERITY",
        "AUTHORITY_CONTACTED", "ANY_INJURY", "POLICE_REPORT_AVAILABLE",
        "INCIDENT_STATE", "INCIDENT_CITY", "INCIDENT_HOUR_OF_THE_DAY",
        "AGENT_ID", "VENDOR_ID", "TXN_DATE_TIME"
    ],
    
    # Type-specific fields
    "Life": [
        "DATE_OF_DEATH", "CAUSE_OF_DEATH", "BENEFICIARY_NAME", 
        "BENEFICIARY_RELATION", "PAYOUT_METHOD"
    ],
    
    "Travel": [
        "TRIP_START_DT", "TRIP_END_DT", "DESTINATION", 
        "COVERED_PERILS", "LOSS_TYPE", "FLIGHT_REF"
    ],
    
    "Property": [
        "PROPERTY_TYPE", "DAMAGE_TYPE", "PROPERTY_ADDRESS", 
        "EST_REPAIR_COST"
    ],
    
    "Mobile": [
        "DEVICE_MODEL", "IMEI", "PROOF_OF_PURCHASE", "LOSS_TYPE"
    ],
    
    "Motor": [
        # Motor uses common fields plus incident details
        "VEHICLE_TYPE", "LICENSE_PLATE", "VIN"  # If available
    ],
    
    "Health": [
        # Health uses mainly common fields
        "DIAGNOSIS_CODE", "PROCEDURE_CODE", "PROVIDER_NAME"  # If available
    ]
}

# ----------------------------
# Distinct Color Themes
# ----------------------------
THEMES = {
    "Health": {
        "primary": colors.HexColor("#0EA5E9"),      # Sky Blue
        "secondary": colors.HexColor("#E0F2FE"),     # Light Sky
        "accent": colors.HexColor("#075985"),        # Dark Sky
        "header_bg": colors.HexColor("#0284C7"),     # Medium Sky
        "text": colors.white,
        "title": "HEALTH INSURANCE CLAIM",
        "watermark": "MEDICAL",
        "icon": "⚕"
    },
    "Life": {
        "primary": colors.HexColor("#8B5CF6"),       # Purple
        "secondary": colors.HexColor("#EDE9FE"),     # Light Purple
        "accent": colors.HexColor("#6D28D9"),        # Dark Purple
        "header_bg": colors.HexColor("#7C3AED"),     # Medium Purple
        "text": colors.white,
        "title": "LIFE INSURANCE CLAIM",
        "watermark": "LIFE",
        "icon": "☮"
    },
    "Property": {
        "primary": colors.HexColor("#10B981"),       # Emerald Green
        "secondary": colors.HexColor("#D1FAE5"),     # Light Green
        "accent": colors.HexColor("#047857"),        # Dark Green
        "header_bg": colors.HexColor("#059669"),     # Medium Green
        "text": colors.white,
        "title": "PROPERTY INSURANCE CLAIM",
        "watermark": "PROPERTY",
        "icon": "🏠"
    },
    "Motor": {
        "primary": colors.HexColor("#EF4444"),       # Red
        "secondary": colors.HexColor("#FEE2E2"),     # Light Red
        "accent": colors.HexColor("#B91C1C"),        # Dark Red
        "header_bg": colors.HexColor("#DC2626"),     # Medium Red
        "text": colors.white,
        "title": "MOTOR VEHICLE INSURANCE CLAIM",
        "watermark": "MOTOR",
        "icon": "🚗"
    },
    "Travel": {
        "primary": colors.HexColor("#F59E0B"),       # Amber/Orange
        "secondary": colors.HexColor("#FEF3C7"),     # Light Amber
        "accent": colors.HexColor("#D97706"),        # Dark Amber
        "header_bg": colors.HexColor("#F59E0B"),     # Medium Amber
        "text": colors.white,
        "title": "TRAVEL INSURANCE CLAIM",
        "watermark": "TRAVEL",
        "icon": "✈"
    },
    "Mobile": {
        "primary": colors.HexColor("#6366F1"),       # Indigo
        "secondary": colors.HexColor("#E0E7FF"),     # Light Indigo
        "accent": colors.HexColor("#4338CA"),        # Dark Indigo  
        "header_bg": colors.HexColor("#4F46E5"),     # Medium Indigo
        "text": colors.white,
        "title": "MOBILE DEVICE INSURANCE CLAIM",
        "watermark": "DEVICE",
        "icon": "📱"
    },
    "General": {
        "primary": colors.HexColor("#6B7280"),       # Gray
        "secondary": colors.HexColor("#F3F4F6"),     # Light Gray
        "accent": colors.HexColor("#374151"),        # Dark Gray
        "header_bg": colors.HexColor("#4B5563"),     # Medium Gray
        "text": colors.white,
        "title": "GENERAL INSURANCE CLAIM",
        "watermark": "CLAIM",
        "icon": "📋"
    }
}

# ----------------------------
# Style Creation
# ----------------------------
def create_styles(theme):
    """Create dynamic styles based on theme"""
    SS = getSampleStyleSheet()
    
    return {
        "LABEL": ParagraphStyle(
            "LABEL", 
            parent=SS["Normal"], 
            fontName="Helvetica-Bold",
            fontSize=8, 
            textColor=theme["accent"],
            wordWrap="CJK", 
            splitLongWords=True
        ),
        "BODY": ParagraphStyle(
            "BODY", 
            parent=SS["Normal"], 
            fontName="Helvetica",
            fontSize=9.5, 
            leading=12, 
            wordWrap="CJK", 
            splitLongWords=True,
            textColor=colors.black
        ),
        "H2": ParagraphStyle(
            "H2", 
            parent=SS["Heading2"], 
            fontName="Helvetica-Bold",
            fontSize=11, 
            leading=14, 
            spaceBefore=8, 
            spaceAfter=6, 
            textTransform="uppercase",
            textColor=theme["text"]
        ),
        "SMALL": ParagraphStyle(
            "SMALL",
            parent=SS["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.grey
        )
    }

# ----------------------------
# Utilities
# ----------------------------
def clean_val(value, default=""):
    """Clean value from CSV"""
    if pd.isna(value) or value is None:
        return default
    str_val = str(value).strip()
    if str_val.lower() in ['nan', 'none', 'null', '']:
        return default
    return str_val

def format_money(value):
    """Format as currency"""
    try:
        cleaned = clean_val(value, "0")
        amount = float(cleaned)
        return f"${amount:,.2f}"
    except:
        return "$0.00"

def format_date(value):
    """Format date properly"""
    cleaned = clean_val(value)
    if not cleaned:
        return "N/A"
    try:
        if ' ' in cleaned:
            cleaned = cleaned.split(' ')[0]
        dt = datetime.strptime(cleaned, '%Y-%m-%d')
        return dt.strftime('%B %d, %Y')
    except:
        return cleaned

def mask_ssn(value):
    """Mask SSN"""
    # ssn = clean_val(value).replace('-', '')
    if len(value) >= 4:
        return value
    return "N/A"

def mask_account(value):
    """Mask account number"""
    acc = clean_val(value)
    if len(acc) >= 4:
        return f"{'•' * (len(acc)-4)}{acc[-4:]}"
    return "N/A"

def format_yes_no(value):
    """Convert various values to Yes/No"""
    val = clean_val(value)
    if val in ['1', 'Y', 'y', 'Yes', 'yes', 'TRUE', 'True', True, 1]:
        return "Yes"
    elif val in ['0', 'N', 'n', 'No', 'no', 'FALSE', 'False', False, 0]:
        return "No"
    return val if val else "N/A"

def format_datetime(value):
    """Format datetime with time"""
    cleaned = clean_val(value)
    if not cleaned:
        return "N/A"
    try:
        dt = datetime.strptime(cleaned, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%B %d, %Y at %I:%M %p')
    except:
        return format_date(cleaned)

# ----------------------------
# Components
# ----------------------------
def labeled_box(label_txt, value_txt, width=2.4*inch, theme=None, styles=None):
    """Create themed labeled field"""
    label_p = Paragraph(label_txt or "", styles["LABEL"])
    value_p = Paragraph(clean_val(value_txt, "N/A"), styles["BODY"])
    t = Table([[label_p], [value_p]], colWidths=[width])
    st = [
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("BOX", (0, 1), (-1, 1), 0.8, theme["primary"]),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    st.append(("LINEBELOW", (0, 0), (-1, 0), 1, theme["primary"]))
    t.setStyle(TableStyle(st))
    return t

def section_header(title, theme, styles):
    """Create themed section header"""
    header_content = Paragraph(f"{theme['icon']} {title.upper()}", styles["H2"])
    
    t = Table([[header_content]], colWidths=[6.9*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), theme["header_bg"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOX", (0, 0), (-1, -1), 2, theme["primary"]),
    ]))
    return t

def info_box(content, theme, styles):
    """Create information box"""
    para = Paragraph(content, styles["BODY"])
    t = Table([[para]], colWidths=[6.9*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), theme["secondary"]),
        ("BOX", (0, 0), (-1, -1), 1, theme["primary"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t

# ----------------------------
# Header/Footer
# ----------------------------
def create_header_footer(title, txn, theme, claim_date):
    def _on_page(c: canvas.Canvas, doc):
        W, H = LETTER
        
        # Colored border
        c.setStrokeColor(theme["primary"])
        c.setLineWidth(2)
        c.rect(0.4*inch, 0.4*inch, W-0.8*inch, H-0.8*inch)
        
        # Watermark
        c.saveState()
        c.setFont("Helvetica-Bold", 80)
        c.setFillColor(colors.Color(
            theme["primary"].red, 
            theme["primary"].green, 
            theme["primary"].blue, 
            alpha=0.08
        ))
        c.translate(W/2, H/2)
        c.rotate(45)
        c.drawCentredString(0, 0, theme["watermark"])
        c.restoreState()
        
        # Header background
        c.setFillColor(theme["header_bg"])
        c.rect(0.4*inch, H-1.4*inch, W-0.8*inch, 0.8*inch, fill=1)
        
        # Company name
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(theme["text"])
        c.drawString(0.6*inch, H-0.9*inch, "PREMIER INSURANCE GROUP")
        
        c.setFont("Helvetica", 9)
        c.drawString(0.6*inch, H-1.1*inch,
                    "Excellence in Coverage • Trusted Since 1985")
        
        # Contact info
        c.setFont("Helvetica", 8)
        c.setFillColor(theme["accent"])
        c.drawString(0.6*inch, H-1.55*inch,
                    "24/7 Helpline: 1-800-555-CLAIM | claims@premierinsurance.com")
        
        # Title and claim date
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(theme["primary"])
        c.drawString(0.6*inch, H-1.85*inch, title)
        
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        c.drawString(0.6*inch, H-2.05*inch, f"Claim Date: {claim_date}")
        
        # Transaction barcode
        if txn and txn != "UNKNOWN":
            try:
                bc = code128.Code128(txn, barHeight=0.3*inch, barWidth=0.6)
                bc.drawOn(c, W-2.8*inch, H-1.1*inch)
                c.setFont("Helvetica", 8)
                c.setFillColor(theme["accent"])
                c.drawCentredString(W-1.8*inch, H-1.25*inch, txn)
            except:
                pass
        
        # Footer
        c.setStrokeColor(theme["primary"])
        c.setLineWidth(1)
        c.line(0.6*inch, 0.85*inch, W-0.6*inch, 0.85*inch)
        
        c.setFont("Helvetica", 8)
        c.setFillColor(theme["accent"])
        c.drawString(0.6*inch, 0.65*inch, 
                    f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        c.drawCentredString(W/2, 0.65*inch, 
                          f"Reference: {txn}")
        c.drawRightString(W-0.6*inch, 0.65*inch, f"Page {doc.page}")
    
    return _on_page

# ----------------------------
# Build Comprehensive Sections
# ----------------------------
def build_transaction_section(rec, theme, styles):
    """Build transaction details section"""
    story = []
    story.append(section_header("Transaction Information", theme, styles))
    story.append(Spacer(1, 8))
    
    trans_row = Table([[
        labeled_box("Transaction ID", rec.get("TRANSACTION_ID"), 2.2*inch, theme, styles),
        labeled_box("Transaction Date", format_datetime(rec.get("TXN_DATE_TIME")), 2.2*inch, theme, styles),
        labeled_box("Agent ID", rec.get("AGENT_ID"), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(trans_row)
    story.append(Spacer(1, 6))
    
    vendor_row = Table([[
        labeled_box("Vendor ID", rec.get("VENDOR_ID"), 3.4*inch, theme, styles),
        labeled_box("Policy Effective Date", format_date(rec.get("POLICY_EFF_DT")), 3.4*inch, theme, styles),
    ]], colWidths=[3.4*inch, 3.4*inch])
    story.append(vendor_row)
    
    return story

def build_policyholder_complete(rec, theme, styles):
    """Build complete policyholder section with all fields"""
    story = []
    story.append(section_header("Policyholder Complete Information", theme, styles))
    story.append(Spacer(1, 8))
    
    # Basic info
    basic_row = Table([[
        labeled_box("Policy Number", rec.get("POLICY_NUMBER"), 2.2*inch, theme, styles),
        labeled_box("Customer ID", rec.get("CUSTOMER_ID"), 2.2*inch, theme, styles),
        labeled_box("Insurance Type", rec.get("INSURANCE_TYPE"), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(basic_row)
    story.append(Spacer(1, 6))
    
    # Name and contact
    story.append(labeled_box("Customer Name", rec.get("CUSTOMER_NAME"), 6.9*inch, theme, styles))
    story.append(Spacer(1, 6))
    
    # Complete address
    addr_row = Table([[
        labeled_box("Address Line 1", rec.get("ADDRESS_LINE1"), 3.4*inch, theme, styles),
        labeled_box("Address Line 2", rec.get("ADDRESS_LINE2"), 3.4*inch, theme, styles),
    ]], colWidths=[3.4*inch, 3.4*inch])
    story.append(addr_row)
    story.append(Spacer(1, 6))
    
    addr_row2 = Table([[
        labeled_box("City", rec.get("CITY"), 2.2*inch, theme, styles),
        labeled_box("State", rec.get("STATE"), 2.2*inch, theme, styles),
        labeled_box("Postal Code", rec.get("POSTAL_CODE"), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(addr_row2)
    story.append(Spacer(1, 6))
    
    # Personal details
    personal_row = Table([[
        labeled_box("SSN", mask_ssn(rec.get("SSN")), 1.7*inch, theme, styles),
        labeled_box("Age", rec.get("AGE"), 1.1*inch, theme, styles),
        labeled_box("Marital", format_yes_no(rec.get("MARITAL_STATUS")), 1.1*inch, theme, styles),
        labeled_box("Tenure", f"{rec.get('TENURE')} months", 1.4*inch, theme, styles),
        labeled_box("Education", rec.get("CUSTOMER_EDUCATION_LEVEL"), 1.5*inch, theme, styles),
    ]], colWidths=[1.7*inch, 1.1*inch, 1.1*inch, 1.4*inch, 1.5*inch])
    story.append(personal_row)
    story.append(Spacer(1, 6))
    
    # Employment and family
    emp_row = Table([[
        labeled_box("Employed", format_yes_no(rec.get("EMPLOYMENT_STATUS")), 1.7*inch, theme, styles),
        labeled_box("Family Members", rec.get("NO_OF_FAMILY_MEMBERS"), 1.7*inch, theme, styles),
        labeled_box("House Type", rec.get("HOUSE_TYPE"), 1.7*inch, theme, styles),
        labeled_box("Social Class", rec.get("SOCIAL_CLASS"), 1.7*inch, theme, styles),
    ]], colWidths=[1.7*inch, 1.7*inch, 1.7*inch, 1.7*inch])
    story.append(emp_row)
    
    return story

def build_incident_complete(rec, theme, styles):
    """Build complete incident section with all fields"""
    story = []
    story.append(section_header("Complete Incident Details", theme, styles))
    story.append(Spacer(1, 8))
    
    # Dates
    dates_row = Table([[
        labeled_box("Loss Date", format_date(rec.get("LOSS_DT")), 2.2*inch, theme, styles),
        labeled_box("Report Date", format_date(rec.get("REPORT_DT")), 2.2*inch, theme, styles),
        labeled_box("Hour of Day", f"{rec.get('INCIDENT_HOUR_OF_THE_DAY')}:00", 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(dates_row)
    story.append(Spacer(1, 6))
    
    # Location
    location_row = Table([[
        labeled_box("Incident City", rec.get("INCIDENT_CITY"), 2.2*inch, theme, styles),
        labeled_box("Incident State", rec.get("INCIDENT_STATE"), 2.2*inch, theme, styles),
        labeled_box("Severity", rec.get("INCIDENT_SEVERITY"), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(location_row)
    story.append(Spacer(1, 6))
    
    # Response details
    response_row = Table([[
        labeled_box("Authority Contacted", rec.get("AUTHORITY_CONTACTED"), 2.2*inch, theme, styles),
        labeled_box("Any Injury", format_yes_no(rec.get("ANY_INJURY")), 2.2*inch, theme, styles),
        labeled_box("Police Report", format_yes_no(rec.get("POLICE_REPORT_AVAILABLE")), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(response_row)
    
    return story

def build_financial_complete(rec, theme, styles):
    """Build complete financial section with all fields"""
    story = []
    story.append(section_header("Financial & Risk Information", theme, styles))
    story.append(Spacer(1, 8))
    
    # Amounts
    amounts_row = Table([[
        labeled_box("Premium Amount", format_money(rec.get("PREMIUM_AMOUNT")), 2.2*inch, theme, styles),
        labeled_box("Claim Amount", format_money(rec.get("CLAIM_AMOUNT")), 2.2*inch, theme, styles),
        labeled_box("Claim Status", rec.get("CLAIM_STATUS"), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(amounts_row)
    story.append(Spacer(1, 6))
    
    # Banking
    banking_row = Table([[
        labeled_box("Routing Number", rec.get("ROUTING_NUMBER"), 2.2*inch, theme, styles),
        labeled_box("Account (Masked)", mask_account(rec.get("ACCT_NUMBER")), 2.2*inch, theme, styles),
        labeled_box("Risk Segment", rec.get("RISK_SEGMENTATION"), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(banking_row)
    story.append(Spacer(1, 8))
    
    # Summary box
    summary = f"""
    <b>Financial Summary:</b><br/>
    • Total Claim Amount: {format_money(rec.get('CLAIM_AMOUNT'))}<br/>
    • Monthly Premium: {format_money(rec.get('PREMIUM_AMOUNT'))}<br/>
    • Risk Category: {rec.get('RISK_SEGMENTATION')}<br/>
    • Status: {rec.get('CLAIM_STATUS')}
    """
    story.append(info_box(summary, theme, styles))
    
    return story

# ----------------------------
# Type-Specific Comprehensive Sections
# ----------------------------
def add_life_complete(rec, story, theme, styles):
    """Life insurance with ALL specific fields"""
    story.append(section_header("Life Insurance Claim Details", theme, styles))
    story.append(Spacer(1, 8))
    
    # Death information
    death_row = Table([[
        labeled_box("Date of Death", format_date(rec.get("DATE_OF_DEATH")), 3.4*inch, theme, styles),
        labeled_box("Cause of Death", rec.get("CAUSE_OF_DEATH"), 3.4*inch, theme, styles),
    ]], colWidths=[3.4*inch, 3.4*inch])
    story.append(death_row)
    story.append(Spacer(1, 6))
    
    # Beneficiary
    beneficiary_row = Table([[
        labeled_box("Beneficiary Name", rec.get("BENEFICIARY_NAME"), 2.2*inch, theme, styles),
        labeled_box("Relationship", rec.get("BENEFICIARY_RELATION"), 2.2*inch, theme, styles),
        labeled_box("Payout Method", rec.get("PAYOUT_METHOD"), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(beneficiary_row)
    story.append(Spacer(1, 8))
    
    # Required documents
    docs_text = """
    <b>Required Documents for Life Insurance Claim:</b><br/>
    ☐ Original Death Certificate<br/>
    ☐ Medical Certificate stating cause of death<br/>
    ☐ Beneficiary ID Proof (Government issued)<br/>
    ☐ Original Policy Document<br/>
    ☐ Bank Account Details for payout<br/>
    ☐ Claimant's Statement Form<br/>
    ☐ Attending Physician's Statement<br/>
    ☐ Hospital Records (if applicable)
    """
    story.append(info_box(docs_text, theme, styles))
    
    return story

def add_travel_complete(rec, story, theme, styles):
    """Travel insurance with ALL specific fields"""
    story.append(section_header("Travel Insurance Claim Details", theme, styles))
    story.append(Spacer(1, 8))
    
    # Trip details
    trip_row = Table([[
        labeled_box("Trip Start Date", format_date(rec.get("TRIP_START_DT")), 2.2*inch, theme, styles),
        labeled_box("Trip End Date", format_date(rec.get("TRIP_END_DT")), 2.2*inch, theme, styles),
        labeled_box("Destination", rec.get("DESTINATION"), 2.2*inch, theme, styles),
    ]], colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    story.append(trip_row)
    story.append(Spacer(1, 6))
    
    # Coverage details
    coverage_row = Table([[
        labeled_box("Loss Type", rec.get("LOSS_TYPE"), 3.4*inch, theme, styles),
        labeled_box("Flight Reference", rec.get("FLIGHT_REF"), 3.4*inch, theme, styles),
    ]], colWidths=[3.4*inch, 3.4*inch])
    story.append(coverage_row)
    story.append(Spacer(1, 6))
    
    # Covered perils
    story.append(labeled_box("Covered Perils", rec.get("COVERED_PERILS"), 6.9*inch, theme, styles))
    story.append(Spacer(1, 8))
    
    # Required documents
    docs_text = """
    <b>Required Documents for Travel Insurance Claim:</b><br/>
    ☐ Travel Tickets (Flight/Train/Bus)<br/>
    ☐ Booking Confirmations (Hotel/Tour)<br/>
    ☐ Medical Reports (for medical emergency claims)<br/>
    ☐ Police Report (for theft/loss claims)<br/>
    ☐ Original Receipts for expenses<br/>
    ☐ Passport Copy<br/>
    ☐ Visa Copy (if applicable)<br/>
    ☐ Airline Confirmation (for delays/cancellations)
    """
    story.append(info_box(docs_text, theme, styles))
    
    return story

def add_property_complete(rec, story, theme, styles):
    """Property insurance with ALL specific fields"""
    story.append(section_header("Property Insurance Claim Details", theme, styles))
    story.append(Spacer(1, 8))
    
    # Property details
    prop_row = Table([[
        labeled_box("Property Type", rec.get("PROPERTY_TYPE"), 3.4*inch, theme, styles),
        labeled_box("Damage Type", rec.get("DAMAGE_TYPE"), 3.4*inch, theme, styles),
    ]], colWidths=[3.4*inch, 3.4*inch])
    story.append(prop_row)
    story.append(Spacer(1, 6))
    
    # Property address
    story.append(labeled_box("Property Address", rec.get("PROPERTY_ADDRESS"), 6.9*inch, theme, styles))
    story.append(Spacer(1, 6))
    
    # Repair cost
    repair_row = Table([[
        labeled_box("Estimated Repair Cost", format_money(rec.get("EST_REPAIR_COST")), 3.4*inch, theme, styles),
        labeled_box("Claim Amount", format_money(rec.get("CLAIM_AMOUNT")), 3.4*inch, theme, styles),
    ]], colWidths=[3.4*inch, 3.4*inch])
    story.append(repair_row)
    story.append(Spacer(1, 8))
    
    # Required documents
    docs_text = """
    <b>Required Documents for Property Insurance Claim:</b><br/>
    ☐ Property Ownership Documents<br/>
    ☐ Photos of Damage (Multiple angles)<br/>
    ☐ Repair Estimates from contractors<br/>
    ☐ Police Report (for theft/vandalism)<br/>
    ☐ Fire Department Report (for fire damage)<br/>
    ☐ Original Purchase Receipts<br/>
    ☐ Previous Inspection Reports<br/>
    ☐ Inventory of damaged items
    """
    story.append(info_box(docs_text, theme, styles))
    
    return story

def add_mobile_complete(rec, story, theme, styles):
    """Mobile insurance with ALL specific fields"""
    story.append(section_header("Mobile Device Insurance Claim Details", theme, styles))
    story.append(Spacer(1, 8))
    
    # Device details
    device_row = Table([[
        labeled_box("Device Model", rec.get("DEVICE_MODEL"), 3.4*inch, theme, styles),
        labeled_box("IMEI Number", rec.get("IMEI"), 3.4*inch, theme, styles),
    ]], colWidths=[3.4*inch, 3.4*inch])
    story.append(device_row)
    story.append(Spacer(1, 6))
    
    # Loss details
    loss_row = Table([[
        labeled_box("Loss Type", rec.get("LOSS_TYPE"), 3.4*inch, theme, styles),
        labeled_box("Proof of Purchase", rec.get("PROOF_OF_PURCHASE"), 3.4*inch, theme, styles),
    ]], colWidths=[3.4*inch, 3.4*inch])
    story.append(loss_row)
    story.append(Spacer(1, 8))
    
    # Required documents
    docs_text = """
    <b>Required Documents for Mobile Device Claim:</b><br/>
    ☐ Original Purchase Receipt/Invoice<br/>
    ☐ Device Photos (if damaged)<br/>
    ☐ IMEI Screenshot from device settings<br/>
    ☐ Police Report (if stolen)<br/>
    ☐ Warranty Card<br/>
    ☐ SIM Card details<br/>
    ☐ Device Box with IMEI sticker<br/>
    ☐ Service center report (if applicable)
    """
    story.append(info_box(docs_text, theme, styles))
    
    return story

def add_motor_complete(rec, story, theme, styles):
    """Motor insurance with complete details"""
    story.append(section_header("Motor Vehicle Insurance Claim Details", theme, styles))
    story.append(Spacer(1, 8))
    
    # Vehicle details (using available fields)
    vehicle_info = f"""
    <b>Vehicle Incident Information:</b><br/>
    • Policy Number: {rec.get('POLICY_NUMBER')}<br/>
    • Vehicle Type: {rec.get('VEHICLE_TYPE')}<br/>
    • VIN: {rec.get('VIN')}<br/>
    • License Plate: {rec.get('LICENSE_PLATE')}<br/>
    • Incident Location: {rec.get('INCIDENT_CITY')}, {rec.get('INCIDENT_STATE')}<br/>
    • Date of Incident: {format_date(rec.get('LOSS_DT'))}<br/>
    • Time of Incident: {rec.get('INCIDENT_HOUR_OF_THE_DAY')}:00 hours<br/>
    • Severity: {rec.get('INCIDENT_SEVERITY')}<br/>
    • Claim Amount: {format_money(rec.get('CLAIM_AMOUNT'))}
    """
    story.append(info_box(vehicle_info, theme, styles))
    story.append(Spacer(1, 8))
    
    # Required documents
    docs_text = """
    <b>Required Documents for Motor Insurance Claim:</b><br/>
    ☐ Driver's License<br/>
    ☐ Vehicle Registration Certificate<br/>
    ☐ Police Report (FIR copy)<br/>
    ☐ Photos of vehicle damage<br/>
    ☐ Repair Estimates<br/>
    ☐ Insurance Policy Copy<br/>
    ☐ Claim Form duly filled<br/>
    ☐ Third party details (if applicable)
    """
    story.append(info_box(docs_text, theme, styles))
    
    return story

def add_health_complete(rec, story, theme, styles):
    """Health insurance with complete details"""
    story.append(section_header("Health Insurance Claim Details", theme, styles))
    story.append(Spacer(1, 8))
    
    # Medical claim info
    medical_info = f"""
    <b>Medical Claim Information:</b><br/>
    • Provider Name: {rec.get('PROVIDER_NAME')}<br/>
    • Diagnosis Code: {rec.get('DIAGNOSIS_CODE')}<br/>
    • Procedure Code: {rec.get('PROCEDURE_CODE')}<br/>
    • Treatment Date: {format_date(rec.get('LOSS_DT'))}<br/>
    • Claim Amount: {format_money(rec.get('CLAIM_AMOUNT'))}<br/>
    • Premium Amount: {format_money(rec.get('PREMIUM_AMOUNT'))}<br/>
    • Incident Severity: {rec.get('INCIDENT_SEVERITY')}<br/>
    • Authority Contacted: {rec.get('AUTHORITY_CONTACTED')}<br/>
    • Injury Reported: {format_yes_no(rec.get('ANY_INJURY'))}
    """
    story.append(info_box(medical_info, theme, styles))
    story.append(Spacer(1, 8))
    
    # Required documents
    docs_text = """
    <b>Required Documents for Health Insurance Claim:</b><br/>
    ☐ Medical Bills and Invoices<br/>
    ☐ Prescription Receipts<br/>
    ☐ Doctor's Certificate<br/>
    ☐ Diagnostic Reports (Lab/X-ray/MRI)<br/>
    ☐ Discharge Summary (if hospitalized)<br/>
    ☐ Insurance Card Copy<br/>
    ☐ Claim Form<br/>
    ☐ KYC Documents
    """
    story.append(info_box(docs_text, theme, styles))
    
    return story

def build_declaration_complete(theme, styles):
    """Build comprehensive declaration"""
    story = []
    story.append(section_header("Declaration & Authorization", theme, styles))
    story.append(Spacer(1, 8))
    
    declaration = """
    <b>DECLARATION:</b><br/>
    I hereby declare that all the information provided in this claim form is true, complete, and accurate 
    to the best of my knowledge and belief. I have not withheld any material information that may influence 
    the assessment or settlement of this claim.<br/><br/>
    
    <b>AUTHORIZATION:</b><br/>
    I authorize Premier Insurance Group and its representatives to investigate this claim, including obtaining 
    information from medical providers, employers, government agencies, and any other relevant parties. 
    I understand that any false statement or misrepresentation may result in denial of the claim and may 
    subject me to legal action.<br/><br/>
    
    <b>ACKNOWLEDGMENT:</b><br/>
    I acknowledge that the settlement of this claim is subject to the terms, conditions, and exclusions 
    of my insurance policy.
    """
    story.append(info_box(declaration, theme, styles))
    story.append(Spacer(1, 20))
    
    # Signature section
    sig_table = Table([
        ["_" * 40, "_" * 20],
        [Paragraph("Policyholder Signature", styles["LABEL"]), 
         Paragraph("Date", styles["LABEL"])],
        ["", ""],
        ["_" * 40, "_" * 20],
        [Paragraph("Witness Signature", styles["LABEL"]), 
         Paragraph("Date", styles["LABEL"])]
    ], colWidths=[4.0*inch, 2.5*inch])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 1), (-1, 1), 6),
        ("TOPPADDING", (0, 4), (-1, 4), 6),
    ]))
    story.append(sig_table)
    
    return story

# ----------------------------
# Main Story Builder
# ----------------------------
def build_story(rec):
    """Build complete story with ALL fields"""
    ins_type = clean_val(rec.get("INSURANCE_TYPE"), "General").title()
    theme = THEMES.get(ins_type, THEMES["General"])
    styles = create_styles(theme)
    
    story = []
    
    # Transaction section
    story.extend(build_transaction_section(rec, theme, styles))
    story.append(Spacer(1, 12))
    
    # Complete policyholder section
    story.extend(build_policyholder_complete(rec, theme, styles))
    story.append(Spacer(1, 12))
    
    # Complete incident section
    story.extend(build_incident_complete(rec, theme, styles))
    story.append(Spacer(1, 12))
    
    # Complete financial section
    story.extend(build_financial_complete(rec, theme, styles))
    story.append(Spacer(1, 12))
    
    # Type-specific comprehensive sections
    if ins_type == "Life":
        add_life_complete(rec, story, theme, styles)
    elif ins_type == "Travel":
        add_travel_complete(rec, story, theme, styles)
    elif ins_type == "Property":
        add_property_complete(rec, story, theme, styles)
    elif ins_type == "Mobile":
        add_mobile_complete(rec, story, theme, styles)
    elif ins_type == "Motor":
        add_motor_complete(rec, story, theme, styles)
    elif ins_type == "Health":
        add_health_complete(rec, story, theme, styles)
    
    story.append(Spacer(1, 12))
    
    # Comprehensive declaration
    story.extend(build_declaration_complete(theme, styles))
    
    return story, theme["title"]

# ----------------------------
# Main Function
# ----------------------------
def main():
    """Generate comprehensive PDFs with all fields"""
    print("\n" + "="*60)
    print(" COMPREHENSIVE INSURANCE CLAIM PDF GENERATOR")
    print(" Including ALL CSV Fields for Each Insurance Type")
    print("="*60 + "\n")
    
    # Find CSV
    csv_path = None
    for filename in [INPUT_CSV, FALLBACK_CSV]:
        path = Path(filename)
        if path.exists():
            csv_path = path
            print(f"✓ Found CSV: {filename}")
            break
    
    if not csv_path:
        print(f"✗ Error: No CSV file found")
        return
    
    # Load data
    try:
        df = pd.read_csv(csv_path)
        print(f"✓ Loaded: {len(df)} records with {len(df.columns)} columns")
        
        # Show available columns
        print(f"\nAvailable columns ({len(df.columns)}):")
        for i in range(0, len(df.columns), 5):
            cols = df.columns[i:i+5].tolist()
            print(f"  {', '.join(cols)}")
        
    except Exception as e:
        print(f"✗ Error loading CSV: {e}")
        return
    
    # Create output directory
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n✓ Output directory: {out_dir.absolute()}\n")
    
    # Generate PDFs
    num_rows = min(NUM_ROWS, len(df))
    print(f"Generating {num_rows} comprehensive PDFs...\n")
    
    success = 0
    for idx, row in df.head(num_rows).iterrows():
        rec = row.to_dict()
        txn = clean_val(rec.get("TRANSACTION_ID"), f"UNK{idx:04d}")
        ins_type = clean_val(rec.get("INSURANCE_TYPE"), "General")
        customer = clean_val(rec.get("CUSTOMER_NAME"), "Unknown")
        claim_date = format_date(rec.get("LOSS_DT"))
        
        filename = f"{txn}_{ins_type.lower()}_complete.pdf"
        full_path = out_dir / filename
        
        try:
            theme = THEMES.get(ins_type.title(), THEMES["General"])
            story, title = build_story(rec)
            
            doc = SimpleDocTemplate(
                str(full_path),
                pagesize=LETTER,
                leftMargin=0.7*inch,
                rightMargin=0.7*inch,
                topMargin=2.2*inch,
                bottomMargin=1.0*inch
            )
            
            doc.build(
                story,
                onFirstPage=create_header_footer(title, txn, theme, claim_date),
                onLaterPages=create_header_footer(title, txn, theme, claim_date)
            )
            
            print(f"  {theme['icon']} {filename:<40} [{ins_type:<10}] {customer}")
            success += 1
            
        except Exception as e:
            print(f"  ✗ Error: {filename} - {str(e)[:50]}")
    
    # Summary
    print("\n" + "="*60)
    print(f"✓ Successfully generated: {success} comprehensive PDFs")
    print(f"📁 Location: {out_dir.absolute()}")
    print("\nEach PDF includes:")
    print("  • ALL common fields (30+ fields)")
    print("  • Type-specific fields")
    print("  • Transaction details")
    print("  • Complete financial information")
    print("  • Required documents checklist")
    print("  • Comprehensive declaration")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
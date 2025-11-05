from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from io import BytesIO
from datetime import datetime


def generate_invoice_pdf(invoice_data: dict, company_data: dict) -> bytes:
    """
    Generate PDF for invoice
    
    Args:
        invoice_data: Invoice details with line items
        company_data: Company/tenant details
    
    Returns:
        bytes: PDF content
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30,
                           topMargin=30, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#4F46E5'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=12
    )
    
    normal_style = styles['Normal']
    
    # Title
    title = Paragraph("INVOICE", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Company and Invoice Info
    info_data = [
        [Paragraph(f"<b>{company_data.get('name', 'Company Name')}</b>", normal_style),
         Paragraph(f"<b>Invoice #:</b> {invoice_data.get('invoiceNumber', 'N/A')}", normal_style)],
        [Paragraph(company_data.get('address', 'Company Address'), normal_style),
         Paragraph(f"<b>Date:</b> {invoice_data.get('invoiceDate', 'N/A')}", normal_style)],
        [Paragraph(f"<b>GST:</b> {company_data.get('taxId', 'N/A')}", normal_style),
         Paragraph(f"<b>Due Date:</b> {invoice_data.get('dueDate', 'N/A')}", normal_style)],
    ]
    
    info_table = Table(info_data, colWidths=[3*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Bill To
    elements.append(Paragraph("<b>Bill To:</b>", heading_style))
    customer_info = Paragraph(f"""
        <b>{invoice_data.get('customerName', 'Customer Name')}</b><br/>
        {invoice_data.get('customerEmail', '')}<br/>
        {invoice_data.get('customerPhone', '')}
    """, normal_style)
    elements.append(customer_info)
    elements.append(Spacer(1, 20))
    
    # Line Items Table
    line_items_data = [
        ['#', 'Description', 'Qty', 'Rate', 'Tax %', 'Amount']
    ]
    
    for idx, item in enumerate(invoice_data.get('lineItems', []), 1):
        line_items_data.append([
            str(idx),
            item.get('description', ''),
            str(item.get('quantity', 0)),
            f"₹{item.get('rate', 0):,.2f}",
            f"{item.get('taxRate', 0)}%",
            f"₹{item.get('totalAmount', 0):,.2f}"
        ])
    
    # Add totals
    line_items_data.append(['', '', '', '', 'Subtotal:', f"₹{invoice_data.get('subtotal', 0):,.2f}"])
    line_items_data.append(['', '', '', '', 'Tax:', f"₹{invoice_data.get('taxAmount', 0):,.2f}"])
    line_items_data.append(['', '', '', '', 'Discount:', f"₹{invoice_data.get('discountAmount', 0):,.2f}"])
    line_items_data.append(['', '', '', '', '<b>Total:</b>', f"<b>₹{invoice_data.get('total', 0):,.2f}</b>"])
    
    line_items_table = Table(line_items_data, colWidths=[0.5*inch, 2.5*inch, 0.7*inch, 1*inch, 1*inch, 1.3*inch])
    line_items_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Body
        ('ALIGN', (2, 1), (2, -5), 'CENTER'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -5), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -5), 0.5, colors.grey),
        
        # Totals section
        ('FONTNAME', (4, -4), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (4, -4), (-1, -4), 1, colors.black),
        ('LINEABOVE', (4, -1), (-1, -1), 2, colors.black),
    ]))
    
    elements.append(line_items_table)
    elements.append(Spacer(1, 30))
    
    # Notes
    if invoice_data.get('notes'):
        elements.append(Paragraph("<b>Notes:</b>", heading_style))
        elements.append(Paragraph(invoice_data.get('notes', ''), normal_style))
        elements.append(Spacer(1, 20))
    
    # Terms
    if invoice_data.get('terms'):
        elements.append(Paragraph("<b>Terms & Conditions:</b>", heading_style))
        elements.append(Paragraph(invoice_data.get('terms', ''), normal_style))
    
    # Footer
    elements.append(Spacer(1, 30))
    footer = Paragraph(
        f"<i>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
        ParagraphStyle('Footer', parent=normal_style, fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    )
    elements.append(footer)
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF content
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content


def generate_receipt_pdf(receipt_data: dict, company_data: dict) -> bytes:
    """Generate PDF for payment receipt"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("PAYMENT RECEIPT", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    # Receipt details
    data = [
        ['Receipt Number:', receipt_data.get('receiptNumber', 'N/A')],
        ['Date:', receipt_data.get('receiptDate', 'N/A')],
        ['Customer:', receipt_data.get('customerName', 'N/A')],
        ['Amount Received:', f"₹{receipt_data.get('amount', 0):,.2f}"],
        ['Payment Method:', receipt_data.get('paymentMethod', 'N/A')],
    ]
    
    table = Table(data, colWidths=[2*inch, 4*inch])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(table)
    
    doc.build(elements)
    
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content

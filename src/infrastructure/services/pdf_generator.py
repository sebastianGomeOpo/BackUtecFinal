"""
PDF Generator Service for Purchase Orders
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime
import uuid
import os


class PDFGenerator:
    """Generate professional purchase order PDFs"""
    
    @staticmethod
    def generate_purchase_order(
        order_data: dict,
        output_path: str = None
    ) -> str:
        """
        Generate a professional purchase order PDF
        
        Args:
            order_data: Dictionary with order information
            output_path: Optional path to save PDF
            
        Returns:
            Path to generated PDF file
        """
        if not output_path:
            # Create pdfs directory if it doesn't exist
            pdf_dir = os.path.join(os.getcwd(), 'pdfs')
            os.makedirs(pdf_dir, exist_ok=True)
            
            order_id = order_data.get('order_id', str(uuid.uuid4())[:8])
            output_path = os.path.join(pdf_dir, f'orden_{order_id}.pdf')
        
        # Create PDF
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Container for elements
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Title
        story.append(Paragraph("ORDEN DE COMPRA", title_style))
        story.append(Spacer(1, 12))
        
        # Company Info
        company_info = [
            ["<b>Tienda de Artículos para el Hogar</b>", ""],
            ["Dirección: Av. Principal 123", f"<b>Orden #:</b> {order_data.get('order_id', 'N/A')}"],
            ["Ciudad, País", f"<b>Fecha:</b> {order_data.get('date', datetime.now().strftime('%d/%m/%Y'))}"],
            ["Tel: +123 456 7890", f"<b>Válida hasta:</b> {order_data.get('valid_until', 'N/A')}"],
        ]
        
        company_table = Table(company_info, colWidths=[3*inch, 3*inch])
        company_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#374151')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#374151')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(company_table)
        story.append(Spacer(1, 20))
        
        # Customer Info (if available)
        if order_data.get('customer_name'):
            story.append(Paragraph("<b>DATOS DEL CLIENTE</b>", heading_style))
            customer_data = [
                ["Nombre:", order_data.get('customer_name', 'N/A')],
                ["Dirección:", order_data.get('customer_address', 'N/A')],
                ["Distrito:", order_data.get('district', 'N/A')],
                ["Teléfono:", order_data.get('customer_phone', 'N/A') or 'No proporcionado'],
                ["Email:", order_data.get('customer_email', 'N/A') or 'No proporcionado'],
            ]
            customer_table = Table(customer_data, colWidths=[1.5*inch, 4.5*inch])
            customer_table.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(customer_table)
            story.append(Spacer(1, 20))
        
        # Products Table
        story.append(Paragraph("<b>DETALLE DE PRODUCTOS</b>", heading_style))
        
        # Table header
        products_data = [
            ['#', 'Producto', 'Cantidad', 'Precio Unit.', 'Subtotal']
        ]
        
        # Add products
        for idx, item in enumerate(order_data.get('items', []), 1):
            products_data.append([
                str(idx),
                item.get('name', 'N/A'),
                str(item.get('quantity', 0)),
                f"${item.get('price', 0):.2f}",
                f"${item.get('subtotal', 0):.2f}"
            ])
        
        products_table = Table(
            products_data,
            colWidths=[0.5*inch, 3*inch, 1*inch, 1.25*inch, 1.25*inch]
        )
        
        products_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Body
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#374151')),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ]))
        
        story.append(products_table)
        story.append(Spacer(1, 20))
        
        # Financial Summary
        summary_data = [
            ['', 'Subtotal:', f"${order_data.get('subtotal', 0):.2f}"],
            ['', f"Envío ({order_data.get('district', 'N/A')}):", f"${order_data.get('shipping_cost', 0):.2f}"],
            ['', f"IVA ({order_data.get('tax_rate', 16)}%):", f"${order_data.get('tax', 0):.2f}"],
            ['', '<b>TOTAL:</b>', f"<b>${order_data.get('total', 0):.2f}</b>"],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch, 1*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#374151')),
            ('LINEABOVE', (1, 2), (-1, 2), 2, colors.HexColor('#1e40af')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Terms and Conditions
        story.append(Paragraph("<b>TÉRMINOS Y CONDICIONES</b>", heading_style))
        
        terms = [
            "1. Esta orden de compra es válida por 7 días a partir de la fecha de emisión.",
            "2. Los precios incluyen IVA y están sujetos a cambios sin previo aviso.",
            "3. El pago debe realizarse antes de la entrega de los productos.",
            "4. Métodos de pago aceptados: Transferencia bancaria, tarjeta de crédito/débito.",
            "5. Tiempo estimado de entrega: 3-5 días hábiles después de confirmar el pago.",
            "6. Los productos pueden ser devueltos dentro de 30 días con el recibo original.",
            "7. La garantía de los productos varía según el fabricante (consultar detalles).",
            "8. Para cualquier consulta, contactar a nuestro servicio al cliente."
        ]
        
        for term in terms:
            story.append(Paragraph(term, styles['Normal']))
            story.append(Spacer(1, 6))
        
        story.append(Spacer(1, 20))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#6b7280'),
            alignment=TA_CENTER
        )
        
        story.append(Paragraph(
            "Gracias por su preferencia | www.tiendahogar.com | ventas@tiendahogar.com",
            footer_style
        ))
        
        # Build PDF
        doc.build(story)
        
        return output_path

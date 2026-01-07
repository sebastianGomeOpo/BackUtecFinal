"""
Receipt/Invoice Route - Generate HTML receipts for orders
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime
from ...infrastructure.database.mongodb import MongoDB

router = APIRouter()


def generate_receipt_html(order: dict) -> str:
    """Generate HTML receipt for an order"""
    
    # Format date
    try:
        order_date = datetime.fromisoformat(order['created_at']).strftime('%d/%m/%Y %H:%M')
    except:
        order_date = order.get('created_at', 'N/A')
    
    # Build items HTML
    items_html = ""
    for item in order.get('items', []):
        items_html += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <div style="font-weight: 500; color: #111827;">{item['name']}</div>
            </td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: center;">{item['quantity']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right;">${item['unit_price']:.2f}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: right; font-weight: 600;">${item['subtotal']:.2f}</td>
        </tr>
        """
    
    # Status badge color
    status_colors = {
        'confirmed': {'bg': '#dcfce7', 'text': '#166534'},
        'pending_payment': {'bg': '#fef3c7', 'text': '#92400e'},
        'paid': {'bg': '#d1fae5', 'text': '#065f46'},
        'shipped': {'bg': '#dbeafe', 'text': '#1e40af'},
        'delivered': {'bg': '#e9d5ff', 'text': '#6b21a8'},
    }
    status = order.get('status', 'confirmed')
    status_color = status_colors.get(status, {'bg': '#f3f4f6', 'text': '#374151'})
    
    status_text = {
        'confirmed': 'Confirmado',
        'pending_payment': 'Pendiente Pago',
        'paid': 'Pagado',
        'shipped': 'Enviado',
        'delivered': 'Entregado'
    }.get(status, status.title())
    
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Orden de Compra #{order['order_id'].upper()}</title>
        <style>
            @media print {{
                body {{ margin: 0; }}
                .no-print {{ display: none; }}
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #111827;
                background: #f9fafb;
                margin: 0;
                padding: 20px;
            }}
            
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                border-radius: 8px;
                overflow: hidden;
            }}
            
            .header {{
                background: linear-gradient(135deg, #FF285B 0%, #cc2049 100%);
                color: white;
                padding: 40px 30px;
                text-align: center;
            }}
            
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 700;
            }}
            
            .header p {{
                margin: 8px 0 0 0;
                opacity: 0.95;
                font-size: 16px;
            }}
            
            .content {{
                padding: 30px;
            }}
            
            .info-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
                margin-bottom: 30px;
            }}
            
            .info-section {{
                background: #f9fafb;
                padding: 20px;
                border-radius: 8px;
                border: 1px solid #e5e7eb;
            }}
            
            .info-section h3 {{
                margin: 0 0 12px 0;
                font-size: 14px;
                text-transform: uppercase;
                color: #6b7280;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            
            .info-section p {{
                margin: 6px 0;
                font-size: 15px;
                color: #111827;
            }}
            
            .info-section .label {{
                color: #6b7280;
                font-size: 13px;
                margin-bottom: 2px;
            }}
            
            .status-badge {{
                display: inline-block;
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                background-color: {status_color['bg']};
                color: {status_color['text']};
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            
            th {{
                background: #f9fafb;
                padding: 12px;
                text-align: left;
                font-weight: 600;
                color: #374151;
                border-bottom: 2px solid #e5e7eb;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            th:nth-child(2), th:nth-child(3), th:nth-child(4) {{
                text-align: right;
            }}
            
            td {{
                color: #374151;
                font-size: 15px;
            }}
            
            .totals {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 2px solid #e5e7eb;
            }}
            
            .totals-row {{
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                font-size: 15px;
            }}
            
            .totals-row.subtotal {{
                color: #6b7280;
            }}
            
            .totals-row.shipping {{
                color: #6b7280;
            }}
            
            .totals-row.total {{
                font-size: 20px;
                font-weight: 700;
                color: #111827;
                padding-top: 12px;
                margin-top: 8px;
                border-top: 2px solid #e5e7eb;
            }}
            
            .footer {{
                background: #f9fafb;
                padding: 20px 30px;
                text-align: center;
                border-top: 1px solid #e5e7eb;
                color: #6b7280;
                font-size: 14px;
            }}
            
            .print-button {{
                background: #FF285B;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(255, 40, 91, 0.2);
                transition: all 0.2s;
            }}
            
            .print-button:hover {{
                background: #cc2049;
                box-shadow: 0 4px 8px rgba(255, 40, 91, 0.3);
            }}
            
            @media (max-width: 640px) {{
                .info-grid {{
                    grid-template-columns: 1fr;
                    gap: 15px;
                }}
                
                .content {{
                    padding: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header -->
            <div class="header">
                <h1>ORDEN DE COMPRA</h1>
                <p>#{order['order_id'].upper()}</p>
            </div>
            
            <!-- Print Button -->
            <div class="content">
                <div class="no-print" style="text-align: center;">
                    <button class="print-button" onclick="window.print()">
                        Imprimir Orden
                    </button>
                </div>
                
                <!-- Info Grid -->
                <div class="info-grid">
                    <!-- Order Info -->
                    <div class="info-section">
                        <h3>Información de Orden</h3>
                        <p class="label">Número de Orden</p>
                        <p><strong>#{order['order_id'].upper()}</strong></p>
                        <p class="label">Fecha</p>
                        <p>{order_date}</p>
                        <p class="label">Estado</p>
                        <p><span class="status-badge">{status_text}</span></p>
                    </div>
                    
                    <!-- Customer Info -->
                    <div class="info-section">
                        <h3>Datos del Cliente</h3>
                        <p class="label">Nombre</p>
                        <p><strong>{order.get('customer_name', 'N/A')}</strong></p>
                        <p class="label">Dirección</p>
                        <p>{order.get('customer_address', 'N/A')}</p>
                        <p class="label">Distrito</p>
                        <p>{order.get('district', 'N/A')}</p>
                        <p class="label">Teléfono</p>
                        <p>{order.get('customer_phone', 'N/A')}</p>
                        {f'<p class="label">Email</p><p>{order.get("customer_email")}</p>' if order.get('customer_email') else ''}
                    </div>
                </div>
                
                <!-- Products Table -->
                <div>
                    <h3 style="margin: 30px 0 15px 0; color: #111827; font-size: 18px;">Productos</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Producto</th>
                                <th style="text-align: center;">Cantidad</th>
                                <th style="text-align: right;">Precio Unit.</th>
                                <th style="text-align: right;">Subtotal</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>
                </div>
                
                <!-- Totals -->
                <div class="totals">
                    <div class="totals-row subtotal">
                        <span>Subtotal</span>
                        <span>${order.get('subtotal', 0):.2f}</span>
                    </div>
                    <div class="totals-row shipping">
                        <span>Envío ({order.get('district', 'N/A')})</span>
                        <span>S/. {order.get('shipping_cost', 0):.2f}</span>
                    </div>
                    <div class="totals-row total">
                        <span>TOTAL</span>
                        <span>${order.get('total', 0):.2f}</span>
                    </div>
                </div>
                
                <!-- Additional Info -->
                <div style="margin-top: 40px; padding: 20px; background: #f0f9ff; border-left: 4px solid #0ea5e9; border-radius: 4px;">
                    <p style="margin: 0; color: #0c4a6e; font-size: 14px;">
                        <strong> Tiempo de entrega:</strong> 2-3 días hábiles<br>
                        <strong> Método de pago:</strong> {order.get('payment_method', 'Por confirmar')}<br>
                        {f'<strong> ID de Cotización:</strong> {order.get("quote_id", "N/A")}' if order.get('quote_id') else ''}
                    </p>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="footer">
                <p style="margin: 0;">Gracias por tu compra</p>
                <p style="margin: 8px 0 0 0; font-size: 13px;">
                    Este es un documento generado automáticamente • Canal de Ventas Digitales
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


@router.get("/orders/{order_id}/receipt", response_class=HTMLResponse)
async def get_order_receipt(order_id: str):
    """Get HTML receipt for an order"""
    try:
        db = MongoDB.get_database()
        
        # Find order in MongoDB
        order = await db.orders.find_one({"order_id": order_id})
        
        if not order:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        # Generate HTML
        html = generate_receipt_html(order)
        
        return HTMLResponse(content=html)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando recibo: {str(e)}")

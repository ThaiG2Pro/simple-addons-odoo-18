import requests
import json
import re
import markdown
import base64
from datetime import datetime, timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError

class DashboardSummary(models.TransientModel):
    _name = 'dashboard.summary'
    _description = 'AI Dashboard Summary'

    summary_type = fields.Selection([
        ('sales', 'Sales Summary'),
        ('crm', 'CRM Summary'),
        ('combined', 'Combined Summary')
    ], string='Summary Type', default='sales', required=True)
    
    summary_text = fields.Html('AI Summary', readonly=True)
    data_preview = fields.Text('Data Preview', readonly=True)
    llm_provider = fields.Selection([
        ('mock', 'Mock/Demo (No API)'),
        ('groq', 'Groq AI'),
        
    ], string='AI Provider', default='mock', required=True)
    
    days_range = fields.Integer('Days to Analyze', default=30, required=True)
    enable_pdf_export = fields.Boolean('Enable PDF Export', default=False, help="Enable PDF generation (requires WeasyPrint)")
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Set current date context
        res['summary_text'] = f'<p>Ready to generate summary for {self.env.user.name}</p>'
        return res
    
    def action_generate_summary(self):
        """Generate AI summary based on selected type"""
        try:
            if self.summary_type == 'sales':
                data_text = self._get_sales_data()
            elif self.summary_type == 'crm':
                data_text = self._get_crm_data()
            else:  # combined
                sales_data = self._get_sales_data()
                crm_data = self._get_crm_data()
                data_text = f"SALES DATA:\n{sales_data}\n\nCRM DATA:\n{crm_data}"
            
            # Store data preview
            self.data_preview = data_text
            
            # Generate AI summary
            summary = self._call_llm(data_text)
            self.summary_text = summary
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'dashboard.summary',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'name': f'AI {self.summary_type.title()} Summary'
            }
            
        except Exception as e:
            raise UserError(f"Error generating summary: {str(e)}")
    
    def _get_sales_data(self):
        """Extract sales data for analysis"""
        end_date = fields.Date.today()
        start_date = end_date - timedelta(days=self.days_range)
        
        sales_orders = self.env['sale.order'].search([
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('state', 'in', ['sale', 'done'])
        ])
        
        if not sales_orders:
            return "No sales data found for the selected period."
        
        total_amount = sum(sales_orders.mapped('amount_total'))
        total_orders = len(sales_orders)
        avg_order = total_amount / total_orders if total_orders else 0
        
        # Top customers
        customers = {}
        for order in sales_orders:
            customer = order.partner_id.name
            customers[customer] = customers.get(customer, 0) + order.amount_total
        
        top_customers = sorted(customers.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Products sold
        order_lines = sales_orders.mapped('order_line')
        products = {}
        for line in order_lines:
            product = line.product_id.name
            products[product] = products.get(product, 0) + line.product_uom_qty
        
        top_products = sorted(products.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return f"""
SALES PERFORMANCE ({start_date} to {end_date}):
• Total Orders: {total_orders}
• Total Revenue: ${total_amount:,.2f}
• Average Order Value: ${avg_order:,.2f}
• Top Customers: {', '.join([f"{name} (${amount:,.0f})" for name, amount in top_customers])}
• Top Products: {', '.join([f"{name} ({qty:.0f} units)" for name, qty in top_products])}
        """.strip()
    
    def _get_crm_data(self):
        """Extract CRM data for analysis"""
        end_date = fields.Date.today()
        start_date = end_date - timedelta(days=self.days_range)
        
        opportunities = self.env['crm.lead'].search([
            ('type', '=', 'opportunity'),
            ('create_date', '>=', start_date),
            ('create_date', '<=', end_date)
        ])
        
        if not opportunities:
            return "No CRM opportunities found for the selected period."
        
        total_opps = len(opportunities)
        won_opps = opportunities.filtered(lambda o: o.stage_id.is_won)
        lost_opps = opportunities.filtered(lambda o: o.probability == 0)
        
        total_value = sum(opportunities.mapped('expected_revenue'))
        won_value = sum(won_opps.mapped('expected_revenue'))
        
        win_rate = (len(won_opps) / total_opps * 100) if total_opps else 0
        
        # Pipeline by stage
        stages = {}
        for opp in opportunities:
            stage = opp.stage_id.name
            stages[stage] = stages.get(stage, 0) + 1
        
        return f"""
CRM PERFORMANCE ({start_date} to {end_date}):
• Total Opportunities: {total_opps}
• Won Opportunities: {len(won_opps)}
• Lost Opportunities: {len(lost_opps)}
• Win Rate: {win_rate:.1f}%
• Total Pipeline Value: ${total_value:,.2f}
• Won Value: ${won_value:,.2f}
• Pipeline by Stage: {', '.join([f"{stage}: {count}" for stage, count in stages.items()])}
        """.strip()
    
    def _call_llm(self, data_text):
        """Call LLM API for summary generation"""
        
        prompt = f"""
You are a business analyst. Analyze this business data and provide insights:

{data_text}

Please provide:
1. Key Performance Highlights
2. Notable Trends or Patterns  
3. Business Insights
4. Actionable Recommendations

Keep it concise but insightful. Use bullet points and business language.
Current date: {datetime.now().strftime('%Y-%m-%d')}
Analysis requested by: {self.env.user.name}
        """.strip()
        
        if self.llm_provider == 'mock':
            return self._generate_mock_summary(data_text)
        elif self.llm_provider == 'groq':
            return self._call_groq(prompt)

        else:
            return "<p>Please select an AI provider to generate summary.</p>"
    
    def _generate_mock_summary(self, data_text):
        """Generate a mock summary for demo purposes"""
        lines = data_text.strip().split('\n')
        
        summary = f"""
        <div style="font-family: Arial, sans-serif;">
        <h3>🤖 AI Business Summary</h3>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
        <p><strong>Analyst:</strong> {self.env.user.name}</p>
        
        <h4>📊 Key Performance Highlights:</h4>
        <ul>
        <li>Data analysis completed for {self.days_range} days period</li>
        <li>Summary type: {self.summary_type.title()}</li>
        <li>Total data points analyzed: {len(lines)}</li>
        </ul>
        
        <h4>📈 Business Insights:</h4>
        <ul>
        <li><strong>Performance Trend:</strong> Business metrics show activity in the analyzed period</li>
        <li><strong>Data Quality:</strong> Sufficient data available for meaningful analysis</li>
        <li><strong>Time Frame:</strong> {self.days_range}-day analysis provides good insights</li>
        </ul>
        
        <h4>💡 Actionable Recommendations:</h4>
        <ul>
        <li>Continue monitoring key performance indicators</li>
        <li>Set up regular AI-powered reporting</li>
        <li>Consider integrating with real LLM providers for deeper insights</li>
        <li>Focus on data-driven decision making</li>
        </ul>
        
        <hr>
        <p><em>This is a demo summary. Connect real LLM providers for advanced AI analysis.</em></p>
        </div>
        """
        return summary
    
    def _format_ai_response(self, ai_text):
        """Format AI response to structured HTML based on todo requirements"""
        
        # Check if response looks like Markdown
        if self._is_markdown_format(ai_text):
            return self._convert_markdown_to_html(ai_text)
        else:
            return self._convert_plain_text_to_html(ai_text)
    
    def _is_markdown_format(self, text):
        """Check if the text contains Markdown formatting"""
        markdown_patterns = [
            r'^#{1,6}\s',  # Headers (#, ##, ###, etc.)
            r'^\*{1,2}.*\*{1,2}',  # Bold/italic (*text*, **text**)
            r'^\s*[-*+]\s',  # Bullet points (-, *, +)
            r'^\s*\d+\.\s',  # Numbered lists (1., 2., etc.)
            r'`.*`',  # Inline code blocks
            r'^```',  # Fenced code blocks
            r'^\|.*\|',  # Table formatting
            r'^\s*>\s',  # Blockquotes
            r'\[.*\]\(.*\)',  # Links [text](url)
            r'!\[.*\]\(.*\)',  # Images ![alt](url)
            r'^---+$',  # Horizontal rules
        ]
        
        # Count how many markdown patterns are found
        pattern_count = 0
        for pattern in markdown_patterns:
            if re.search(pattern, text, re.MULTILINE):
                pattern_count += 1
        
        # Consider it markdown if we find 2 or more patterns
        return pattern_count >= 2
    
    def _convert_markdown_to_html(self, markdown_text):
        """Convert Markdown to HTML using markdown library"""
        try:
            # Convert markdown to HTML
            html_content = markdown.markdown(markdown_text, extensions=['tables', 'fenced_code'])
            
            # Add custom CSS styling
            css_styles = """
            <style>
                body { font-family: "Arial", sans-serif; line-height: 1.6; margin: 20px; }
                h1, h2, h3 { color: #2c3e50; margin-top: 20px; margin-bottom: 10px; }
                h1 { font-size: 24px; border-bottom: 2px solid #3498db; }
                h2 { font-size: 20px; color: #34495e; }
                h3 { font-size: 16px; color: #7f8c8d; }
                p { margin-bottom: 10px; color: #2c3e50; }
                ul, ol { margin-left: 20px; margin-bottom: 15px; }
                li { margin-bottom: 5px; }
                code { background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: 'Courier New', monospace; }
                pre { background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }
                strong { color: #2c3e50; font-weight: bold; }
                em { color: #7f8c8d; font-style: italic; }
                table { border-collapse: collapse; width: 100%; margin: 10px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; font-weight: bold; }
            </style>
            """
            
            return f"{css_styles}<div class='ai-response'>{html_content}</div>"
            
        except Exception as e:
            # Fallback to plain text conversion if markdown fails
            return self._convert_plain_text_to_html(markdown_text)
    
    def _convert_plain_text_to_html(self, plain_text):
        """Convert plain text to structured HTML using regex patterns"""
        
        # Split text into paragraphs
        paragraphs = plain_text.split('\n\n')
        html_parts = []
        
        css_styles = """
        <style>
            .ai-response { font-family: "Arial", sans-serif; line-height: 1.6; margin: 20px; }
            .ai-response h1, .ai-response h2, .ai-response h3 { color: #2c3e50; margin-top: 20px; margin-bottom: 10px; }
            .ai-response h1 { font-size: 24px; border-bottom: 2px solid #3498db; }
            .ai-response h2 { font-size: 20px; color: #34495e; }
            .ai-response h3 { font-size: 16px; color: #7f8c8d; }
            .ai-response p { margin-bottom: 10px; color: #2c3e50; }
            .ai-response ul { margin-left: 20px; margin-bottom: 15px; }
            .ai-response li { margin-bottom: 5px; }
            .ai-response .highlight { background: #f39c12; color: white; padding: 2px 4px; border-radius: 3px; }
            .ai-response .number { color: #e74c3c; font-weight: bold; }
        </style>
        """
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
                
            lines = paragraph.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Convert headers (lines starting with numbers or special patterns)
                if re.match(r'^\d+\.\s*(.+)', line):
                    match = re.match(r'^\d+\.\s*(.+)', line)
                    html_parts.append(f"<h2>{match.group(1)}</h2>")
                
                # Convert bullet points
                elif re.match(r'^[-•*]\s*(.+)', line):
                    if not html_parts or not html_parts[-1].startswith('<ul>'):
                        html_parts.append('<ul>')
                    match = re.match(r'^[-•*]\s*(.+)', line)
                    content = self._format_inline_text(match.group(1))
                    html_parts.append(f"<li>{content}</li>")
                
                # Convert lines with colons (like "Key Insights:")
                elif ':' in line and len(line.split(':')[0]) < 50:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        title = parts[0].strip()
                        content = parts[1].strip()
                        if content:
                            html_parts.append(f"<h3>{title}:</h3><p>{self._format_inline_text(content)}</p>")
                        else:
                            html_parts.append(f"<h3>{title}:</h3>")
                    else:
                        html_parts.append(f"<p>{self._format_inline_text(line)}</p>")
                
                # Regular paragraphs
                else:
                    # Close any open lists
                    if html_parts and html_parts[-1] == '</li>':
                        html_parts.append('</ul>')
                    html_parts.append(f"<p>{self._format_inline_text(line)}</p>")
        
        # Close any remaining open lists
        if html_parts and html_parts[-1].endswith('</li>'):
            html_parts.append('</ul>')
        
        html_content = ''.join(html_parts)
        return f"{css_styles}<div class='ai-response'>{html_content}</div>"
    
    def _format_inline_text(self, text):
        """Format inline text elements like bold, numbers, etc."""
        
        # Highlight numbers with currency or percentages
        text = re.sub(r'\$([0-9,]+(?:\.[0-9]{2})?)', r'<span class="number">$\1</span>', text)
        text = re.sub(r'([0-9]+(?:\.[0-9]+)?%)', r'<span class="number">\1</span>', text)
        
        # Bold text in asterisks or emphasis
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        
        # Highlight key terms
        key_terms = ['increase', 'decrease', 'growth', 'decline', 'opportunity', 'risk', 'recommendation']
        for term in key_terms:
            text = re.sub(f'\\b({term})\\b', r'<span class="highlight">\1</span>', text, flags=re.IGNORECASE)
        
        return text
    
    def _call_groq(self, prompt):
        """Real Groq API call with improved response formatting"""
        
        api_key = "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"  # Or get from system parameters
        
        try:
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama-3.3-70b-versatile',  # Groq's model
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 800,
                    'temperature': 0.7
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_text = result['choices'][0]['message']['content']
                # Process the response for better formatting
                formatted_html = self._format_ai_response(ai_text)
                return formatted_html
            else:
                return f"<p>Error: {response.status_code} - {response.text}</p>"
                
        except Exception as e:
            return f"<p>API Error: {str(e)}</p>"
    
    def action_export_pdf(self):
        """Export the summary as PDF (optional feature)"""
        if not self.summary_text:
            raise UserError("Please generate a summary first before exporting to PDF.")
        
        try:
            # Try to import WeasyPrint
            from weasyprint import HTML
            
            # Prepare HTML content for PDF
            pdf_html = self._prepare_pdf_content()
            
            # Generate PDF
            pdf_content = HTML(string=pdf_html).write_pdf()
            
            # Create attachment
            filename = f"ai_summary_{self.summary_type}_{fields.Date.today()}.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': pdf_content,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}/{filename}',
                'target': 'new',
            }
            
        except ImportError:
            raise UserError("WeasyPrint library is not installed. Please install it using: pip install weasyprint")
        except Exception as e:
            raise UserError(f"Error generating PDF: {str(e)}")
    
    def _prepare_pdf_content(self):
        """Prepare HTML content optimized for PDF generation"""
        
        pdf_css = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page { 
                    size: A4; 
                    margin: 2cm; 
                    @top-center { content: "AI Business Summary - Generated " counter(page); }
                }
                body { 
                    font-family: "Arial", sans-serif; 
                    line-height: 1.6; 
                    color: #2c3e50;
                    font-size: 12px;
                }
                .header { 
                    text-align: center; 
                    margin-bottom: 30px; 
                    border-bottom: 2px solid #3498db;
                    padding-bottom: 20px;
                }
                .header h1 { 
                    color: #2c3e50; 
                    margin: 0;
                    font-size: 24px;
                }
                .meta-info { 
                    background: #ecf0f1; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin-bottom: 20px;
                }
                h1, h2, h3 { 
                    color: #2c3e50; 
                    page-break-after: avoid;
                }
                h1 { font-size: 20px; border-bottom: 1px solid #3498db; }
                h2 { font-size: 16px; color: #34495e; }
                h3 { font-size: 14px; color: #7f8c8d; }
                p { margin-bottom: 8px; }
                ul, ol { margin-left: 15px; }
                li { margin-bottom: 3px; }
                .highlight { background: #f39c12; color: white; padding: 1px 3px; }
                .number { color: #e74c3c; font-weight: bold; }
                .footer { 
                    position: fixed; 
                    bottom: 0; 
                    width: 100%; 
                    text-align: center; 
                    font-size: 10px; 
                    color: #7f8c8d;
                }
            </style>
        </head>
        <body>
        """
        
        pdf_footer = """
        <div class="footer">
            Generated by Simple Dashboard - AI Summary Module
        </div>
        </body>
        </html>
        """
        
        # Prepare content
        summary_content = self.summary_text or "<p>No summary available</p>"
        data_preview = self.data_preview or "No data available"
        
        content_body = f"""
        <div class="header">
            <h1>AI Business Summary Report</h1>
        </div>
        
        <div class="meta-info">
            <strong>Summary Type:</strong> {self.summary_type.title()}<br>
            <strong>Analysis Period:</strong> {self.days_range} days<br>
            <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC<br>
            <strong>Generated by:</strong> {self.env.user.name}<br>
            <strong>AI Provider:</strong> {dict(self._fields['llm_provider'].selection).get(self.llm_provider)}
        </div>
        
        <div class="summary-content">
            {summary_content}
        </div>
        
        <div style="page-break-before: always;">
            <h2>Raw Data Analysis</h2>
            <pre style="background: #f8f9fa; padding: 15px; font-size: 10px; white-space: pre-wrap;">{data_preview}</pre>
        </div>
        """
        
        return pdf_css + content_body + pdf_footer

    # def _call_claude(self, prompt):
    #     """Call Claude API - implement when ready"""
    #     return "<p>Claude integration ready - add your API key to enable.</p>"
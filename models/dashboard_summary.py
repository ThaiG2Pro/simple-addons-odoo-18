import requests
import json
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
    
    def _call_groq(self, prompt):
            """Real Groq API call"""
            
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
                    formatted_text = ai_text.replace('\n', '<br>')
                    return f"<div style='font-family: Arial;'>{formatted_text}</div>"
                else:
                    return f"<p>Error: {response.status_code} - {response.text}</p>"
                    
            except Exception as e:
                return f"<p>API Error: {str(e)}</p>"
    
    # def _call_claude(self, prompt):
    #     """Call Claude API - implement when ready"""
    #     return "<p>Claude integration ready - add your API key to enable.</p>"
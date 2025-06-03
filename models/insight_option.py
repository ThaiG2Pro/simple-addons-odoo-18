from odoo import models, fields, api

class DashboardInsightOption(models.Model):
    _name = 'dashboard.insight.option'
    _description = 'Dashboard Insight Options'
    
    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    category = fields.Selection([
        ('sales', 'Sales'),
        ('inventory', 'Inventory'),
        ('manufacturing', 'Manufacturing'),
    ], string='Category', required=True)
    active = fields.Boolean('Active', default=True)
    color = fields.Integer('Color', default=1)  # Add the missing color field
    
    _sql_constraints = [
        ('unique_code_category', 'unique(code, category)', 'Code must be unique per category!'),
    ]
    
    @api.model
    def create_default_insights(self):
        """Create default insight options if they don't exist"""
        insights_data = [
            # Sales insights
            {'name': 'Revenue Trends & Performance', 'code': 'revenue_trends', 'category': 'sales', 'color': 1},
            {'name': 'Top Customers Analysis', 'code': 'customer_analysis', 'category': 'sales', 'color': 2},
            {'name': 'Product Sales Performance', 'code': 'product_performance', 'category': 'sales', 'color': 3},
            {'name': 'Order Patterns & Behavior', 'code': 'order_patterns', 'category': 'sales', 'color': 4},
            {'name': 'Growth Opportunities', 'code': 'growth_opportunities', 'category': 'sales', 'color': 5},
            
            # Inventory insights
            {'name': 'Stock Level Analysis', 'code': 'stock_levels', 'category': 'inventory', 'color': 6},
            {'name': 'Product Movement Trends', 'code': 'movement_trends', 'category': 'inventory', 'color': 7},
            {'name': 'Reorder Point Optimization', 'code': 'reorder_points', 'category': 'inventory', 'color': 8},
            {'name': 'Slow Moving Products', 'code': 'slow_moving', 'category': 'inventory', 'color': 9},
            {'name': 'Inventory Valuation', 'code': 'valuation', 'category': 'inventory', 'color': 10},
            
            # Manufacturing insights
            {'name': 'Production Efficiency', 'code': 'efficiency', 'category': 'manufacturing', 'color': 11},
            {'name': 'Resource Utilization', 'code': 'utilization', 'category': 'manufacturing', 'color': 12},
            {'name': 'Quality Control Metrics', 'code': 'quality', 'category': 'manufacturing', 'color': 1},
            {'name': 'Production Bottlenecks', 'code': 'bottlenecks', 'category': 'manufacturing', 'color': 2},
            {'name': 'Capacity Planning', 'code': 'capacity', 'category': 'manufacturing', 'color': 3},
        ]
        
        for data in insights_data:
            existing = self.search([('code', '=', data['code']), ('category', '=', data['category'])])
            if not existing:
                self.create(data)
        
        return True

import requests
import json
import re
import markdown
import base64
from datetime import datetime, timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class DashboardSummary(models.TransientModel):
    _name = 'dashboard.summary'
    _description = 'AI Dashboard Summary'

    summary_type = fields.Selection([
    ('sales', 'Sales Summary'),
    ('inventory', 'Inventory Summary'),
    ('manufacturing', 'Manufacturing Summary'),
    ('combined', 'Combined Summary')
    ], string='Summary Type', default='sales', required=True)
    
    summary_text = fields.Html('AI Summary', readonly=True)
    data_preview = fields.Text('Data Preview', readonly=True)
    llm_provider = fields.Selection([
        ('mock', 'Mock/Demo (No API)'),
        ('groq', 'Groq AI'),
        
    ], string='AI Provider', default='mock', required=True)
    
    # Model updates
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date', default=fields.Date.today)

    # New insight selection fields
    sales_insights = fields.Selection([
        ('revenue_trends', 'Revenue Trends & Performance'),
        ('customer_analysis', 'Top Customers Analysis'),
        ('product_performance', 'Product Sales Performance'),
        ('order_patterns', 'Order Patterns & Behavior'),
        ('growth_opportunities', 'Growth Opportunities'),
    ], string='Sales Insight', help='Select specific sales insight to focus on')
    
    sales_insights_multi = fields.Many2many(
        'dashboard.insight.option', 
        'summary_sales_insight_rel', 
        'summary_id', 
        'insight_id',
        string='Sales Insights (Select 2-3)',
        domain=[('category', '=', 'sales')],
        help='Select 2-3 specific sales insights'
    )
    
    inventory_insights_multi = fields.Many2many(
        'dashboard.insight.option', 
        'summary_inventory_insight_rel', 
        'summary_id', 
        'insight_id',
        string='Inventory Insights (Select 2-3)',
        domain=[('category', '=', 'inventory')],
        help='Select 2-3 specific inventory insights'
    )
    
    manufacturing_insights_multi = fields.Many2many(
        'dashboard.insight.option', 
        'summary_manufacturing_insight_rel', 
        'summary_id', 
        'insight_id',
        string='Manufacturing Insights (Select 2-3)',
        domain=[('category', '=', 'manufacturing')],
        help='Select 2-3 specific manufacturing insights'
    )

    @api.onchange('date_start')
    def _onchange_date_start(self):
        if self.date_start and self.date_end and self.date_start > self.date_end:
            self.date_end = self.date_start

    @api.onchange('date_end')
    def _onchange_date_end(self):
        if self.date_start and self.date_end and self.date_start > self.date_end:
            self.date_start = self.date_end

    @api.constrains('sales_insights_multi', 'inventory_insights_multi', 'manufacturing_insights_multi')
    def _check_insight_limits(self):
        """Ensure users select 2-3 insights maximum"""
        for record in self:
            if record.summary_type == 'sales' and len(record.sales_insights_multi) > 3:
                raise ValidationError("Please select maximum 3 sales insights.")
            if record.summary_type == 'inventory' and len(record.inventory_insights_multi) > 3:
                raise ValidationError("Please select maximum 3 inventory insights.")
            if record.summary_type == 'manufacturing' and len(record.manufacturing_insights_multi) > 3:
                raise ValidationError("Please select maximum 3 manufacturing insights.")

    @api.onchange('summary_type')
    def _onchange_summary_type(self):
        """Clear insight selections when summary type changes"""
        if self.summary_type:
            self.sales_insights_multi = [(5, 0, 0)]  # Clear all
            self.inventory_insights_multi = [(5, 0, 0)]
            self.manufacturing_insights_multi = [(5, 0, 0)]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        today = fields.Date.today()
        if 'date_end' in fields_list and 'date_end' not in res:
            res['date_end'] = today
        if 'date_start' in fields_list and 'date_start' not in res:
            res['date_start'] = today - timedelta(days=30)
        # Set welcome message
        if 'summary_text' in fields_list and 'summary_text' not in res:
            res['summary_text'] = f'<p>Ready to generate summary for {self.env.user.name}</p>'
        return res
    
    def action_generate_summary(self):
        """Generate AI summary based on selected type and insights"""
        
        try:
            # Validate that insights are selected
            self._validate_insight_selection()

            if self.summary_type == 'sales':
                data_text = self._get_sales_data_selective()
            elif self.summary_type == 'inventory':
                data_text = self._get_inventory_data_selective()
            elif self.summary_type == 'manufacturing':
                data_text = self._get_manufacturing_data_selective()
            else:  # combined
                sales_data = self._get_sales_data()
                inventory_data = self._get_inventory_data()
                manufacturing_data = self._get_manufacturing_data()
                data_text = f"SALES DATA:\n{sales_data}\n\nINVENTORY DATA:\n{inventory_data}\n\nMANUFACTURING DATA:\n{manufacturing_data}"
            
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

    def _validate_insight_selection(self):
        """Validate that appropriate insights are selected"""
        if self.summary_type == 'sales' and not self.sales_insights_multi:
            raise UserError("Please select at least one sales insight before generating summary.")
        elif self.summary_type == 'inventory' and not self.inventory_insights_multi:
            raise UserError("Please select at least one inventory insight before generating summary.")
        elif self.summary_type == 'manufacturing' and not self.manufacturing_insights_multi:
            raise UserError("Please select at least one manufacturing insight before generating summary.")
    
    def _get_sales_data(self):
        """Extract sales data for analysis"""
        end_date = self.date_end 
        start_date = self.date_start 

        if not end_date:
            end_date = fields.Date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

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

    def _get_sales_data_selective(self):
        """Extract sales data based on selected insights"""
        end_date = self.date_end 
        start_date = self.date_start 

        peak_day = ('N/A', 0)


        if not end_date:
            end_date = fields.Date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        selected_insights = self.sales_insights_multi.mapped('code')
        
        sales_orders = self.env['sale.order'].search([
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('state', 'in', ['sale', 'done'])
        ])
        
        if not sales_orders:
            return "No sales data found for the selected period."
        
        insights_data = []
        
        # Revenue Trends & Performance
        if 'revenue_trends' in selected_insights:
            total_amount = sum(sales_orders.mapped('amount_total'))
            total_orders = len(sales_orders)
            avg_order = total_amount / total_orders if total_orders else 0
            
            # Compare with previous period
            prev_start = start_date - timedelta(days=(end_date - start_date).days)
            prev_end = start_date - timedelta(days=1)
            prev_orders = self.env['sale.order'].search([
                ('date_order', '>=', prev_start),
                ('date_order', '<=', prev_end),
                ('state', 'in', ['sale', 'done'])
            ])
            prev_amount = sum(prev_orders.mapped('amount_total'))
            growth_rate = ((total_amount - prev_amount) / prev_amount * 100) if prev_amount else 0
            
            insights_data.append(f"""
REVENUE TRENDS & PERFORMANCE:
• Current Period Revenue: ${total_amount:,.2f}
• Total Orders: {total_orders}
• Average Order Value: ${avg_order:,.2f}
• Growth Rate vs Previous Period: {growth_rate:+.1f}%
• Revenue per Day: ${total_amount / (end_date - start_date).days:,.2f}
            """.strip())
        
        # Customer Analysis
        if 'customer_analysis' in selected_insights:
            customers = {}
            customer_orders = {}
            for order in sales_orders:
                customer = order.partner_id.name
                customers[customer] = customers.get(customer, 0) + order.amount_total
                customer_orders[customer] = customer_orders.get(customer, 0) + 1
            
            top_customers = sorted(customers.items(), key=lambda x: x[1], reverse=True)[:5]
            total_customers = len(customers)
            avg_customer_value = sum(customers.values()) / total_customers if total_customers else 0
            
            insights_data.append(f"""
TOP CUSTOMERS ANALYSIS:
• Total Unique Customers: {total_customers}
• Average Customer Value: ${avg_customer_value:,.2f}
• Top 5 Customers: {', '.join([f"{name} (${amount:,.0f})" for name, amount in top_customers])}
• Top Customer Orders: {', '.join([f"{name} ({customer_orders[name]} orders)" for name, _ in top_customers[:3]])}
            """.strip())
        
        # Product Performance
        if 'product_performance' in selected_insights:
            order_lines = sales_orders.mapped('order_line')
            products = {}
            product_revenue = {}
            for line in order_lines:
                product = line.product_id.name
                products[product] = products.get(product, 0) + line.product_uom_qty
                product_revenue[product] = product_revenue.get(product, 0) + line.price_subtotal
            
            top_products_qty = sorted(products.items(), key=lambda x: x[1], reverse=True)[:5]
            top_products_revenue = sorted(product_revenue.items(), key=lambda x: x[1], reverse=True)[:5]
            
            insights_data.append(f"""
PRODUCT SALES PERFORMANCE:
• Top Products by Quantity: {', '.join([f"{name} ({qty:.0f} units)" for name, qty in top_products_qty])}
• Top Products by Revenue: {', '.join([f"{name} (${rev:,.0f})" for name, rev in top_products_revenue])}
• Total Products Sold: {len(products)} unique products
• Total Quantity Sold: {sum(products.values()):.0f} units
            """.strip())
        
        # Order Patterns
        if 'order_patterns' in selected_insights:
            # Analyze order patterns by day of week and month
            from collections import defaultdict
            day_patterns = defaultdict(int)
            month_patterns = defaultdict(float)

            for order in sales_orders:
                day_name = order.date_order.strftime('%A')
                month_name = order.date_order.strftime('%B')
                day_patterns[day_name] += 1
                month_patterns[month_name] += order.amount_total
            
            peak_day = max(day_patterns.items(), key=lambda x: x[1]) if day_patterns else ('N/A', 0)
            peak_month_revenue = max(month_patterns.items(), key=lambda x: x[1]) if month_patterns else ('N/A', 0)
            
            # Order size analysis
            order_sizes = sales_orders.mapped('amount_total')
            avg_size = sum(order_sizes) / len(order_sizes) if order_sizes else 0
            large_orders = len([o for o in order_sizes if o > avg_size * 1.5])
            
            insights_data.append(f"""
ORDER PATTERNS & BEHAVIOR:
• Peak Order Day: {peak_day[0]} ({peak_day[1]} orders)
• Peak Revenue Month: {peak_month_revenue[0]} (${peak_month_revenue[1]:,.0f})
• Large Orders (>150% avg): {large_orders} orders
• Order Size Distribution: Avg ${avg_size:,.0f}, Min ${min(order_sizes):,.0f}, Max ${max(order_sizes):,.0f}
            """.strip())
        
        # Growth Opportunities
        if 'growth_opportunities' in selected_insights:
            # Ensure 'customers' and 'avg_customer_value' are defined
            if 'customer_analysis' in selected_insights:
                # Use already computed values
                pass  # 'customers' and 'avg_customer_value' already set above
            else:
                customers = {}
                for order in sales_orders:
                    customer = order.partner_id.name
                    customers[customer] = customers.get(customer, 0) + order.amount_total
                total_customers = len(customers)
                avg_customer_value = sum(customers.values()) / total_customers if total_customers else 0
            
            # Identify opportunities based on data patterns
            opportunities = []
            
            # Low-frequency customers with high value
            customer_frequency = {}
            for order in sales_orders:
                customer = order.partner_id.name
                customer_frequency[customer] = customer_frequency.get(customer, 0) + 1
            
            high_value_low_freq = []
            for customer, revenue in customers.items():
                if customer_frequency.get(customer, 0) <= 2 and revenue > avg_customer_value:
                    high_value_low_freq.append(customer)
            
            # Product cross-sell opportunities
            single_product_customers = 0
            for customer in customers:
                customer_products = set()
                for order in sales_orders.filtered(lambda o: o.partner_id.name == customer):
                    for line in order.order_line:
                        customer_products.add(line.product_id.name)
                if len(customer_products) == 1:
                    single_product_customers += 1
            
            insights_data.append(f"""
SALES GROWTH OPPORTUNITIES:
• High-Value Low-Frequency Customers: {len(high_value_low_freq)} customers (upsell opportunity)
• Single-Product Customers: {single_product_customers} customers (cross-sell opportunity)
• Market Expansion: Focus on {peak_day[0]}s for promotions
• Product Bundling: Top products could be bundled for increased AOV
            """.strip())
        
        return f"""
SALES ANALYSIS ({start_date} to {end_date}) - FOCUSED INSIGHTS:
Selected Insights: {', '.join([insight.name for insight in self.sales_insights_multi])}

{chr(10).join(insights_data)}
        """.strip()

    def _get_inventory_data(self):
        """Extract inventory data for analysis"""
        end_date = self.date_end 
        start_date = self.date_start 

        if not end_date:
            end_date = fields.Date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        stock_moves = self.env['stock.move'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', '=', 'done')
        ])
        
        if not stock_moves:
            return "No inventory movements found for the selected period."
        
        # Analyze stock movements
        total_moves = len(stock_moves)
        incoming_moves = stock_moves.filtered(lambda m: m.location_dest_id.usage == 'internal')
        outgoing_moves = stock_moves.filtered(lambda m: m.location_id.usage == 'internal')
        
        # Product analysis
        products = {}
        for move in stock_moves:
            product = move.product_id.name
            if product not in products:
                products[product] = {'in': 0, 'out': 0, 'net': 0}
            
            if move.location_dest_id.usage == 'internal':
                products[product]['in'] += move.product_uom_qty
            elif move.location_id.usage == 'internal':
                products[product]['out'] += move.product_uom_qty
            
            products[product]['net'] = products[product]['in'] - products[product]['out']
        
        # Top moved products
        top_products = sorted(products.items(), key=lambda x: abs(x[1]['net']), reverse=True)[:5]
        
        # Current stock levels (quants)
        stock_quants = self.env['stock.quant'].search([
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0)
        ])
        
        # Low stock products (assuming reorder point exists)
        low_stock_products = []
        for quant in stock_quants:
            if quant.product_id.reordering_min_qty > 0 and quant.quantity <= quant.product_id.reordering_min_qty:
                low_stock_products.append((quant.product_id.name, quant.quantity, quant.product_id.reordering_min_qty))
        
        total_stock_value = sum(quant.quantity * quant.product_id.standard_price for quant in stock_quants)
        
        return f"""
    INVENTORY PERFORMANCE ({start_date} to {end_date}):
    • Total Stock Movements: {total_moves}
    • Incoming Movements: {len(incoming_moves)}
    • Outgoing Movements: {len(outgoing_moves)}
    • Total Stock Value: ${total_stock_value:,.2f}
    • Top Products by Movement: {', '.join([f"{name} (Net: {data['net']:.0f})" for name, data in top_products])}
    • Low Stock Alerts: {len(low_stock_products)} products below reorder point
    • Critical Stock Items: {', '.join([f"{name} ({qty:.0f}/{min_qty:.0f})" for name, qty, min_qty in low_stock_products[:3]])}
        """.strip()

    def _get_inventory_data_selective(self):
        """Extract inventory data based on selected insights"""
        end_date = self.date_end 
        start_date = self.date_start 

        if not end_date:
            end_date = fields.Date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        selected_insights = self.inventory_insights_multi.mapped('code')
        insights_data = []
        
        # Get base inventory data
        stock_moves = self.env['stock.move'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', '=', 'done')
        ])
        
        stock_quants = self.env['stock.quant'].search([
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0)
        ])
        
        if not stock_moves and not stock_quants:
            return "No inventory data found for the selected period."
        
        # Stock Level Analysis
        if 'stock_levels' in selected_insights:
            total_stock_value = sum(quant.quantity * quant.product_id.standard_price for quant in stock_quants)
            total_items = len(stock_quants)
            avg_stock_value = total_stock_value / total_items if total_items else 0
            
            # High value products
            high_value_products = []
            for quant in stock_quants:
                product_value = quant.quantity * quant.product_id.standard_price
                if product_value > avg_stock_value * 2:
                    high_value_products.append((quant.product_id.name, product_value, quant.quantity))
            
            high_value_products = sorted(high_value_products, key=lambda x: x[1], reverse=True)[:5]
            
            insights_data.append(f"""
STOCK LEVEL ANALYSIS:
• Total Stock Value: ${total_stock_value:,.2f}
• Total Stock Items: {total_items} products
• Average Product Value: ${avg_stock_value:,.2f}
• High-Value Inventory: {', '.join([f"{name} (${val:,.0f})" for name, val, qty in high_value_products])}
• Stock Distribution: {len([q for q in stock_quants if q.quantity > 100])} products with >100 units
            """.strip())
        
        # Movement & Turnover
        product_movements = None
        if 'movement_turnover' in selected_insights:
            product_movements = {}
            for move in stock_moves:
                product = move.product_id.name
                if product not in product_movements:
                    product_movements[product] = {'in': 0, 'out': 0}
                if move.location_dest_id.usage == 'internal':
                    product_movements[product]['in'] += move.product_uom_qty
                elif move.location_id.usage == 'internal':
                    product_movements[product]['out'] += move.product_uom_qty
            
            total_moves = len(stock_moves)
            incoming_moves = stock_moves.filtered(lambda m: m.location_dest_id.usage == 'internal')
            outgoing_moves = stock_moves.filtered(lambda m: m.location_id.usage == 'internal')
            
            # Calculate turnover for products
            high_turnover = []
            for product, movements in product_movements.items():
                if movements['out'] > 0:
                    turnover = movements['out'] / max(movements['in'], 1)
                    if turnover > 0.5:  # High turnover threshold
                        high_turnover.append((product, turnover, movements['out']))
            
            high_turnover = sorted(high_turnover, key=lambda x: x[1], reverse=True)[:5]
            
            insights_data.append(f"""
MOVEMENT & TURNOVER ANALYSIS:
• Total Stock Movements: {total_moves}
• Incoming Movements: {len(incoming_moves)} ({len(incoming_moves)/total_moves*100:.1f}% if total_moves else 0)
• Outgoing Movements: {len(outgoing_moves)} ({len(outgoing_moves)/total_moves*100:.1f}% if total_moves else 0)
• High Turnover Products: {', '.join([f"{name} ({rate:.1f}x turnover)" for name, rate, out in high_turnover])}
• Movement Velocity: {total_moves / (end_date - start_date).days:.1f} movements per day
            """.strip())
        
        # Reorder Alerts
        if 'reorder_alerts' in selected_insights:
            product_movements = {}
            low_stock_products = []
            critical_stock_products = []
            for quant in stock_quants:
                if quant.product_id.reordering_min_qty > 0:
                    if quant.quantity <= quant.product_id.reordering_min_qty:
                        low_stock_products.append((quant.product_id.name, quant.quantity, quant.product_id.reordering_min_qty))
                    if quant.quantity <= quant.product_id.reordering_min_qty * 0.5:
                        critical_stock_products.append((quant.product_id.name, quant.quantity, quant.product_id.reordering_min_qty))
            
            # Stockout risk prediction
            stockout_risk = []
            for product, movements in product_movements.items():
                if movements['out'] > 0:
                    current_stock = next((q.quantity for q in stock_quants if q.product_id.name == product), 0)
                    avg_daily_usage = movements['out'] / (end_date - start_date).days
                    days_until_stockout = current_stock / avg_daily_usage if avg_daily_usage > 0 else float('inf')
                    if days_until_stockout < 30:  # Less than 30 days
                        stockout_risk.append((product, days_until_stockout, current_stock))
            
            stockout_risk = sorted(stockout_risk, key=lambda x: x[1])[:5]
            
            insights_data.append(f"""
LOW STOCK & REORDER ALERTS:
• Products Below Reorder Point: {len(low_stock_products)} items
• Critical Stock Items: {', '.join([f"{name} ({qty:.0f}/{min_qty:.0f})" for name, qty, min_qty in critical_stock_products[:3]])}
• Stockout Risk (30 days): {', '.join([f"{name} ({days:.0f} days)" for name, days, stock in stockout_risk])}
• Immediate Action Required: {len(critical_stock_products)} critical items
            """.strip())
        
        # Product Performance Inventory
        if 'product_performance_inv' in selected_insights:
            # Fast vs slow moving analysis
            fast_moving = []
            slow_moving = []
            product_movements = {}
            for product, movements in product_movements.items():
                total_movement = movements['in'] + movements['out']
                if total_movement > 10:  # Fast moving threshold
                    fast_moving.append((product, total_movement))
                elif total_movement < 2:  # Slow moving threshold
                    slow_moving.append((product, total_movement))
            
            fast_moving = sorted(fast_moving, key=lambda x: x[1], reverse=True)[:5]
            slow_moving = sorted(slow_moving, key=lambda x: x[1])[:5]
            
            # Dead stock analysis
            dead_stock = []
            for quant in stock_quants:
                product = quant.product_id.name
                if product not in product_movements or product_movements[product]['out'] == 0:
                    dead_stock.append((product, quant.quantity, quant.quantity * quant.product_id.standard_price))
            
            dead_stock = sorted(dead_stock, key=lambda x: x[2], reverse=True)[:5]
            
            insights_data.append(f"""
PRODUCT PERFORMANCE (INVENTORY):
• Fast-Moving Products: {', '.join([f"{name} ({moves:.0f} movements)" for name, moves in fast_moving])}
• Slow-Moving Products: {', '.join([f"{name} ({moves:.0f} movements)" for name, moves in slow_moving])}
• Dead Stock Items: {', '.join([f"{name} (${val:,.0f})" for name, qty, val in dead_stock])}
• Movement Categories: {len(fast_moving)} fast, {len(slow_moving)} slow, {len(dead_stock)} dead stock
            """.strip())
        
        # Inventory Optimization
        if 'optimization' in selected_insights:
            # Calculate optimization opportunities
            total_value = sum(quant.quantity * quant.product_id.standard_price for quant in stock_quants)
            dead_stock_value = sum(val for _, _, val in dead_stock) if 'product_performance_inv' in selected_insights else 0
            
            # Overstock analysis
            overstock_items = []
            for quant in stock_quants:
                if quant.product_id.reordering_max_qty > 0 and quant.quantity > quant.product_id.reordering_max_qty:
                    excess_qty = quant.quantity - quant.product_id.reordering_max_qty
                    excess_value = excess_qty * quant.product_id.standard_price
                    overstock_items.append((quant.product_id.name, excess_qty, excess_value))
            
            overstock_value = sum(val for _, _, val in overstock_items)
            space_utilization = len([q for q in stock_quants if q.quantity > 0]) / max(len(stock_quants), 1) * 100
            
            insights_data.append(f"""
INVENTORY OPTIMIZATION OPPORTUNITIES:
• Total Inventory Investment: ${total_value:,.2f}
• Dead Stock Value: ${dead_stock_value:,.2f} ({dead_stock_value/total_value*100:.1f}% of total)
• Overstock Value: ${overstock_value:,.2f} ({len(overstock_items)} items)
• Space Utilization: {space_utilization:.1f}%
• Optimization Potential: ${dead_stock_value + overstock_value:,.2f} in working capital
            """.strip())
        
        return f"""
INVENTORY ANALYSIS ({start_date} to {end_date}) - FOCUSED INSIGHTS:
Selected Insights: {', '.join([insight.name for insight in self.inventory_insights_multi])}

{chr(10).join(insights_data)}
        """.strip()

    def _get_manufacturing_data(self):
        """Extract manufacturing data for analysis"""
        end_date = self.date_end
        start_date = self.date_start 

        if not end_date:
            end_date = fields.Date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        manufacturing_orders = self.env['mrp.production'].search([
            ('date_start', '>=', start_date),
            ('date_start', '<=', end_date)
        ])
        
        if not manufacturing_orders:
            return "No manufacturing orders found for the selected period."
        
        total_orders = len(manufacturing_orders)
        completed_orders = manufacturing_orders.filtered(lambda mo: mo.state == 'done')
        in_progress_orders = manufacturing_orders.filtered(lambda mo: mo.state == 'progress')
        planned_orders = manufacturing_orders.filtered(lambda mo: mo.state in ['draft', 'confirmed'])
        
        # Production analysis
        total_produced = sum(completed_orders.mapped('product_qty'))
        total_planned = sum(manufacturing_orders.mapped('product_qty'))
        
        # Product analysis
        products_produced = {}
        for order in completed_orders:
            product = order.product_id.name
            products_produced[product] = products_produced.get(product, 0) + order.product_qty
        
        top_products = sorted(products_produced.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Work center analysis
        workorders = self.env['mrp.workorder'].search([
            ('production_id', 'in', manufacturing_orders.ids)
        ])
        
        work_centers = {}
        for workorder in workorders:
            wc = workorder.workcenter_id.name
            work_centers[wc] = work_centers.get(wc, 0) + (workorder.duration or 0)
        
        # Efficiency metrics
        on_time_orders = 0
        for order in completed_orders:
            if order.date_finished and order.date_deadline:
                if order.date_finished <= order.date_deadline:
                    on_time_orders += 1
        
        on_time_rate = (on_time_orders / len(completed_orders) * 100) if completed_orders else 0
        
        return f"""
    MANUFACTURING PERFORMANCE ({start_date} to {end_date}):
    • Total Manufacturing Orders: {total_orders}
    • Completed Orders: {len(completed_orders)}
    • In Progress Orders: {len(in_progress_orders)}
    • Planned Orders: {len(planned_orders)}
    • Total Units Produced: {total_produced:.0f}
    • On-Time Delivery Rate: {on_time_rate:.1f}%
    • Top Products Produced: {', '.join([f"{name} ({qty:.0f} units)" for name, qty in top_products])}
    • Active Work Centers: {len(work_centers)} centers with {sum(work_centers.values()):.0f} total hours
        """.strip()
    
    def _get_manufacturing_data_selective(self):
        """Extract manufacturing data based on selected insights"""
        end_date = self.date_end
        start_date = self.date_start

        if not end_date:
            end_date = fields.Date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        selected_insights = self.manufacturing_insights_multi.mapped('code')
        insights_data = []

        manufacturing_orders = self.env['mrp.production'].search([
            ('date_start', '>=', start_date),
            ('date_start', '<=', end_date)
        ])
        if not manufacturing_orders:
            return "No manufacturing orders found for the selected period."

        completed_orders = manufacturing_orders.filtered(lambda mo: mo.state == 'done')
        in_progress_orders = manufacturing_orders.filtered(lambda mo: mo.state == 'progress')
        planned_orders = manufacturing_orders.filtered(lambda mo: mo.state in ['draft', 'confirmed'])

        # Production Efficiency
        if 'efficiency' in selected_insights:
            total_produced = sum(completed_orders.mapped('product_qty'))
            total_planned = sum(manufacturing_orders.mapped('product_qty'))
            completion_rate = len(completed_orders) / len(manufacturing_orders) * 100 if manufacturing_orders else 0
            insights_data.append(f"""
PRODUCTION EFFICIENCY:
• Total Units Produced: {total_produced:.0f} units
• Production Completion Rate: {completion_rate:.1f}%
• Output vs Planned: {total_produced}/{total_planned:.0f} units ({(total_produced/total_planned*100) if total_planned else 0:.1f}%)
            """.strip())

        # Resource Utilization
        if 'utilization' in selected_insights:
            workorders = self.env['mrp.workorder'].search([
                ('production_id', 'in', manufacturing_orders.ids)
            ])
            work_centers = {}
            for workorder in workorders:
                wc = workorder.workcenter_id.name
                work_centers[wc] = work_centers.get(wc, 0) + (workorder.duration or 0)
            total_work_hours = sum(work_centers.values())
            avg_wc_utilization = total_work_hours / len(work_centers) if work_centers else 0
            insights_data.append(f"""
RESOURCE UTILIZATION:
• Total Work Centers: {len(work_centers)}
• Total Production Hours: {total_work_hours:.1f} hours
• Average Utilization per Center: {avg_wc_utilization:.1f} hours
            """.strip())

        # Quality Control Metrics
        if 'quality' in selected_insights:
            total_scrap = sum(order.scrap_ids.mapped('scrap_qty') for order in completed_orders if order.scrap_ids)
            total_produced = sum(completed_orders.mapped('product_qty'))
            scrap_rate = (total_scrap / total_produced * 100) if total_produced else 0
            successful_orders = completed_orders.filtered(lambda o: o.state == 'done' and not o.scrap_ids)
            first_pass_yield = len(successful_orders) / len(completed_orders) * 100 if completed_orders else 0
            insights_data.append(f"""
QUALITY CONTROL METRICS:
• Scrap Rate: {scrap_rate:.2f}% of total production
• First-Pass Yield: {first_pass_yield:.1f}% orders without rework
• Clean Completions: {len(successful_orders)}/{len(completed_orders)}
            """.strip())

        # Production Bottlenecks
        if 'bottlenecks' in selected_insights:
            workorders = self.env['mrp.workorder'].search([
                ('production_id', 'in', manufacturing_orders.ids)
            ])
            work_centers = {}
            for workorder in workorders:
                wc = workorder.workcenter_id.name
                work_centers[wc] = work_centers.get(wc, 0) + (workorder.duration or 0)
            bottlenecks = sorted(work_centers.items(), key=lambda x: x[1], reverse=True)[:3]
            insights_data.append(f"""
PRODUCTION BOTTLENECKS:
• Top Bottleneck Centers: {', '.join([f'{name} ({hours:.1f}h)' for name, hours in bottlenecks])}
            """.strip())

        # Capacity Planning
        if 'capacity' in selected_insights:
            avg_lead_time = 0
            lead_times = []
            for order in completed_orders:
                if order.date_start and order.date_finished:
                    lead_time = (order.date_finished - order.date_start).days
                    lead_times.append(lead_time)
            if lead_times:
                avg_lead_time = sum(lead_times) / len(lead_times)
            backlog_value = sum(order.product_qty * (order.product_id.standard_price or 0) for order in planned_orders)
            insights_data.append(f"""
CAPACITY PLANNING:
• Average Lead Time: {avg_lead_time:.1f} days
• Production Backlog: {len(planned_orders)} orders (${backlog_value:,.0f} value)
            """.strip())

        # Production Performance (main summary)
        if 'production_performance' in selected_insights or 'performance' in selected_insights:
            total_orders = len(manufacturing_orders)
            total_produced = sum(completed_orders.mapped('product_qty'))
            total_planned = sum(manufacturing_orders.mapped('product_qty'))
            on_time_orders = 0
            for order in completed_orders:
                if order.date_finished and order.date_deadline:
                    if order.date_finished <= order.date_deadline:
                        on_time_orders += 1
            on_time_rate = (on_time_orders / len(completed_orders) * 100) if completed_orders else 0
            products_produced = {}
            for order in completed_orders:
                product = order.product_id.name
                products_produced[product] = products_produced.get(product, 0) + order.product_qty
            top_products = sorted(products_produced.items(), key=lambda x: x[1], reverse=True)[:5]
            workorders = self.env['mrp.workorder'].search([
                ('production_id', 'in', manufacturing_orders.ids)
            ])
            work_centers = {}
            for workorder in workorders:
                wc = workorder.workcenter_id.name
                work_centers[wc] = work_centers.get(wc, 0) + (workorder.duration or 0)
            insights_data.append(f"""
PRODUCTION PERFORMANCE:
• Total Manufacturing Orders: {total_orders}
• Completed Orders: {len(completed_orders)}
• In Progress Orders: {len(in_progress_orders)}
• Planned Orders: {len(planned_orders)}
• Total Units Produced: {total_produced:.0f}
• On-Time Delivery Rate: {on_time_rate:.1f}%
• Top Products Produced: {', '.join([f"{name} ({qty:.0f} units)" for name, qty in top_products])}
• Active Work Centers: {len(work_centers)} centers with {sum(work_centers.values()):.0f} total hours
            """.strip())

        return f"""
MANUFACTURING ANALYSIS ({start_date} to {end_date}) - FOCUSED INSIGHTS:
Selected Insights: {chr(10).join([insight.name for insight in self.manufacturing_insights_multi])}

{chr(10).join(insights_data)}
        """.strip()

    def _call_llm(self, data_text):
        """Call LLM API for summary generation"""
        
        data_type = "Sales" if "SALES PERFORMANCE" in data_text else \
                    "Inventory" if "INVENTORY PERFORMANCE" in data_text else \
                    "Manufacturing" if "MANUFACTURING PERFORMANCE" in data_text else \
                    "Combined Business"
        
        prompt = f"""
    You are a business analyst specializing in {data_type.lower()} operations. Analyze this business data and provide insights:
    
    {data_text}
    
    Please provide:
    1. Key Performance Highlights
    2. Notable Trends or Patterns  
    3. Operational Insights
    4. Actionable Recommendations
    
    Focus on {data_type.lower()}-specific metrics and KPIs. Keep it concise but insightful. Use bullet points and business language.
    Current date: {datetime.now().strftime('%Y-%m-%d')}
    Analysis requested by: {self.env.user.name}
        """.strip()
        
        if self.llm_provider == 'mock':
            return self._generate_mock_summary(data_text)
        elif self.llm_provider == 'groq':
            return self._call_groq_api(prompt)
        else:
            return "<p>Please select a valid LLM provider.</p>"
    
    def _generate_mock_summary(self, data_text):
        """Generate a mock summary for demo purposes"""
        lines = data_text.strip().split('\n')
        
        if "INVENTORY PERFORMANCE" in data_text:
            summary = f"""
            <h3>🏭 Inventory Analysis Summary</h3>
            <p><strong>Analysis Period:</strong> {lines[0].split('(')[1].split(')')[0] if '(' in lines[0] else 'Recent period'}</p>
            
            <h4>📊 Key Inventory Metrics:</h4>
            <ul>
                <li>✅ <strong>Stock Movement Activity:</strong> Good inventory flow detected</li>
                <li>📦 <strong>Stock Levels:</strong> Current inventory status reviewed</li>
                <li>⚠️ <strong>Low Stock Alerts:</strong> Monitor reorder points closely</li>
            </ul>
            
            <h4>💡 Inventory Insights:</h4>
            <ul>
                <li>Maintain optimal inventory levels to avoid stockouts</li>
                <li>Review slow-moving items for potential clearance</li>
                <li>Consider adjusting reorder points based on demand patterns</li>
            </ul>
            """
        elif "MANUFACTURING PERFORMANCE" in data_text:
            summary = f"""
            <h3>🏭 Manufacturing Analysis Summary</h3>
            <p><strong>Analysis Period:</strong> {lines[0].split('(')[1].split(')')[0] if '(' in lines[0] else 'Recent period'}</p>
            
            <h4>📊 Key Manufacturing Metrics:</h4>
            <ul>
                <li>🏭 <strong>Production Orders:</strong> Manufacturing pipeline active</li>
                <li>⏰ <strong>On-Time Delivery:</strong> Schedule adherence tracked</li>
                <li>🔧 <strong>Work Center Utilization:</strong> Resource allocation optimized</li>
            </ul>
            
            <h4>💡 Manufacturing Insights:</h4>
            <ul>
                <li>Focus on improving on-time delivery rates</li>
                <li>Optimize work center scheduling for better efficiency</li>
                <li>Monitor production bottlenecks and capacity constraints</li>
            </ul>
            """
        else:
            # Default sales summary or combined
            summary = f"""
            <h3>📈 Business Analysis Summary</h3>
            <p><strong>Analysis Period:</strong> Recent business performance</p>
            
            <h4>📊 Key Performance Indicators:</h4>
            <ul>
                <li>💰 <strong>Revenue Trends:</strong> Financial performance tracked</li>
                <li>📦 <strong>Operational Efficiency:</strong> Process optimization opportunities</li>
                <li>🎯 <strong>Strategic Focus:</strong> Areas for improvement identified</li>
            </ul>
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
                    if html_parts and html_parts[-1].endswith('</li>'):
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

    def _call_groq_api(self, prompt):
        """Real LLM API call with improved response formatting"""

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
            
            # Debug: Check if HTML content is generated
            if not pdf_html or len(pdf_html) < 100:
                raise UserError("PDF content is empty or too short. Please check your summary content.")
            
            # Generate PDF
            pdf_content = HTML(string=pdf_html).write_pdf()
            
            if not pdf_content:
                raise UserError("PDF generation failed - no content returned.")
            
            # Encode PDF content to base64 for Odoo
            pdf_base64 = base64.b64encode(pdf_content).decode()
            
            # Create attachment
            filename = f"ai_summary_{self.summary_type}_{fields.Date.today()}.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': pdf_base64,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })
            
            # Alternative return for direct download
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
            
        except ImportError:
            raise UserError("WeasyPrint library is not installed. Please install it using: pip install weasyprint")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            raise UserError(f"Error generating PDF: {str(e)}\n\nDetails:\n{error_details}")
    
    def action_export_pdf_simple(self):
        """Simple PDF export using reportlab as fallback"""
        if not self.summary_text:
            raise UserError("Please generate a summary first before exporting to PDF.")
        
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import inch
            import io
            
            # Create PDF buffer
            buffer = io.BytesIO()
            
            # Create PDF document
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Title
            title = Paragraph(f"AI {self.summary_type.title()} Summary", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Meta info
            meta_text = f"""
            <b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC<br/>
            <b>Generated by:</b> {self.env.user.name}<br/>
            <b>Analysis Period:</b> {self.date_start} to {self.date_end}<br/>
            <b>AI Provider:</b> {dict(self._fields['llm_provider'].selection).get(self.llm_provider)}
            """
            meta_para = Paragraph(meta_text, styles['Normal'])
            story.append(meta_para)
            story.append(Spacer(1, 12))
            
            # Summary content (strip HTML tags for simple text)
            import re
            clean_text = re.sub('<[^<]+?>', '', self.summary_text or "No summary available")
            clean_text = clean_text.replace('&nbsp;', ' ').strip()
            
            content_para = Paragraph(clean_text, styles['Normal'])
            story.append(content_para)
            
            # Build PDF
            doc.build(story)
            pdf_content = buffer.getvalue()
            buffer.close()
            
            # Encode to base64
            pdf_base64 = base64.b64encode(pdf_content).decode()
            
            # Create attachment
            filename = f"ai_summary_{self.summary_type}_{fields.Date.today()}_simple.pdf"
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': pdf_base64,
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'application/pdf'
            })
            
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
        except ImportError:
            raise UserError("ReportLab library is not installed. Please install it using: pip install reportlab")
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            raise UserError(f"Error generating simple PDF: {str(e)}\n\nDetails:\n{error_details}")
    
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
                .highlight { background: #f39c12; color: white; padding: 1px 3px; border-radius: 3px; }
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
            <strong>Analysis Period:</strong> {self.date_start} to {self.date_end}<br>
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
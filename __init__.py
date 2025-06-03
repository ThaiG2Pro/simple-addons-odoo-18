# Empty init file
from . import models

def post_init_hook(cr, registry):
    """Initialize default insights after installation"""
    from odoo import api, SUPERUSER_ID
    
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        insight_model = env['dashboard.insight.option']
        insight_model.create_default_insights()
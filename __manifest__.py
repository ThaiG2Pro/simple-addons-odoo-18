{
    'name': 'Simple Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Simple dashboard to view core information from Sales and CRM',
    'description': """
        A simple dashboard addon that provides:
        - Top menu with sub-menus
        - View core information from Sales
        - View core information from CRM
        - AI powered insights
    """,
    'author': 'ThaiG2Pro',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'sale', 'crm'],
    'external_dependencies': {
        'python': ['markdown', 'requests'],  # weasyprint is optional for PDF export
    },
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/summary_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}

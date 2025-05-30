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
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'sale', 'crm'],
    'data': [
        'views/dashboard_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
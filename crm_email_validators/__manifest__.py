{
    'name': ' Crm Email Validator',
    'version': '16.0',
    'category': 'CRM',
    "author": "technians",
    'summary': 'Validate email domain via DNS MX record',
    'depends': ['base','crm'],
    'data': [
        'data/cron_email_validation.xml',
        'views/crm_lead_email_validation.xml',
        'views/res_config_setting.xml',
    ],
    'installable': True,
    'application': False,
}

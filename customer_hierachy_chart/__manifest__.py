{
    'name' : 'customer_hierachy_chart',
    'version': '16.0',
    'category': 'Contacts',
    'depends' : ['base', 'contacts','hr_attendance'],
    'description': "Geminate Consultancy Services",
    'data': [
        'security/ir.model.access.csv',
        'views/partner.xml',
        'wizard/child.xml',
        'views/attendances.xml',
    ],
    'qweb': [],
    'installable': True,
    'auto_install':False,
    'license': 'LGPL-3',
}

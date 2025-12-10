# __manifest__.py
# -*- coding: utf-8 -*-
{
    'name': 'School Trip Request',
    'version': '16.0.1.0.0',
    'summary': 'نموذج طلب رحلة مدرسية',
    'description': 'إدارة طلبات الرحلات المدرسية وطباعة النموذج العربي الرسمي مع شعار التهذيب.',
    'category': 'Education',
    'author': 'Knowledge Bonds',
    'website': 'https://knowledge-bonds.com',
    'depends': [
        'base', 
        'mail', 
        'fleet', 
        'event',
        'school',  # ✅ Added dependency on school module
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'data/school_trip_sequence.xml',
        'data/event_type_data.xml',
        'report/school_trip_report.xml',
        'views/school_trip_request_views.xml',
        'views/event_event_views.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            '/kb_school_trip_request/static/src/css/report.css',
        ],
    },
    'application': True,
    'installable': True,
    'license': 'LGPL-3',
}
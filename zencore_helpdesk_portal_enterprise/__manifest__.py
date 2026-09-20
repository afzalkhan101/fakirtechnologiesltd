{
    "name": "Zencore Helpdesk Portal",
    "summary": "Customer portal for Odoo 19 Enterprise Helpdesk",
    "version": "19.0.1.0.2",
    "category": "Services/Helpdesk",
    "author": "Zencore Solutions Limited",
    "website": "https://zencoreltd.com",
    "license": "LGPL-3",
    "depends": ["helpdesk", "portal", "website", "mail"],
    "data": [
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "zencore_helpdesk_portal_enterprise/static/src/css/helpdesk_portal.css",
        ],
    },
    "installable": True,
    "application": False,
}

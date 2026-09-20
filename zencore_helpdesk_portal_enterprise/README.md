# Zencore Helpdesk Portal - Odoo 19 Enterprise

This add-on is a **portal extension for the native Odoo 19 Enterprise Helpdesk**. It does not create a parallel Helpdesk backend.

## Dependencies
- Odoo 19 Enterprise
- Helpdesk (`helpdesk`)
- Portal
- Website
- Mail

## Native Enterprise features reused
- `helpdesk.ticket`
- `helpdesk.team`
- `helpdesk.stage`
- `helpdesk.tag`
- SLA policies
- automatic assignment
- native chatter / followers
- native reporting and Helpdesk dashboard

## Portal features
- `/my/helpdesk` dashboard
- ticket counts: all/open/urgent/closed
- create ticket
- native Helpdesk Team selection
- Category/Tag selection
- priority
- description
- multiple attachments
- ticket list with search/filter/sort
- ticket details
- customer replies in native ticket chatter
- attachment download
- close/reopen using Helpdesk stages
- portal ownership/follower isolation

## Required Helpdesk configuration
For customer-facing teams, configure Helpdesk > Configuration > Helpdesk Teams and use the portal/public visibility option. Odoo's Helpdesk documentation describes this as **Invited portal users and all internal users (public)**.

For Close/Reopen, at least one open stage and one folded/closed stage must be configured for the team.

## Install
Copy `zencore_helpdesk_portal_enterprise` into your custom addons path, update Apps List, and install **Zencore Helpdesk Portal - Enterprise**.

CLI example:

```bash
./odoo-bin -c /etc/odoo19.conf -d YOUR_DB -u zencore_helpdesk_portal_enterprise --stop-after-init
```

Portal URL:

```text
/my/helpdesk
```

## Notes
The add-on intentionally leaves the Enterprise backend untouched. SLA, assignment rules, ticket stages, Helpdesk reporting and agent workflow continue to be managed from Odoo's native Helpdesk application.

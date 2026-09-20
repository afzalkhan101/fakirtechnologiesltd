import base64
from collections import OrderedDict
from markupsafe import Markup, escape
from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers import portal
from odoo.addons.portal.controllers.portal import pager as portal_pager


class ZencoreEnterpriseHelpdeskPortal(portal.CustomerPortal):

    def _ticket_domain(self):
        partner = request.env.user.partner_id
        return [
            "|",
            ("partner_id", "=", partner.id),
            ("message_partner_ids", "in", partner.id),
        ]

    def _portal_team_domain(self):
        Team = request.env["helpdesk.team"].sudo()
        domain = []
        if "active" in Team._fields:
            domain.append(("active", "=", True))

        # Prefer teams explicitly enabled for Odoo's native website Helpdesk form.
        if "use_website_helpdesk_form" in Team._fields:
            website_domain = domain + [("use_website_helpdesk_form", "=", True)]
            if Team.search_count(website_domain):
                domain = website_domain

        # Odoo Enterprise uses the public/portal visibility for customer portal access.
        if "privacy_visibility" in Team._fields:
            portal_domain = domain + [("privacy_visibility", "=", "portal")]
            if Team.search_count(portal_domain):
                domain = portal_domain
        return domain

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "zc_helpdesk_ticket_count" in counters:
            values["zc_helpdesk_ticket_count"] = request.env["helpdesk.ticket"].sudo().search_count(
                self._ticket_domain()
            )
        return values

    def _closed_domain(self, closed=True):
        Stage = request.env["helpdesk.stage"]
        if "fold" in Stage._fields:
            return [("stage_id.fold", "=", closed)]
        if "is_close" in Stage._fields:
            return [("stage_id.is_close", "=", closed)]
        if "closed" in Stage._fields:
            return [("stage_id.closed", "=", closed)]
        return []

    def _prepare_dashboard_values(self):
        Ticket = request.env["helpdesk.ticket"].sudo()
        domain = self._ticket_domain()
        closed_domain = self._closed_domain(True)
        open_domain = self._closed_domain(False)
        return {
            "ticket_count": Ticket.search_count(domain),
            "open_count": Ticket.search_count(domain + open_domain),
            "closed_count": Ticket.search_count(domain + closed_domain),
            "urgent_count": Ticket.search_count(domain + open_domain + [("priority", "=", "3")]),
        }

    def _get_portal_ticket(self, ticket_id):
        return request.env["helpdesk.ticket"].sudo().search(
            self._ticket_domain() + [("id", "=", ticket_id)],
            limit=1,
        )

    def _safe_html(self, text):
        escaped = escape(text or "")
        return Markup(str(escaped).replace("\n", "<br/>"))

    def _visible_messages(self, ticket):
        messages = ticket.sudo().message_ids.filtered(
            lambda message: message.message_type in ("comment", "email")
        )
        if "internal" in request.env["mail.message.subtype"]._fields:
            messages = messages.filtered(
                lambda message: not message.subtype_id or not message.subtype_id.internal
            )
        return messages.sorted(key=lambda message: (message.date, message.id))

    @http.route(["/my/helpdesk"], type="http", auth="user", website=True)
    def portal_helpdesk_dashboard(self, **kw):
        values = self._prepare_portal_layout_values()
        values.update(self._prepare_dashboard_values())
        values["page_name"] = "zc_helpdesk_dashboard"
        return request.render(
            "zencore_helpdesk_portal_enterprise.portal_helpdesk_dashboard",
            values,
        )

    @http.route(
        ["/my/helpdesk/tickets", "/my/helpdesk/tickets/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_helpdesk_tickets(self, page=1, sortby=None, filterby=None, search=None, **kw):
        Ticket = request.env["helpdesk.ticket"].sudo()
        values = self._prepare_portal_layout_values()
        domain = self._ticket_domain()

        searchbar_sortings = {
            "date": {"label": _("Newest"), "order": "create_date desc, id desc"},
            "priority": {"label": _("Priority"), "order": "priority desc, create_date desc"},
            "stage": {"label": _("Stage"), "order": "stage_id, create_date desc"},
        }
        searchbar_filters = {
            "all": {"label": _("All"), "domain": []},
            "open": {"label": _("Open"), "domain": self._closed_domain(False)},
            "closed": {"label": _("Closed"), "domain": self._closed_domain(True)},
            "urgent": {"label": _("Urgent"), "domain": [("priority", "=", "3")]},
        }

        sortby = sortby if sortby in searchbar_sortings else "date"
        filterby = filterby if filterby in searchbar_filters else "all"
        domain += searchbar_filters[filterby]["domain"]

        if search:
            domain += [
                "|", "|",
                ("name", "ilike", search),
                ("team_id.name", "ilike", search),
                ("tag_ids.name", "ilike", search),
            ]

        total = Ticket.search_count(domain)
        pager = portal_pager(
            url="/my/helpdesk/tickets",
            url_args={"sortby": sortby, "filterby": filterby, "search": search},
            total=total,
            page=page,
            step=self._items_per_page,
        )
        tickets = Ticket.search(
            domain,
            order=searchbar_sortings[sortby]["order"],
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        request.session["zc_my_helpdesk_ticket_history"] = tickets.ids[:100]

        values.update({
            "tickets": tickets,
            "page_name": "zc_helpdesk_tickets",
            "pager": pager,
            "default_url": "/my/helpdesk/tickets",
            "searchbar_sortings": searchbar_sortings,
            "searchbar_filters": OrderedDict(searchbar_filters),
            "sortby": sortby,
            "filterby": filterby,
            "search": search or "",
        })
        return request.render(
            "zencore_helpdesk_portal_enterprise.portal_helpdesk_tickets",
            values,
        )

    @http.route(
        ["/my/helpdesk/ticket/new"],
        type="http",
        auth="user",
        website=True,
        methods=["GET", "POST"],
    )
    def portal_helpdesk_ticket_new(self, **post):
        Team = request.env["helpdesk.team"].sudo()
        Tag = request.env["helpdesk.tag"].sudo()
        teams = Team.search(self._portal_team_domain(), order="name")
        tags = Tag.search([], order="name", limit=100)

        values = self._prepare_portal_layout_values()
        values.update({
            "page_name": "zc_helpdesk_ticket_new",
            "teams": teams,
            "tags": tags,
            "form_values": post,
            "error": False,
        })

        if request.httprequest.method == "POST":
            subject = (post.get("subject") or "").strip()
            description = (post.get("description") or "").strip()
            priority = post.get("priority") if post.get("priority") in {"0", "1", "2", "3"} else "0"

            try:
                team_id = int(post.get("team_id") or 0)
            except (TypeError, ValueError):
                team_id = 0
            try:
                tag_id = int(post.get("tag_id") or 0)
            except (TypeError, ValueError):
                tag_id = 0

            team = Team.search(self._portal_team_domain() + [("id", "=", team_id)], limit=1) if team_id else Team
            tag = Tag.browse(tag_id).exists() if tag_id else Tag

            errors = []
            if not subject:
                errors.append(_("Subject is required."))
            if not description:
                errors.append(_("Description is required."))
            if not team:
                errors.append(_("Please select a valid Helpdesk Team."))
            if tag_id and not tag:
                errors.append(_("Please select a valid category/tag."))

            if errors:
                values["error"] = " ".join(errors)
                return request.render(
                    "zencore_helpdesk_portal_enterprise.portal_helpdesk_ticket_new",
                    values,
                )

            partner = request.env.user.partner_id
            ticket_vals = {
                "name": subject,
                "description": self._safe_html(description),
                "partner_id": partner.id,
                "partner_name": partner.name,
                "partner_email": partner.email,
                "team_id": team.id,
                "priority": priority,
            }
            if tag:
                ticket_vals["tag_ids"] = [(6, 0, tag.ids)]

            ticket = request.env["helpdesk.ticket"].sudo().create(ticket_vals)
            ticket.message_subscribe(partner_ids=[partner.id])

            attachments = []
            for upload in request.httprequest.files.getlist("attachments"):
                filename = (upload.filename or "").strip()
                if filename:
                    attachments.append((filename, upload.read()))

            ticket.sudo().message_post(
                author_id=partner.id,
                body=Markup("<p><strong>%s</strong></p><p>%s</p>") % (
                    _("Ticket submitted from customer portal."),
                    self._safe_html(description),
                ),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                attachments=attachments,
            )
            return request.redirect("/my/helpdesk/ticket/%s" % ticket.id)

        return request.render(
            "zencore_helpdesk_portal_enterprise.portal_helpdesk_ticket_new",
            values,
        )

    @http.route(
        ["/my/helpdesk/ticket/<int:ticket_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_helpdesk_ticket_detail(self, ticket_id, **kw):
        ticket = self._get_portal_ticket(ticket_id)
        if not ticket:
            return request.not_found()

        values = self._prepare_portal_layout_values()
        values.update({
            "ticket": ticket,
            "messages": self._visible_messages(ticket),
            "page_name": "zc_helpdesk_ticket",
            "error": request.session.pop("zc_helpdesk_error", False),
        })
        return request.render(
            "zencore_helpdesk_portal_enterprise.portal_helpdesk_ticket_detail",
            values,
        )

    @http.route(
        ["/my/helpdesk/ticket/<int:ticket_id>/reply"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_helpdesk_ticket_reply(self, ticket_id, **post):
        ticket = self._get_portal_ticket(ticket_id)
        if not ticket:
            return request.not_found()

        body = (post.get("message") or "").strip()
        attachments = []
        for upload in request.httprequest.files.getlist("attachments"):
            filename = (upload.filename or "").strip()
            if filename:
                attachments.append((filename, upload.read()))

        if not body and not attachments:
            request.session["zc_helpdesk_error"] = _("Write a message or attach a file before sending.")
            return request.redirect("/my/helpdesk/ticket/%s" % ticket.id)

        partner = request.env.user.partner_id
        ticket.sudo().message_subscribe(partner_ids=[partner.id])
        ticket.sudo().message_post(
            author_id=partner.id,
            body=self._safe_html(body) if body else Markup("<p>%s</p>") % _("Attachment added."),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            attachments=attachments,
        )
        return request.redirect("/my/helpdesk/ticket/%s#communication" % ticket.id)

    @http.route(
        ["/my/helpdesk/ticket/<int:ticket_id>/close"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_helpdesk_ticket_close(self, ticket_id, **post):
        ticket = self._get_portal_ticket(ticket_id)
        if not ticket:
            return request.not_found()
        try:
            ticket.action_zc_portal_close()
        except Exception as exc:
            request.session["zc_helpdesk_error"] = str(exc)
        return request.redirect("/my/helpdesk/ticket/%s" % ticket.id)

    @http.route(
        ["/my/helpdesk/ticket/<int:ticket_id>/reopen"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_helpdesk_ticket_reopen(self, ticket_id, **post):
        ticket = self._get_portal_ticket(ticket_id)
        if not ticket:
            return request.not_found()
        try:
            ticket.action_zc_portal_reopen()
        except Exception as exc:
            request.session["zc_helpdesk_error"] = str(exc)
        return request.redirect("/my/helpdesk/ticket/%s" % ticket.id)

    @http.route(
        ["/my/helpdesk/ticket/<int:ticket_id>/attachment/<int:attachment_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_helpdesk_attachment(self, ticket_id, attachment_id, **kw):
        ticket = self._get_portal_ticket(ticket_id)
        if not ticket:
            return request.not_found()
        attachment = request.env["ir.attachment"].sudo().browse(attachment_id).exists()
        if not attachment or attachment.res_model != "helpdesk.ticket" or attachment.res_id != ticket.id:
            return request.not_found()
        content = base64.b64decode(attachment.datas or b"")
        headers = [
            ("Content-Type", attachment.mimetype or "application/octet-stream"),
            ("Content-Disposition", 'attachment; filename="%s"' % (attachment.name or "attachment")),
        ]
        return request.make_response(content, headers=headers)

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    zc_portal_closed = fields.Boolean(
        string="Portal Closed",
        compute="_compute_zc_portal_closed",
    )

    @api.depends("stage_id")
    def _compute_zc_portal_closed(self):
        for ticket in self:
            stage = ticket.stage_id
            if not stage:
                ticket.zc_portal_closed = False
                continue
            if "fold" in stage._fields:
                ticket.zc_portal_closed = bool(stage.fold)
            elif "is_close" in stage._fields:
                ticket.zc_portal_closed = bool(stage.is_close)
            elif "closed" in stage._fields:
                ticket.zc_portal_closed = bool(stage.closed)
            else:
                ticket.zc_portal_closed = False

    def _zc_portal_stage_domain(self, closed=False):
        self.ensure_one()
        Stage = self.env["helpdesk.stage"].sudo()
        stage_fields = Stage._fields

        domain = []
        if "fold" in stage_fields:
            domain.append(("fold", "=", closed))
        elif "is_close" in stage_fields:
            domain.append(("is_close", "=", closed))
        elif "closed" in stage_fields:
            domain.append(("closed", "=", closed))
        else:
            raise UserError(_("No close/open indicator was found on Helpdesk stages."))

        if self.team_id:
            if "team_ids" in stage_fields:
                domain += ["|", ("team_ids", "=", False), ("team_ids", "in", self.team_id.id)]
            elif "team_id" in stage_fields:
                domain += ["|", ("team_id", "=", False), ("team_id", "=", self.team_id.id)]
        if "active" in stage_fields:
            domain.append(("active", "=", True))
        return domain

    def action_zc_portal_close(self):
        for ticket in self:
            if ticket.zc_portal_closed:
                continue
            stage = self.env["helpdesk.stage"].sudo().search(
                ticket._zc_portal_stage_domain(closed=True),
                order="sequence, id",
                limit=1,
            )
            if not stage:
                raise UserError(_(
                    "No folded/closed Helpdesk stage is configured for team '%s'. "
                    "Create or configure a closed stage first."
                ) % (ticket.team_id.display_name or _("Helpdesk")))
            ticket.sudo().write({"stage_id": stage.id})
        return True

    def action_zc_portal_reopen(self):
        for ticket in self:
            if not ticket.zc_portal_closed:
                continue
            stage = self.env["helpdesk.stage"].sudo().search(
                ticket._zc_portal_stage_domain(closed=False),
                order="sequence, id",
                limit=1,
            )
            if not stage:
                raise UserError(_(
                    "No open Helpdesk stage is configured for team '%s'."
                ) % (ticket.team_id.display_name or _("Helpdesk")))
            ticket.sudo().write({"stage_id": stage.id})
        return True

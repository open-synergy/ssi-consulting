# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ConsultingServiceDetail(models.Model):
    _name = "consulting_service.detail"
    _description = "Consulting Service - Detail"

    service_id = fields.Many2one(
        string="# Service",
        comodel_name="consulting_service",
        required=True,
        ondelete="cascade",
    )
    type_id = fields.Many2one(
        string="Type",
        comodel_name="consulting_service_type",
        required=True,
        ondelete="restrict",
    )
    report_template_id = fields.Many2one(
        string="Report Template",
        comodel_name="consulting_report_template",
        required=True,
        ondelete="restrict",
    )

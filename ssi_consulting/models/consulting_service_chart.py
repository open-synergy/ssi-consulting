# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ConsultingServiceChart(models.Model):
    _name = "consulting_service.chart"
    _description = "Consulting Service - Chart"

    service_id = fields.Many2one(
        string="# Service",
        comodel_name="consulting_service",
        required=True,
        ondelete="cascade",
    )
    chart_id = fields.Many2one(
        string="Chart",
        comodel_name="consulting_chart_template",
        required=True,
        ondelete="restrict",
    )
    superset_id = fields.Integer(
        string="Superset ID",
    )

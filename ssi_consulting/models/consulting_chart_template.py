# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ConsultingChartTemplate(models.Model):
    _name = "consulting_chart_template"
    _description = "Consulting Chart Template"
    _inherit = [
        "mixin.master_data",
    ]

    specification = fields.Text(
        string="Specification",
        required=True,
    )
    materialized_view_id = fields.Many2one(
        string="Materialized View",
        comodel_name="consulting_materialized_view",
        required=True,
    )

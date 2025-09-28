# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ConsultingIssueTemplate(models.Model):
    _name = "consulting_issue_template"
    _description = "Consulting Issue Template"
    _inherit = [
        "mixin.master_data",
    ]

    materialized_view_ids = fields.Many2many(
        string="Materialized Views",
        comodel_name="consulting_materialized_view",
        relation="rel_consulting_issue_template_2_materialized_view",
        column1="issue_template_id",
        column2="materialized_view_id",
    )
    data_structure_ids = fields.Many2many(
        string="Data Structures",
        comodel_name="consulting_data_structure",
        compute="_compute_data_structure_ids",
    )

    @api.depends("materialized_view_ids", "materialized_view_ids.data_structure_ids")
    def _compute_data_structure_ids(self):
        for record in self:
            result = self.env["consulting_data_structure"]
            for mv in record.materialized_view_ids:
                result += mv.data_structure_ids
            record.data_structure_ids = result

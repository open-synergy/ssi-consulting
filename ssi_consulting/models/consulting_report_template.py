# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ConsultingReportTemplate(models.Model):
    _name = "consulting_report_template"
    _description = "Consulting Report Template"
    _inherit = [
        "mixin.master_data",
    ]

    specification = fields.Text(
        string="Specification",
        required=True,
    )
    service_type_id = fields.Many2one(
        string="Service Type",
        comodel_name="consulting_service_type",
        required=True,
    )
    materialized_view_ids = fields.Many2many(
        string="Materialized Views",
        comodel_name="consulting_materialized_view",
        relation="rel_consulting_reporting_template_2_materialized_view",
        column1="report_template_id",
        column2="materialized_view_id",
    )
    data_structure_ids = fields.Many2many(
        string="data Structure",
        comodel_name="consulting_data_structure",
        compute="_compute_data_structure_ids",
        store=False,
    )

    def _compute_data_structure_ids(self):
        for record in self:
            result = []
            if record.materialized_view_ids:
                result = record.mapped("materialized_view_ids.data_structure_ids").ids
            record.data_structure_ids = result

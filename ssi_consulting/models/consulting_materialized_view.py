# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ConsultingMaterializedView(models.Model):
    _name = "consulting_materialized_view"
    _description = "Consulting Materialized View"
    _inherit = ["mixin.master_data"]

    schema = fields.Text(
        string="Schema",
        required=True,
    )
    data_structure_ids = fields.Many2many(
        string="Data Structure",
        comodel_name="consulting_data_structure",
        relation="rel_consulting_materialized_view_2_data_structure",
        column1="materialized_view_id",
        column2="data_structure_id",
    )

    def _create_service_mv(self, issue):
        self.ensure_one()
        data = {
            "service_id": issue.service_id.id,
            "partner_id": issue.service_id.partner_id.id,
            "materialized_view_id": self.id,
            "schema": self.schema,
            "date": issue.date,
        }
        return self.env["consulting_service.materialized_view"].create(data)

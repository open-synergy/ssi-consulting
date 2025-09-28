# consulting_data_structure.py
# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
#
# Catatan: Mekanisme tenant-per-schema. Jika spec tidak menyediakan "schema",
#          gunakan placeholder {{tenant_schema}}.


from odoo import api, fields, models

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class ConsultingDataStructure(models.Model):
    _name = "consulting_data_structure"
    _description = "Consulting Data Structure"
    _inherit = [
        "mixin.master_data",
    ]

    schema = fields.Text(
        string="Schema",
        required=True,
    )
    direct_dependency_ids = fields.Many2many(
        string="Direct Dependencies",
        comodel_name="consulting_data_structure",
        relation="rel_data_structure_direct_dependecies",
        column1="data_structure_id",
        column2="dependency_id",
    )
    all_dependency_ids = fields.Many2many(
        string="All Direct Dependencies",
        comodel_name="consulting_data_structure",
        compute="_compute_all_dependency_ids",
        store=False,
        compute_sudo=True,
    )

    @api.depends("all_dependency_ids")
    def _compute_all_dependency_ids(self):
        for record in self:
            record.all_dependency_ids = record.direct_dependency_ids
            for module in record.direct_dependency_ids:
                record.all_dependency_ids += module.all_dependency_ids

    def _craete_entity(self, materialized_view):
        self.ensure_one()
        data = {
            "service_id": materialized_view.service_id.id,
            "partner_id": materialized_view.partner_id.id,
            "data_structure_id": self.id,
            "title": self.name,
            "schema": self.schema,
            "date": materialized_view.date,
        }
        return self.env["consulting_service.entity"].create(data)

# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ConsultingMaterializedView(models.Model):
    _name = "consulting_materialized_view"
    _description = "Consulting Materialized View"
    _inherit = [
        "mixin.master_data",
    ]

    specification = fields.Text(
        string="Specification",
        required=True,
    )

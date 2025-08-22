# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ConsultingDataStructure(models.Model):
    _name = "consulting_data_structure"
    _description = "Consulting Data Structure"
    _inherit = [
        "mixin.master_data",
    ]

    specification = fields.Text(
        string="Specification",
        required=True,
    )

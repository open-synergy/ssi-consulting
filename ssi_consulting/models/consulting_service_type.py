# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class ConsultingServiceType(models.Model):
    _name = "consulting_service_type"
    _description = "Consulting Service Type"
    _inherit = [
        "mixin.master_data",
    ]

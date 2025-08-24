# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ConsultingServiceMaterializedView(models.Model):
    _name = "consulting_service.materialized_view"
    _description = "Consulting Service - Materialized View"

    service_id = fields.Many2one(
        string="# Service",
        comodel_name="consulting_service",
        required=True,
        ondelete="cascade",
    )
    materialized_view_id = fields.Many2one(
        string="Materialized View",
        comodel_name="consulting_materialized_view",
        required=True,
        ondelete="restrict",
    )
    superset_id = fields.Integer(
        string="Superset ID",
    )

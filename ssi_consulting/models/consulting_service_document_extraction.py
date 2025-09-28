# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


# External libs used to fetch & render CSV as plain text

from odoo import api, fields, models
from odoo.addons.ssi_decorator import ssi_decorator


class ConsultingServiceDocumentExtraction(models.Model):
    _name = "consulting_service.document_extraction"
    _description = "Consulting Service - Document Extraction"
    _inherit = [
        "mixin.transaction_cancel",
        "mixin.transaction_done",
        "mixin.transaction_confirm",
        "mixin.transaction_open",
        "mixin.transaction_partner",
        "mixin.many2one_configurator",
    ]

    # Attributes related to add element on view automatically
    _automatically_insert_view_element = True
    _automatically_insert_done_policy_fields = False
    _automatically_insert_done_button = False

    # Multiple Approval Attribute
    _approval_from_state = "open"
    _approval_to_state = "done"
    _approval_state = "confirm"
    _after_approved_method = "action_done"

    _statusbar_visible_label = "draft,open,confirm"
    _policy_field_order = [
        "confirm_ok",
        "approve_ok",
        "reject_ok",
        "open_ok",
        "restart_approval_ok",
        "cancel_ok",
        "restart_ok",
        "done_ok",
        "manual_number_ok",
    ]
    _header_button_order = [
        "action_open",
        "action_confirm",
        "action_approve_approval",
        "action_reject_approval",
        "%(ssi_transaction_cancel_mixin.base_select_cancel_reason_action)d",
        "action_restart",
    ]

    # Attributes related to add element on search view automatically
    _state_filter_order = [
        "dom_draft",
        "dom_confirm",
        "dom_open",
        "dom_reject",
        "dom_done",
        "dom_cancel",
    ]

    # Sequence attribute
    _create_sequence_state = "open"

    service_id = fields.Many2one(
        string="# Service",
        comodel_name="consulting_service",
        required=True,
        ondelete="cascade",
    )
    title = fields.Char(
        string="Title",
        default="-",
        required=True,
        readonly=True,
        states={
            "draft": [
                ("readonly", False),
            ],
            "open": [
                ("readonly", False),
            ],
        },
    )
    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        states={
            "draft": [
                ("readonly", False),
            ],
            "open": [
                ("readonly", False),
            ],
        },
    )
    document_type_id = fields.Many2one(
        string="Document Type",
        comodel_name="consulting_service.document_type",
        required=False,
        readonly=True,
        states={
            "draft": [
                ("readonly", False),
            ],
            "open": [
                ("readonly", False),
            ],
        },
    )
    binary_data = fields.Binary(
        string="File",
        required=False,
        readonly=True,
        states={
            "draft": [
                ("readonly", False),
            ],
            "open": [
                ("readonly", False),
            ],
        },
    )
    result_json = fields.Text(
        string="Result (JSON)",
        required=False,
        readonly=True,
        states={
            "draft": [
                ("readonly", False),
            ],
            "open": [
                ("readonly", False),
            ],
        },
    )

    @api.model
    def _get_policy_field(self):
        res = super()._get_policy_field()
        policy_field = [
            "confirm_ok",
            "approve_ok",
            "done_ok",
            "open_ok",
            "cancel_ok",
            "reject_ok",
            "restart_ok",
            "restart_approval_ok",
            "manual_number_ok",
        ]
        res += policy_field
        return res

    @ssi_decorator.insert_on_form_view()
    def _insert_form_element(self, view_arch):
        if self._automatically_insert_view_element:
            view_arch = self._reconfigure_statusbar_visible(view_arch)
        return view_arch

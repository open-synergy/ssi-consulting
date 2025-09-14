# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


# External libs used to fetch & render CSV as plain text
import csv
import io

import requests
from odoo import api, fields, models
from odoo.addons.ssi_decorator import ssi_decorator
from tabulate import tabulate


class ConsultingServiceMaterializedView(models.Model):
    _name = "consulting_service.materialized_view"
    _description = "Consulting Service - Materialized View"
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
        states={"draft": [("readonly", False)]},
    )
    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    materialized_view_id = fields.Many2one(
        string="Materialized View",
        comodel_name="consulting_materialized_view",
        required=False,
        ondelete="cascade",
    )
    google_sheet_url = fields.Char(
        string="Google Sheet URL",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    mv_text = fields.Text(
        string="MV on Text",
        compute="_compute_mv_text",
        store=True,
        help="Plain text table (Markdown-like) generated from the CSV pointed by S3 URL.",
    )

    @api.depends("google_sheet_url")
    def _compute_mv_text(self):
        """Fetch CSV from google_sheet_url and render a plain-text table using tabulate.

        Notes:
        - Uses a small fallback encoding detector.
        - Limits to first 50 rows to keep the text compact.
        - Returns an error note in the field if fetch/parse fails.
        """
        limit_rows = 50
        for rec in self:
            text_out = False
            url = (rec.google_sheet_url or "").strip()
            if not url:
                rec.mv_text = text_out
                continue

            try:
                resp = requests.get(url, timeout=60, verify=True)
                resp.raise_for_status()
                content_bytes = resp.content

                # Light-weight encoding detection
                encoding = None
                for enc in ("utf-8-sig", "utf-8", "iso-8859-1"):
                    try:
                        content = content_bytes.decode(enc)
                        encoding = enc
                        break
                    except UnicodeDecodeError:
                        continue
                if encoding is None:
                    content = content_bytes.decode("utf-8", errors="replace")

                # Parse CSV
                reader = csv.reader(io.StringIO(content))
                rows = list(reader)

                if not rows:
                    text_out = "(Empty CSV)"
                else:
                    header = rows[0]
                    data = rows[1 : 1 + limit_rows]
                    table = tabulate(data, headers=header, tablefmt="github")

                    if len(rows) - 1 > limit_rows:
                        total_rows = len(rows) - 1
                        table += (
                            f"\n\n(Note: showing first {limit_rows} rows "
                            f"out of {total_rows} rows)"
                        )

                    text_out = table

            except Exception as e:
                text_out = f"(Failed to fetch/parse CSV: {e})"

            rec.mv_text = text_out

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

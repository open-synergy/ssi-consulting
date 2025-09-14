# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


import logging
from urllib.parse import quote, urlsplit, urlunsplit

# External libs used to fetch & render CSV as plain text
import requests
from odoo import api, fields, models
from odoo.addons.ssi_decorator import ssi_decorator

_logger = logging.getLogger(__name__)


class ConsultingServiceIssue(models.Model):
    _name = "consulting_service.issue"
    _description = "Consulting Service - Issue"
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

    # Analysis Result
    analysis_jason_s3_url = fields.Char(
        string="Analysis (JSON) S3 URL",
    )
    analysis_s3_url = fields.Char(
        string="Analysis S3 URL",
    )
    analysis = fields.Text(
        string="Analysis",
        compute="_compute_analysis",
        store=True,
    )

    materialized_view_ids = fields.Many2many(
        string="Materialized Views",
        comodel_name="consulting_service.materialized_view",
        relation="rel_consulting_issue_2_consulting_mv",
        column1="issue_id",
        column2="mv_id",
    )
    business_process_ids = fields.Many2many(
        string="Business Process",
        comodel_name="consulting_service.business_process",
        relation="rel_consulting_issue_2_consulting_business_process",
        column1="issue_id",
        column2="business_process_id",
    )
    business_process_area_ids = fields.Many2many(
        string="Business Process Area",
        comodel_name="consulting_service.business_process_area",
        relation="rel_consulting_issue_2_consulting_business_process_area",
        column1="issue_id",
        column2="business_process_area_id",
    )

    # AI System Prompting
    system_prompting_schema_parser_id = fields.Many2one(
        string="System Prompting Schema Parser",
        comodel_name="schema_parser",
        required=True,
    )
    system_prompting_specification = fields.Text(
        string="System Prompting Specification",
        required=True,
    )
    system_prompting_specification_valid = fields.Boolean(
        string="System Prompting Specification Valid?",
        compute="_compute_system_prompting",
        store=True,
        compute_sudo=True,
    )
    system_prompting_specification_error_message = fields.Text(
        string="System Prompting Specification Error Message",
        compute="_compute_system_prompting",
        store=True,
        compute_sudo=True,
    )
    system_prompting = fields.Text(
        string="System Prompting Specification",
        compute="_compute_system_prompting",
        store=True,
        compute_sudo=True,
    )
    system_prompting_valid = fields.Boolean(
        string="System Prompting Valid?",
        compute="_compute_system_prompting",
        store=True,
        compute_sudo=True,
    )
    system_prompting_error_message = fields.Text(
        string="System Prompting Error Message",
        compute="_compute_system_prompting",
        store=True,
        compute_sudo=True,
    )
    system_prompting_s3_url = fields.Char(
        string="System Prompting S3 URL",
        readonly=True,
    )

    # AI User Prompting
    user_prompting_schema_parser_id = fields.Many2one(
        string="User Prompting Schema Parser",
        comodel_name="schema_parser",
        required=True,
    )
    user_prompting_specification = fields.Text(
        string="User Prompting Specification",
        required=True,
    )
    user_prompting_specification_valid = fields.Boolean(
        string="User Prompting Specification Valid?",
        compute="_compute_user_prompting",
        store=True,
        compute_sudo=True,
    )
    user_prompting_specification_error_message = fields.Text(
        string="User Prompting Specification Error Message",
        compute="_compute_user_prompting",
        store=True,
        compute_sudo=True,
    )
    user_prompting = fields.Text(
        string="User Prompting Specification",
        compute="_compute_user_prompting",
        store=True,
        compute_sudo=True,
    )
    user_prompting_valid = fields.Boolean(
        string="User Prompting Valid?",
        compute="_compute_user_prompting",
        store=True,
        compute_sudo=True,
    )
    user_prompting_error_message = fields.Text(
        string="User Prompting Error Message",
        compute="_compute_user_prompting",
        store=True,
        compute_sudo=True,
    )
    user_prompting_s3_url = fields.Char(
        string="User Prompting S3 URL",
        readonly=True,
    )

    @api.depends(
        "system_prompting_schema_parser_id",
        "system_prompting_specification",
    )
    def _compute_system_prompting(self):
        for record in self:
            specification_valid = parsing_valid = True
            specification_error_message = parsing_error_message = parsing_result = ""
            if (
                record.system_prompting_schema_parser_id
                and record.system_prompting_specification
            ):
                (
                    _spec_obj,
                    specification_valid,
                    specification_error_message,
                ) = record.system_prompting_schema_parser_id.validate_against_schema(
                    data_text=record.system_prompting_specification
                )
                (
                    parsing_result,
                    parsing_valid,
                    parsing_error_message,
                ) = record.system_prompting_schema_parser_id.parse_specification(
                    specification=record.system_prompting_specification
                )
            record.system_prompting_specification_valid = specification_valid
            record.system_prompting_specification_error_message = (
                specification_error_message
            )
            record.system_prompting_valid = parsing_valid
            record.system_prompting_error_message = parsing_error_message
            record.system_prompting = parsing_result

    @api.depends(
        "user_prompting_schema_parser_id",
        "user_prompting_specification",
    )
    def _compute_user_prompting(self):
        for record in self:
            specification_valid = parsing_valid = True
            specification_error_message = parsing_error_message = parsing_result = ""
            if (
                record.user_prompting_schema_parser_id
                and record.user_prompting_specification
            ):
                (
                    _spec_obj,
                    specification_valid,
                    specification_error_message,
                ) = record.user_prompting_schema_parser_id.validate_against_schema(
                    data_text=record.user_prompting_specification
                )
                (
                    parsing_result,
                    parsing_valid,
                    parsing_error_message,
                ) = record.user_prompting_schema_parser_id.parse_specification(
                    specification=record.user_prompting_specification,
                    additional_dict={
                        "consulting_service": record,
                    },
                )
            record.user_prompting_specification_valid = specification_valid
            record.user_prompting_specification_error_message = (
                specification_error_message
            )
            record.user_prompting_valid = parsing_valid
            record.user_prompting_error_message = parsing_error_message
            record.user_prompting = parsing_result

    @api.depends("analysis_s3_url")
    def _compute_analysis(self):  # noqa: C901
        MAX_BYTES = 5 * 1024 * 1024  # 5 MB

        for rec in self:
            rec.analysis = ""
            raw_url = (rec.analysis_s3_url or "").strip()
            if not raw_url:
                continue

            try:
                parsed = urlsplit(raw_url)
            except Exception as e:
                _logger.warning("analysis_s3_url tidak valid: %s (err=%s)", raw_url, e)
                continue

            if parsed.scheme not in ("http", "https"):
                _logger.warning(
                    "Skema URL tidak didukung untuk analysis_s3_url: %s", raw_url
                )
                continue

            try:
                safe_path = quote(parsed.path or "", safe="/-_.~%")
                safe_fragment = quote(parsed.fragment or "", safe="-_.~%")

                is_presigned = ("X-Amz-Signature=" in parsed.query) or (
                    "X-Amz-Credential=" in parsed.query
                )

                if is_presigned:
                    safe_query = parsed.query
                else:
                    safe_query = (parsed.query or "").replace(" ", "%20")

                url = urlunsplit(
                    (parsed.scheme, parsed.netloc, safe_path, safe_query, safe_fragment)
                )
            except Exception as e:
                _logger.warning("Gagal normalisasi URL: %s (err=%s)", raw_url, e)
                url = raw_url  # fallback: tetap pakai raw_url

            headers = {
                "Accept": "text/markdown, text/plain;q=0.9, */*;q=0.1",
                "User-Agent": "ssi-odoo/14 final-report-fetcher",
            }

            try:
                with requests.get(
                    url, headers=headers, timeout=(5, 30), stream=True
                ) as resp:
                    resp.raise_for_status()

                    encoding = (
                        resp.encoding
                        or getattr(resp, "apparent_encoding", None)
                        or "utf-8"
                    )

                    total = 0
                    chunks = []
                    for chunk in resp.iter_content(
                        chunk_size=65536, decode_unicode=False
                    ):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise ValueError("Ukuran file final report melebihi 5 MB.")
                        chunks.append(chunk)

                raw = b"".join(chunks)

                try:
                    text = raw.decode(encoding, errors="replace")
                except Exception:
                    text = raw.decode("utf-8", errors="replace")

                text = text.replace("\r\n", "\n").replace("\r", "\n")

                if not text.strip():
                    _logger.info("Konten final report kosong dari URL: %s", url)
                    rec.analysis = False
                else:
                    rec.analysis = text

            except requests.exceptions.RequestException as e:
                _logger.error(
                    "Gagal mengambil naration dari S3 URL: %s ; err=%s", url, e
                )
                rec.analysis = False
            except Exception as e:
                _logger.exception(
                    "Kesalahan saat memproses naration dari %s: %s", url, e
                )
                rec.analysis = False

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

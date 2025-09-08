# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from urllib.parse import urlsplit

import requests
from odoo import api, fields, models
from odoo.addons.ssi_decorator import ssi_decorator

_logger = logging.getLogger(__name__)


class ConsultingService(models.Model):
    _name = "consulting_service"
    _description = "Consulting Service"
    _inherit = [
        "mixin.transaction_cancel",
        "mixin.transaction_done",
        "mixin.transaction_open",
        "mixin.transaction_confirm",
        "mixin.transaction_partner",
        "mixin.many2one_configurator",
    ]

    # Multiple Approval Attribute
    _approval_from_state = "draft"
    _approval_to_state = "open"
    _approval_state = "confirm"
    _after_approved_method = "action_open"

    # Attributes related to add element on view automatically
    _automatically_insert_view_element = True
    _automatically_insert_open_policy_fields = False
    _automatically_insert_open_button = False

    _statusbar_visible_label = "draft,confirm,open"
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

    type_id = fields.Many2one(
        string="Type",
        comodel_name="consulting_service_type",
        required=True,
        ondelete="restrict",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    report_template_id = fields.Many2one(
        string="Report Template",
        comodel_name="consulting_report_template",
        required=True,
        ondelete="restrict",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    date_start = fields.Date(
        string="Date Start",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    date_end = fields.Date(
        string="Date End",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    pg_schema = fields.Char(required=True, default="public")
    superset_role = fields.Char(required=True, default="public")

    superset_database_id = fields.Integer(required=True)

    s3_endpoint = fields.Char(
        string="S3 Endpoint",
    )
    s3_bucket = fields.Char(
        string="S3 Bucket",
    )
    s3_key = fields.Char(
        string="S3 Key",
    )
    s3_secret = fields.Char(
        string="S3 Secret",
    )

    detail_materialized_view_ids = fields.One2many(
        string="Materialized View Details",
        comodel_name="consulting_service.materialized_view",
        inverse_name="service_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    detail_chart_ids = fields.One2many(
        string="Chart Details",
        comodel_name="consulting_service.chart",
        inverse_name="service_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    detail_business_process_ids = fields.One2many(
        string="Business Process",
        comodel_name="consulting_service.business_process",
        inverse_name="service_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    data_structure_ids = fields.Many2many(
        string="Data Structure",
        comodel_name="consulting_data_structure",
        relation="rel_consulting_service_2_data_structure",
        column1="service_id",
        column2="data_structure_id",
    )
    materialized_view_ids = fields.Many2many(
        string="Materialized Views",
        comodel_name="consulting_materialized_view",
        relation="rel_consulting_service_2_materialized_view",
        column1="service_id",
        column2="materialized_view_id",
    )
    chart_template_ids = fields.Many2many(
        string="Chart Templates",
        comodel_name="consulting_chart_template",
        relation="rel_consulting_service_2_chart_template",
        column1="service_id",
        column2="chart_template_id",
    )

    table_sql_script = fields.Text(
        string="SQL Script for Table Generation (Phase 1)",
        compute="_compute_table_sql_script",
        store=True,
    )
    fk_sql_script = fields.Text(
        string="SQL Script for FK Generation (Phase 3)",
        compute="_compute_fk_sql_script",
        store=True,
    )
    additional_sql_script = fields.Text(
        string="SQL Script for Additional Generation (Phase 4)",
        compute="_compute_additional_sql_script",
        store=True,
    )
    final_sql_script = fields.Text(
        string="Final SQL Script",
        compute="_compute_final_sql_script",
        store=True,
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

    # Final Report
    final_report_s3_url = fields.Char(
        string="Final Report S3 URL",
        readonly=True,
    )
    final_report = fields.Text(
        string="Final Report",
        compute="_compute_final_report",
        store=True,
        compute_sudo=True,
    )

    @api.depends("final_report_s3_url")
    def _compute_final_report(self):
        """
        Mengambil file Markdown dari final_report_s3_url dan
        mengisikan hasilnya ke field final_report.
        - Mendukung http/https (termasuk presigned S3 URL).
        - Batas ukuran file: 5 MB.
        - Normalisasi newline ke '\n'.
        """
        MAX_BYTES = 5 * 1024 * 1024  # 5 MB

        for rec in self:
            rec.final_report = "Weks"
            url = (rec.final_report_s3_url or "").strip()
            if not url:
                continue

            # Validasi skema URL
            try:
                parsed = urlsplit(url)
            except Exception as e:
                _logger.warning("final_report_s3_url tidak valid: %s (err=%s)", url, e)
                continue

            if parsed.scheme not in ("http", "https"):
                _logger.warning(
                    "Skema URL tidak didukung untuk final_report_s3_url: %s", url
                )
                continue

            headers = {
                "Accept": "text/markdown, text/plain;q=0.9, */*;q=0.1",
                "User-Agent": "ssi-odoo/14 final-report-fetcher",
            }

            try:
                # stream=True agar bisa batasi ukuran
                with requests.get(
                    url, headers=headers, timeout=(5, 30), stream=True
                ) as resp:
                    resp.raise_for_status()

                    # Tentukan encoding seawal mungkin
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

                # Decode konten sebagai teks
                try:
                    text = raw.decode(encoding, errors="replace")
                except Exception:
                    text = raw.decode("utf-8", errors="replace")

                # Normalisasi newline
                text = text.replace("\r\n", "\n").replace("\r", "\n")

                # (Opsional) cek sangat dasar: minimal ada karakter
                if not text.strip():
                    _logger.info("Konten final report kosong dari URL: %s", url)
                    rec.final_report = False
                else:
                    rec.final_report = text

            except requests.exceptions.RequestException as e:
                _logger.error(
                    "Gagal mengambil final_report dari S3 URL: %s ; err=%s", url, e
                )
                rec.final_report = False
            except Exception as e:
                _logger.exception(
                    "Kesalahan saat memproses final_report dari %s: %s", url, e
                )
                rec.final_report = False

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

    @api.onchange(
        "type_id",
    )
    def onchange_report_template_id(self):
        self.report_template_id = False

    @api.onchange(
        "report_template_id",
    )
    def onchange_system_prompting_schema_parser_id(self):
        self.system_prompting_schema_parser_id = False
        if self.report_template_id:
            self.system_prompting_schema_parser_id = (
                self.report_template_id.system_prompting_schema_parser_id
            )

    @api.onchange(
        "report_template_id",
    )
    def onchange_system_prompting_specification(self):
        self.system_prompting_specification = ""
        if self.report_template_id:
            self.system_prompting_specification = (
                self.report_template_id.system_prompting_specification
            )

    @api.onchange(
        "report_template_id",
    )
    def onchange_user_prompting_schema_parser_id(self):
        self.user_prompting_schema_parser_id = False
        if self.report_template_id:
            self.user_prompting_schema_parser_id = (
                self.report_template_id.user_prompting_schema_parser_id
            )

    @api.onchange(
        "report_template_id",
    )
    def onchange_user_prompting_specification(self):
        self.user_prompting_specification = ""
        if self.report_template_id:
            self.user_prompting_specification = (
                self.report_template_id.user_prompting_specification
            )

    def action_open_detail_mv(self):
        for record in self.sudo():
            result = record._open_detail_mv()

        return result

    def action_open_detail_business_process(self):
        for record in self.sudo():
            result = record._open_detail_business_process()

        return result

    def _open_detail_mv(self):
        self.ensure_one()
        waction = self.env.ref(
            "ssi_consulting.consulting_service_materialized_view_action"
        ).read()[0]
        waction.update(
            {
                "view_mode": "tree,form",
                "domain": [("id", "in", self.detail_materialized_view_ids.ids)],
                "context": {},
            }
        )
        return waction

    def _open_detail_business_process(self):
        self.ensure_one()
        waction = self.env.ref(
            "ssi_consulting.consulting_service_business_process_action"
        ).read()[0]
        waction.update(
            {
                "view_mode": "tree,form",
                "domain": [("id", "in", self.detail_business_process_ids.ids)],
                "context": {},
            }
        )
        return waction

    # ===========================
    # Utilities: newline & comment handling
    # ===========================
    @staticmethod
    def _denormalize_newlines(text: str) -> str:
        """
        Ubah literal '\\n' / '\\r\\n' menjadi baris baru asli.
        """
        if not text:
            return ""
        text = text.replace("\\r\\n", "\n")
        text = text.replace("\\n", "\n")
        text = text.replace("\r\n", "\n")
        return text

    @staticmethod
    def _strip_sql_comments(text: str) -> str:
        """
        (Opsional) Hapus komentar SQL satu-baris ('-- ...') dan blok ('/* ... */').
        Dipakai hanya jika Anda ingin final script benar-benar 'bersih'.
        """
        if not text:
            return ""
        import re

        # remove /* ... */ (multiline)
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        # remove -- ... to end-of-line
        text = re.sub(r"(?m)^\s*--.*?$", "", text)
        # rapikan baris kosong berlebih
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _clean_block(text: str, remove_comments: bool = False) -> str:
        """
        Denormalisasi newline + optional stripping comments.
        """
        s = (ConsultingService._denormalize_newlines(text or "")).strip()
        return ConsultingService._strip_sql_comments(s) if remove_comments else s

    # ===========================
    # Compute final SQL
    # ===========================
    @api.depends(
        "pg_schema",
        "table_sql_script",
        "fk_sql_script",
        "additional_sql_script",
        "materialized_view_ids.sql_script",
    )
    def _compute_final_sql_script(self):
        for record in self:
            parts = []
            schema = (record.pg_schema or "").strip()

            # 0) CREATE SCHEMA
            if schema:
                parts.append(f"CREATE SCHEMA IF NOT EXISTS {schema};")

            # 1) Tables
            if record.table_sql_script:
                parts.append(
                    self._clean_block(record.table_sql_script, remove_comments=False)
                )

            # 2) FKs / Index tambahan
            if record.fk_sql_script:
                parts.append(
                    self._clean_block(record.fk_sql_script, remove_comments=False)
                )

            # 3) Additional SQL
            if record.additional_sql_script:
                parts.append(
                    self._clean_block(
                        record.additional_sql_script, remove_comments=False
                    )
                )

            # 4) Materialized Views (AKTIF)
            for mv in record.materialized_view_ids:
                if mv.sql_script:
                    parts.append(
                        self._clean_block(mv.sql_script, remove_comments=False)
                    )

            # 5) Join dengan baris baru asli
            final_sql = "\n\n".join([p for p in parts if p])

            # 6) Ganti placeholder schema
            if schema:
                final_sql = final_sql.replace("{{tenant_schema}}", schema)

            # 7) (Opsional) hapus komentar bila “mengganggu”
            #   -> uncomment baris di bawah jika mau benar-benar tanpa komentar di output
            # final_sql = self._strip_sql_comments(final_sql)

            record.final_sql_script = final_sql

    def _compute_table_sql_script(self):
        for record in self:
            record.table_sql_script = self._build_phase1_sql()

    def _compute_fk_sql_script(self):
        for record in self:
            record.fk_sql_script = self._build_phase3_sql()

    def _compute_additional_sql_script(self):
        for record in self:
            record.additional_sql_script = self._build_phase4_sql()

    def _build_phase1_sql(self):
        self.ensure_one()
        parts = []
        for data_structure in self.data_structure_ids:
            block = self._clean_block(
                data_structure.table_sql_script, remove_comments=False
            )
            if block:
                parts.append(block)
        return "\n\n".join(parts)

    def _build_phase3_sql(self):
        self.ensure_one()
        parts = []
        for data_structure in self.data_structure_ids:
            block = self._clean_block(
                data_structure.fk_sql_script, remove_comments=False
            )
            if block:
                parts.append(block)
        return "\n\n".join(parts)

    def _build_phase4_sql(self):
        self.ensure_one()
        parts = []
        for data_structure in self.data_structure_ids:
            block = self._clean_block(
                data_structure.additional_sql_script, remove_comments=False
            )
            if block:
                parts.append(block)
        return "\n\n".join(parts)

    def action_compute_result(self):
        for record in self.sudo():
            record._compute_data_structure()
            record._compute_materialized_view()
            record._compute_chart_template()
            record._compute_table_sql_script()
            record._compute_fk_sql_script()
            record._compute_additional_sql_script()
            record._compute_final_sql_script()

    def _compute_chart_template(self):
        self.ensure_one()
        result = []
        ChartTemplate = self.env["consulting_chart_template"]
        MV = self.env["consulting_service.materialized_view"]
        Chart = self.env["consulting_service.chart"]
        if self.report_template_id:
            mv_ids = self.mapped("report_template_id.materialized_view_ids").ids
            criteria = [("materialized_view_id", "in", mv_ids)]
            result = ChartTemplate.search(criteria).ids
        self.write({"chart_template_ids": [(6, 0, result)]})

        criteria = [("service_id", "=", self.id)]
        chart_ids = Chart.search(criteria).mapped("chart_id").ids

        to_add_ids = list(set(result) ^ set(chart_ids))
        to_remove_ids = list(set(chart_ids) - set(result))

        for to_add in ChartTemplate.browse(to_add_ids):
            # TODO:
            criteria = [
                ("service_id", "=", self.id),
                ("materialized_view_id", "=", to_add.materialized_view_id.id),
            ]
            mvs = MV.search(criteria)
            if len(mvs) > 0:
                mv = mvs[0]

            Chart.create(
                {
                    "service_id": self.id,
                    "chart_id": to_add.id,
                    "detail_materialized_view_id": mv.id,
                }
            )

        criteria_to_delete = [
            ("service_id", "=", self.id),
            ("chart_id", "in", to_remove_ids),
        ]
        Chart.search(criteria_to_delete).unlink()

    def _compute_data_structure(self):
        self.ensure_one()
        result = []
        if self.report_template_id:
            result = self.mapped("report_template_id.data_structure_ids")
            for data_structure in result:
                result += data_structure.all_dependency_ids
        self.write({"data_structure_ids": [(6, 0, result.ids)]})

    def _compute_materialized_view(self):
        self.ensure_one()
        result = []
        MV = self.env["consulting_service.materialized_view"]
        if self.report_template_id:
            result = self.mapped("report_template_id.materialized_view_ids").ids
        self.write({"materialized_view_ids": [(6, 0, result)]})

        criteria = [("service_id", "=", self.id)]
        mv_ids = MV.search(criteria).mapped("materialized_view_id").ids

        to_add_ids = list(set(result) ^ set(mv_ids))
        to_remove_ids = list(set(mv_ids) - set(result))

        for to_add_id in to_add_ids:
            MV.create(
                {
                    "service_id": self.id,
                    "materialized_view_id": to_add_id,
                }
            )

        criteria_to_delete = [
            ("service_id", "=", self.id),
            ("materialized_view_id", "in", to_remove_ids),
        ]
        MV.search(criteria_to_delete).unlink()

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

# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.addons.ssi_decorator import ssi_decorator


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

    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    pg_schema = fields.Char(required=True, default="public")
    superset_role = fields.Char(required=True, default="public")

    superset_database_id = fields.Integer(required=True)

    detail_ids = fields.One2many(
        string="Details",
        comodel_name="consulting_service.detail",
        inverse_name="service_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
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
        Chart = self.env["consulting_service.chart"]
        if self.detail_ids:
            mv_ids = self.mapped(
                "detail_ids.report_template_id.materialized_view_ids"
            ).ids
            criteria = [("materialized_view_id", "in", mv_ids)]
            result = ChartTemplate.search(criteria).ids
        self.write({"chart_template_ids": [(6, 0, result)]})

        criteria = [("service_id", "=", self.id)]
        chart_ids = Chart.search(criteria).mapped("chart_id").ids

        to_add_ids = list(set(result) ^ set(chart_ids))
        to_remove_ids = list(set(chart_ids) - set(result))

        for to_add_id in to_add_ids:
            Chart.create(
                {
                    "service_id": self.id,
                    "chart_id": to_add_id,
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
        if self.detail_ids:
            result = self.mapped("detail_ids.report_template_id.data_structure_ids").ids
        self.write({"data_structure_ids": [(6, 0, result)]})

    def _compute_materialized_view(self):
        self.ensure_one()
        result = []
        MV = self.env["consulting_service.materialized_view"]
        if self.detail_ids:
            result = self.mapped(
                "detail_ids.report_template_id.materialized_view_ids"
            ).ids
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

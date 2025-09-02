# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ConsultingMaterializedView(models.Model):
    _name = "consulting_materialized_view"
    _description = "Consulting Materialized View"
    _inherit = ["mixin.master_data"]

    # ---- Fields ----------------------------------------------------------------
    specification = fields.Text(
        string="Specification",
        required=True,
        help="YAML or JSON yang mendefinisikan materialized view.",
    )
    service_type_id = fields.Many2one(
        string="Service Type",
        comodel_name="consulting_service_type",
        required=True,
    )
    data_structure_ids = fields.Many2many(
        string="Data Structure",
        comodel_name="consulting_data_structure",
        relation="rel_consulting_materialized_view_2_data_structure",
        column1="materialized_view_id",
        column2="data_structure_id",
    )
    schema_parser_id = fields.Many2one(
        string="Schema Parser",
        comodel_name="schema_parser",
        required=True,
    )
    specification_valid = fields.Boolean(
        string="Specification Valid?",
        compute="_compute_specification",
        store=True,
        compute_sudo=True,
    )
    specification_error_message = fields.Text(
        string="Specification Error Message",
        compute="_compute_specification",
        store=True,
        compute_sudo=True,
    )
    sql_script = fields.Text(
        string="SQL Script",
        compute="_compute_sql_script",
        store=True,
    )
    chart_template_ids = fields.One2many(
        string="Chart Templates",
        comodel_name="consulting_chart_template",
        inverse_name="materialized_view_id",
    )

    # ---- Spec validation (JSON Schema di schema_parser) -------------------------
    @api.depends("schema_parser_id", "specification")
    def _compute_specification(self):
        for record in self:
            specification_valid = True
            error_message = ""
            if record.schema_parser_id and record.specification:
                (
                    _spec_obj,
                    specification_valid,
                    error_message,
                ) = record.schema_parser_id.validate_against_schema(
                    data_text=record.specification
                )
            record.specification_valid = specification_valid
            record.specification_error_message = error_message

    # ---- Util kecil untuk komentar error ---------------------------------------
    @staticmethod
    def _sql_comment_block(lines):
        header = ["/*"]
        body = [f"  {line}" for line in lines]
        footer = ["*/"]
        return "\n".join(header + body + footer)

    # ---- Compute SQL: delegasi penuh ke schema_parser ---------------------------
    @api.depends("schema_parser_id", "specification")
    def _compute_sql_script(self):  # noqa: C901
        for record in self:
            record.sql_script = ""
            if not record.schema_parser_id:
                record.sql_script = self._sql_comment_block(
                    ["Schema Parser belum diisi pada materialized view."]
                )
                continue
            if not record.specification:
                record.sql_script = self._sql_comment_block(
                    ["Specification masih kosong."]
                )
                continue

            # Catatan: seluruh helper sudah pindah ke data parser
            result, ok, err = record.schema_parser_id.parse_specification(
                schema=record.specification
            )
            if not ok:
                record.sql_script = self._sql_comment_block(
                    ["Gagal mengeksekusi parser.", err or ""]
                )
                continue

            if not isinstance(result, dict) or "sql" not in result:
                record.sql_script = self._sql_comment_block(
                    [
                        "Parser tidak mengembalikan format yang diharapkan.",
                        "Harus: result = {'sql': '<SCRIPT>'}",
                    ]
                )
                continue

            record.sql_script = (
                (result.get("sql") or "").replace("\r\n", "\n").replace("\\n", "\n")
            )

# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ConsultingReportTemplate(models.Model):
    _name = "consulting_report_template"
    _description = "Consulting Report Template"
    _inherit = [
        "mixin.master_data",
    ]

    ai_prompt = fields.Text(
        string="AI Prompt",
        required=True,
    )
    service_type_id = fields.Many2one(
        string="Service Type",
        comodel_name="consulting_service_type",
        required=True,
    )
    materialized_view_ids = fields.Many2many(
        string="Materialized Views",
        comodel_name="consulting_materialized_view",
        relation="rel_consulting_reporting_template_2_materialized_view",
        column1="report_template_id",
        column2="materialized_view_id",
    )
    data_structure_ids = fields.Many2many(
        string="data Structure",
        comodel_name="consulting_data_structure",
        compute="_compute_data_structure_ids",
        store=False,
    )
    style_schema_parser_id = fields.Many2one(
        string="Report Style Schema Parser",
        comodel_name="schema_parser",
        required=True,
    )
    style_specification = fields.Text(
        string="Report Style Specification",
        required=True,
    )
    style_valid = fields.Boolean(
        string="Style Specification Valid?",
        compute="_compute_style_specification",
        store=True,
        compute_sudo=True,
    )
    style_error_message = fields.Text(
        string="Style Specification Error Message",
        compute="_compute_style_specification",
        store=True,
        compute_sudo=True,
    )
    style_parsing_result = fields.Text(
        string="Style Parsing Result",
        compute="_compute_style_specification",
        store=True,
        compute_sudo=True,
    )
    style_parsing_valid = fields.Boolean(
        string="Style Parsing Valid?",
        compute="_compute_style_specification",
        store=True,
        compute_sudo=True,
    )
    style_parsing_error_message = fields.Text(
        string="Style Parsing Error Message",
        compute="_compute_style_specification",
        store=True,
        compute_sudo=True,
    )

    @api.depends("style_schema_parser_id", "style_specification")
    def _compute_style_specification(self):
        for record in self:
            specification_valid = style_parsing_valid = True
            error_message = style_parsing_error_message = style_parsing_result = ""
            if record.style_schema_parser_id and record.style_specification:
                (
                    _spec_obj,
                    specification_valid,
                    error_message,
                ) = record.style_schema_parser_id.validate_against_schema(
                    data_text=record.style_specification
                )
                (
                    style_parsing_result,
                    style_parsing_valid,
                    style_parsing_error_message,
                ) = record.style_schema_parser_id.parse_specification(
                    specification=record.style_specification
                )
            record.style_valid = specification_valid
            record.style_error_message = error_message
            record.style_parsing_valid = style_parsing_valid
            record.style_parsing_error_message = style_parsing_error_message
            record.style_parsing_result = style_parsing_result

    def _compute_data_structure_ids(self):
        for record in self:
            result = []
            if record.materialized_view_ids:
                result = record.mapped("materialized_view_ids.data_structure_ids").ids
            record.data_structure_ids = result

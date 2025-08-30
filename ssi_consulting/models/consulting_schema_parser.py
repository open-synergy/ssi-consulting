# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from typing import Any, Dict, List, Optional

import yaml
from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _


class ConsultingSchemaParser(models.Model):
    _name = "consulting_schema_parser"
    _description = "Consulting Schema Parser"
    _inherit = [
        "mixin.master_data",
    ]

    schema = fields.Text(
        string="Schema",
        required=True,
    )
    parser = fields.Text(
        string="Parser",
        required=True,
    )

    def _parse_specification(self, specification):
        self.ensure_one()
        localdict = {
            "yaml_safe_load": yaml.safe_load,
            "yaml_safe_dump": yaml.safe_dump,
            "json_dumps": json.dumps,
            "json_loads": json.loads,
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "Optional": Optional,
            "specification": specification,
        }
        try:
            safe_eval(self.parser, localdict, mode="exec", nocopy=True)
            result = localdict.get("result")
            if result is None:
                raise UserError(_("Parser did not set `result`."))
            if not isinstance(result, dict):
                raise UserError(
                    _("`result` must be a dict, got: %s") % type(result).__name__
                )
            return result
        except Exception as error:
            raise UserError(_("Error executing parser.\n%s") % error)

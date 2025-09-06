# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import csv
import io

# External libs used to fetch & render CSV as plain text
import requests
from odoo import api, fields, models
from tabulate import tabulate


class ConsultingServiceMaterializedView(models.Model):
    _name = "consulting_service.materialized_view"
    _description = "Consulting Service - Materialized View"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
    ]

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
    s3_url = fields.Char(
        string="S3 URL",
    )

    # Plain-text (Markdown-like) preview generated from CSV at s3_url
    mv_text = fields.Text(
        string="MV on Text",
        compute="_compute_mv_text",
        store=True,
        help="Plain text table (Markdown-like) generated from the CSV pointed by S3 URL.",
    )

    @api.depends("s3_url")
    def _compute_mv_text(self):
        """Fetch CSV from s3_url and render a plain-text table using tabulate.

        Notes:
        - Uses a small fallback encoding detector.
        - Limits to first 50 rows to keep the text compact.
        - Returns an error note in the field if fetch/parse fails.
        """
        limit_rows = 50
        for rec in self:
            text_out = False
            url = (rec.s3_url or "").strip()
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

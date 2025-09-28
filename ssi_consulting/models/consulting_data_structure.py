# consulting_data_structure.py
# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
#
# Catatan: Mekanisme tenant-per-schema. Jika spec tidak menyediakan "schema",
#          gunakan placeholder {{tenant_schema}}.


import csv
import io

from odoo import api, fields, models
from tabulate import tabulate

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class ConsultingDataStructure(models.Model):
    _name = "consulting_data_structure"
    _description = "Consulting Data Structure"
    _inherit = [
        "mixin.master_data",
    ]

    schema = fields.Text(
        string="Schema",
        required=True,
    )
    direct_dependency_ids = fields.Many2many(
        string="Direct Dependencies",
        comodel_name="consulting_data_structure",
        relation="rel_data_structure_direct_dependecies",
        column1="data_structure_id",
        column2="dependency_id",
    )
    all_dependency_ids = fields.Many2many(
        string="All Direct Dependencies",
        comodel_name="consulting_data_structure",
        compute="_compute_all_dependency_ids",
        store=False,
        compute_sudo=True,
    )
    example_data = fields.Text(
        string="Example Data",
    )
    example_data_display = fields.Text(
        string="Example Data Display",
        compute="_compute_example_data_display",
        store=True,
        compute_sudo=True,
    )

    @api.depends("example_data")
    def _compute_example_data_display(self):
        """
        Render contoh data CSV menjadi tabel Markdown (format 'github'):

        - Deteksi delimiter otomatis memakai csv.Sniffer (fallback ke ',').
        - Tampilkan header (baris pertama) dan maks. 50 baris data.
        - Jika data kosong, tampilkan '(Empty CSV)'.
        - Jika terjadi error parsing, tampilkan pesan kegagalan yang ramah.
        """
        limit_rows = 50
        for rec in self:
            text_out = ""
            try:
                raw = rec.example_data or ""
                # Normalisasi newline supaya Sniffer bekerja konsisten
                sample = raw.strip()

                if not sample:
                    rec.example_data_display = "(Empty CSV)"
                    continue

                buf = io.StringIO(sample)

                # Coba deteksi dialect; fallback ke default koma
                try:
                    sniff_sample = sample[:4096]
                    dialect = csv.Sniffer().sniff(sniff_sample)
                    buf.seek(0)
                except Exception:
                    dialect = csv.excel  # delimiter default: ','

                reader = csv.reader(buf, dialect)

                # Ambil header
                try:
                    header = next(reader, None)
                except Exception as e:
                    rec.example_data_display = f"(Failed to parse header: {e})"
                    continue

                if not header:
                    rec.example_data_display = "(Empty CSV)"
                    continue

                # Kumpulkan hingga limit_rows baris data tanpa membaca semuanya
                data = []
                total_rows = 0
                for row in reader:
                    total_rows += 1
                    if len(data) < limit_rows:
                        data.append(row)

                table = tabulate(data, headers=header, tablefmt="github")

                if total_rows > limit_rows:
                    table += (
                        f"\n\n(Note: showing first {limit_rows} rows "
                        f"out of {total_rows} rows)"
                    )

                text_out = table or "(Empty CSV)"

            except Exception as e:
                text_out = f"(Failed to fetch/parse CSV: {e})"

            rec.example_data_display = text_out

    @api.depends("all_dependency_ids")
    def _compute_all_dependency_ids(self):
        for record in self:
            record.all_dependency_ids = record.direct_dependency_ids
            for module in record.direct_dependency_ids:
                record.all_dependency_ids += module.all_dependency_ids

    def _craete_entity(self, materialized_view):
        self.ensure_one()
        data = {
            "service_id": materialized_view.service_id.id,
            "partner_id": materialized_view.partner_id.id,
            "data_structure_id": self.id,
            "title": self.name,
            "schema": self.schema,
            "date": materialized_view.date,
        }
        return self.env["consulting_service.entity"].create(data)

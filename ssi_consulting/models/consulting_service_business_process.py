# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from urllib.parse import quote, urlsplit, urlunsplit

# External libs used to fetch & render CSV as plain text
import requests
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ConsultingServiceBusinessProcess(models.Model):
    _name = "consulting_service.business_process"
    _description = "Consulting Service - Business Process"
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
    name = fields.Char(
        string="Business Process Name",
    )
    graphml = fields.Text(
        string="Raw Graphml",
    )
    graphml_s3_url = fields.Char(
        string="Graphml S3 URL",
    )
    naration = fields.Text(
        string="Naration",
        compute="_compute_naration",
        store=True,
    )
    naration_s3_url = fields.Char(
        string="Naration S3 URL",
    )
    analysis_s3_url = fields.Char(
        string="Analysis S3 URL",
    )
    analysis = fields.Text(
        string="Analysis",
        compute="_compute_analysis",
        store=True,
    )

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

    @api.depends("naration_s3_url")
    def _compute_naration(self):  # noqa: C901
        MAX_BYTES = 5 * 1024 * 1024  # 5 MB

        for rec in self:
            rec.naration = ""
            raw_url = (rec.naration_s3_url or "").strip()
            if not raw_url:
                continue

            try:
                parsed = urlsplit(raw_url)
            except Exception as e:
                _logger.warning("naration_s3_url tidak valid: %s (err=%s)", raw_url, e)
                continue

            if parsed.scheme not in ("http", "https"):
                _logger.warning(
                    "Skema URL tidak didukung untuk naration_s3_url: %s", raw_url
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
                    rec.naration = False
                else:
                    rec.naration = text

            except requests.exceptions.RequestException as e:
                _logger.error(
                    "Gagal mengambil naration dari S3 URL: %s ; err=%s", url, e
                )
                rec.naration = False
            except Exception as e:
                _logger.exception(
                    "Kesalahan saat memproses naration dari %s: %s", url, e
                )
                rec.naration = False

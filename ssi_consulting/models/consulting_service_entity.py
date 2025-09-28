# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).  # noqa: E501

# External libs used to fetch & render CSV as plain text
import io
import json

import pandas as pd
from odoo import _, api, fields, models
from odoo.addons.ssi_decorator import ssi_decorator
from odoo.exceptions import ValidationError


class ConsultingServiceEntity(models.Model):
    _name = "consulting_service.entity"
    _description = "Consulting Service - Entity"
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
        "%(ssi_transaction_cancel_mixin.base_select_cancel_reason_action)d",  # noqa: E501
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
    data_structure_id = fields.Many2one(
        string="Data Structure",
        comodel_name="consulting_data_structure",
        required=False,
        ondelete="restrict",
    )
    title = fields.Char(
        string="Title",
        default="-",
        required=True,
        readonly=True,
        states={
            "draft": [("readonly", False)],
            "open": [("readonly", False)],
        },
    )
    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        states={
            "draft": [("readonly", False)],
            "open": [("readonly", False)],
        },
    )
    raw = fields.Text(
        string="Raw Data",
        required=False,
        readonly=True,
        states={
            "draft": [("readonly", False)],
            "open": [("readonly", False)],
        },
    )
    schema = fields.Text(
        string="Raw Data",
        required=False,
        readonly=True,
        states={
            "draft": [("readonly", False)],
            "open": [("readonly", False)],
        },
    )

    @api.onchange("data_structure_id")
    def _onchange_schema(self):
        self.schema = ""
        if self.data_structure_id:
            self.schema = self.data_structure_id.schema or ""

    @api.onchange("data_structure_id")
    def onchange_title(self):
        if self.data_structure_id and self.data_structure_id.name:
            self.title = self.data_structure_id.name

    # ------------------------
    # Helper methods
    # ------------------------
    @staticmethod
    def _ensure_nonempty(name: str, value: str) -> None:
        if not value or not str(value).strip():
            raise ValidationError(
                _(f"[consulting_service.entity.extract_df] Field `{name}` kosong.")
            )

    @staticmethod
    def _parse_schema(schema_text: str) -> dict:
        try:
            return json.loads(schema_text)
        except Exception as e:  # noqa: BLE001
            raise ValidationError(
                _(
                    "[consulting_service.entity.extract_df] `schema` bukan JSON "
                    f"valid: {e}"
                )
            )

    @staticmethod
    def _columns_from_schema(sc: dict) -> list:
        # JSON Schema draft-07: ambil dari properties
        if isinstance(sc, dict) and isinstance(sc.get("properties"), dict):
            return list(sc["properties"].keys())

        # Loader-style: columns: [{name: ...}, ...]
        if isinstance(sc.get("columns"), list):
            cols = [
                c.get("name")
                for c in sc["columns"]
                if isinstance(c, dict) and c.get("name")
            ]
            if cols:
                return cols

        raise ValidationError(
            _(
                "[consulting_service.entity.extract_df] Tidak dapat menentukan "
                "kolom dari schema. Pastikan JSON Schema memiliki 'properties' "
                "atau gunakan format loader dengan 'columns'."
            )
        )

    @staticmethod
    def _detect_format(explicit_fmt: str, raw_text: str) -> str:
        """Kembalikan 'csv' | 'json' | 'jsonl'."""
        fmt = (explicit_fmt or "").strip().lower()
        if fmt in {"jsonl", "ndjson"}:
            return "jsonl"
        if fmt == "json":
            return "json"
        if fmt:
            return "csv"  # format lain dianggap csv

        # Auto-detect
        stripped = raw_text.lstrip()
        if stripped.startswith("["):
            return "json"
        if stripped.startswith("{"):
            return "jsonl"
        return "csv"

    @staticmethod
    def _read_json_lines(raw_text: str) -> pd.DataFrame:
        rows = []
        for line in raw_text.splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return pd.DataFrame(rows)

    @staticmethod
    def _read_json_array(raw_text: str) -> pd.DataFrame:
        data = json.loads(raw_text)
        if not isinstance(data, list):
            raise ValidationError(
                _(
                    "[consulting_service.entity.extract_df] 'json' harus berupa "
                    "array of objects."
                )
            )
        return pd.DataFrame(data)

    @staticmethod
    def _read_csv(raw_text: str) -> pd.DataFrame:
        return pd.read_csv(io.StringIO(raw_text))

    @staticmethod
    def _select_and_fill_columns(df: pd.DataFrame, cols: list) -> pd.DataFrame:
        for c in cols:
            if c not in df.columns:
                df[c] = pd.NA
        return df[cols]

    # ------------------------
    # API utama
    # ------------------------
    def extract_df(self):
        """
        Parse self.raw -> pandas.DataFrame berdasarkan self.schema.

        - Mendukung CSV (default), JSON Lines (jsonl/ndjson), dan JSON array.
        - Jika schema adalah JSON Schema (draft-07), kolom diambil dari
          'properties'.
        - Raise ValidationError dengan pesan spesifik bila gagal.
        """
        self.ensure_one()

        # Validasi awal
        self._ensure_nonempty("raw", self.raw)
        self._ensure_nonempty("schema", self.schema)

        # Parse schema & kolom
        sc = self._parse_schema(self.schema)
        cols = self._columns_from_schema(sc)

        raw_text = self.raw if isinstance(self.raw, str) else str(self.raw)
        fmt = self._detect_format(sc.get("format"), raw_text)

        # Load DataFrame sesuai format
        try:
            if fmt == "jsonl":
                df = self._read_json_lines(raw_text)
            elif fmt == "json":
                df = self._read_json_array(raw_text)
            else:  # csv
                df = self._read_csv(raw_text)
        except ValidationError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ValidationError(
                _(
                    "[consulting_service.entity.extract_df] Gagal memuat data raw "
                    f"(format='{fmt}'): {e}"
                )
            )

        if df is None or df.empty:
            raise ValidationError(
                _(
                    "[consulting_service.entity.extract_df] DataFrame hasil "
                    "parsing kosong."
                )
            )

        # Susun kolom sesuai schema (yang kurang diisi NaN)
        return self._select_and_fill_columns(df, cols)

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

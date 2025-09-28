# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# External libs used to fetch & render CSV as plain text
import csv
import io
import json

import pandas as pd
import requests
from odoo import _, api, fields, models
from odoo.addons.ssi_decorator import ssi_decorator
from odoo.exceptions import ValidationError
from tabulate import tabulate


class ConsultingServiceMaterializedView(models.Model):
    _name = "consulting_service.materialized_view"
    _description = "Consulting Service - Materialized View"
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
        ("%(ssi_transaction_cancel_mixin." "base_select_cancel_reason_action)d"),
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
    materialized_view_id = fields.Many2one(
        string="Materialized View",
        comodel_name="consulting_materialized_view",
        required=False,
        ondelete="cascade",
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
    s3_prefix = fields.Char(
        string="S3 Prefix",
        readonly=True,
        states={
            "draft": [("readonly", False)],
            "open": [("readonly", False)],
        },
    )
    google_sheet_url = fields.Char(
        string="S3 URL",
        readonly=True,
        states={
            "draft": [("readonly", False)],
            "open": [("readonly", False)],
        },
    )
    mv_text = fields.Text(
        string="MV on Text",
        compute="_compute_mv_text",
        store=True,
    )
    mv_json = fields.Text(
        string="MV on Text",
        compute="_compute_mv_json",
        store=True,
    )
    entity_ids = fields.Many2many(
        string="Entities",
        comodel_name="consulting_service.entity",
        relation="consulting_service_materialized_view_entity_rel",
        column1="materialized_view_id",
        column2="entity_id",
        required=False,
    )

    @api.onchange(
        "materialized_view_id",
    )
    def onchange_schema(self):
        if self.materialized_view_id and self.materialized_view_id.schema:
            self.schema = self.materialized_view_id.schema or ""

    @api.onchange(
        "materialized_view_id",
    )
    def onchange_title(self):
        if self.materialized_view_id and self.materialized_view_id.name:
            self.title = self.materialized_view_id.name

    @api.depends("google_sheet_url")
    def _compute_mv_json(self):
        """
        Fetch CSV from google_sheet_url and render as minified JSON.

        - Deteksi encoding ringan (utf-8-sig, utf-8, iso-8859-1,
          fallback utf-8 dengan replace).
        - Hanya ambil 50 baris pertama (selain header).
        - Jika gagal fetch/parse, isi field dengan JSON error
          {"error":"..."}.
        - JSON di-minify (tanpa spasi/indent).
        """
        limit_rows = 50
        for rec in self:
            out_json = False
            url = (rec.google_sheet_url or "").strip()
            if not url:
                rec.mv_json = out_json
                continue

            try:
                resp = requests.get(url, timeout=60, verify=True)
                resp.raise_for_status()
                content_bytes = resp.content

                # Deteksi encoding sederhana
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
                    out_obj = []
                else:
                    header = rows[0]
                    data = rows[1 : 1 + limit_rows]

                    # Normalisasi header kosong
                    if not header or all((h or "").strip() == "" for h in header):
                        header = [
                            f"col_{i + 1}"
                            for i in range(max((len(r) for r in data), default=0))
                        ]

                    # Pad/truncate baris agar sesuai header
                    normalized = []
                    for r in data:
                        row = list(r[: len(header)]) + [""] * max(
                            0, len(header) - len(r)
                        )
                        normalized.append(
                            {header[i]: row[i] for i in range(len(header))}
                        )

                    out_obj = normalized

                # JSON terminify
                out_json = json.dumps(
                    out_obj,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )

            except Exception as e:
                out_json = json.dumps(
                    {"error": f"Failed to fetch/parse CSV: {e}"},
                    separators=(",", ":"),
                    ensure_ascii=False,
                )

            rec.mv_json = out_json

    @api.depends("google_sheet_url")
    def _compute_mv_text(self):
        """Fetch CSV from google_sheet_url and render a plain-text table
        using tabulate.

        Notes:
        - Uses a small fallback encoding detector.
        - Limits to first 50 rows to keep the text compact.
        - Returns an error note in the field if fetch/parse fails.
        """
        limit_rows = 50
        for rec in self:
            text_out = False
            url = (rec.google_sheet_url or "").strip()
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

    def action_create_entities(self):
        for record in self.sudo():
            result = record._create_entities()
        return result

    def _create_entities(self):
        self.ensure_one()
        self.write({"entity_ids": [(5, 0, 0)]})  # clear existing entities
        entity_ids = []
        if self.materialized_view_id:
            all_data_structures = self.materialized_view_id.data_structure_ids
            criteria = [
                ("service_id", "=", self.service_id.id),
                ("data_structure_id", "in", all_data_structures.ids),
            ]
            existing_entities = self.env["consulting_service.entity"].search(criteria)
            if len(existing_entities) > 0:
                entity_ids += existing_entities.ids

            missing_entities = all_data_structures - existing_entities.mapped(
                "data_structure_id"
            )
            for missing_entity in missing_entities:
                entity = missing_entity._craete_entity(self)
                entity_ids.append(entity.id)

            action = {
                "type": "ir.actions.act_window",
                "name": "Consulting Service Entities",
                "res_model": "consulting_service.entity",
                "domain": [("id", "in", entity_ids)],
                "view_mode": "tree,form",
            }

            return action
        return True

    # =========================
    # Orkestrator (entry point)
    # =========================
    def action_build_pandas(self):
        """
        Bangun MV dari self.schema (JSON spec) → tulis CSV ke `raw`.
        Setiap tahap akan raise ValidationError dengan pesan yang
        spesifik jika gagal.
        """
        for rec in self:
            try:
                if not rec.schema:
                    raise ValidationError(
                        _("[action_build_pandas] Field `schema` kosong.")
                    )

                spec = rec._mv_parse_spec(rec.schema)

                dfs = rec._mv_resolve_sources_to_dfs(rec, spec)
                if not dfs:
                    raise ValidationError(
                        _(
                            "[action_build_pandas] Tidak ada DataFrame sumber yang "
                            "berhasil dimuat."
                        )
                    )

                mv_df = rec._mv_build_base_df(spec, dfs)
                if mv_df.empty:
                    raise ValidationError(
                        _(
                            "[_mv_build_base_df] DataFrame sumber utama kosong. "
                            "Cek entity/title & data mentah."
                        )
                    )

                mv_df = rec._mv_apply_joins(spec, dfs, mv_df)
                if mv_df.empty:
                    raise ValidationError(
                        _(
                            "[_mv_apply_joins] Hasil JOIN kosong. Cek kunci join "
                            "& kesesuaian nilai antar entity."
                        )
                    )

                mv_df = rec._mv_apply_filters(spec, mv_df)
                if mv_df.empty and spec.get("filters"):
                    raise ValidationError(
                        _(
                            "[_mv_apply_filters] Semua baris terfilter habis. "
                            "Cek ekspresi filters di schema."
                        )
                    )

                out_df = rec._mv_aggregate_and_select(spec, mv_df)
                if out_df.empty:
                    raise ValidationError(
                        _(
                            "[_mv_aggregate_and_select] Hasil agregasi kosong. "
                            "Cek `select`/`group_by` & data."
                        )
                    )

                # Urut kolom + tulis CSV
                out_df = rec._mv_order_columns(spec, out_df)
                rec.raw = rec._mv_dataframe_to_csv(out_df)

            except ValidationError:
                # re-raise apa adanya untuk tampil ke user
                raise
            except Exception as e:
                # bungkus error tak terduga agar tetap jelas sumbernya
                raise ValidationError(
                    _("[action_build_pandas] Error tak terduga: {err}").format(err=e)
                )
        return True

    # =========================
    # Step 0: Parsing & validasi ringan
    # =========================
    def _mv_parse_spec(self, schema_text: str) -> dict:
        try:
            spec = json.loads(schema_text)
        except Exception as e:
            raise ValidationError(
                _("[_mv_parse_spec] Schema MV bukan JSON valid: {err}").format(err=e)
            )

        # Validasi minimal & pesan yang actionable
        if not isinstance(spec.get("sources"), list) or not spec["sources"]:
            raise ValidationError(
                _("[_mv_parse_spec] `sources` wajib berupa array minimal 1 item.")
            )
        if not isinstance(spec.get("select"), list) or not spec["select"]:
            raise ValidationError(
                _("[_mv_parse_spec] `select` wajib berupa array minimal 1 item.")
            )

        for i, s in enumerate(spec["sources"], start=1):
            if not s.get("alias"):
                raise ValidationError(
                    _("[_mv_parse_spec] sources[{i}].alias wajib diisi.").format(i=i)
                )
            if not s.get("entity_name"):
                raise ValidationError(
                    _(
                        "[_mv_parse_spec] sources[{i}].entity_name "
                        "(pakai title entity) wajib diisi."
                    ).format(i=i)
                )

        return spec

    # =========================
    # Step 1: Resolve sources -> DataFrame
    # =========================
    def _mv_resolve_sources_to_dfs(self, rec, spec) -> dict:
        dfs = {}
        title_map = {e.title: e for e in rec.entity_ids}
        for src in spec.get("sources", []):
            alias = src["alias"]
            ename = src["entity_name"]

            ent = title_map.get(ename) or rec.env["consulting_service.entity"].search(
                [("title", "=", ename)],
                limit=1,
            )
            if not ent:
                raise ValidationError(
                    _(
                        "[_mv_resolve_sources_to_dfs] Entity dengan title='{title}' "
                        "tidak ditemukan (alias '{alias}')."
                    ).format(title=ename, alias=alias)
                )

            if not hasattr(ent, "extract_df"):
                raise ValidationError(
                    _(
                        "[_mv_resolve_sources_to_dfs] Entity '{title}' tidak "
                        "memiliki method extract_df()."
                    ).format(title=ename)
                )

            df = ent.extract_df()
            if df is None:
                raise ValidationError(
                    _(
                        "[_mv_resolve_sources_to_dfs] extract_df() entity '{title}' "
                        "mengembalikan None."
                    ).format(title=ename)
                )
            if df.empty:
                raise ValidationError(
                    _(
                        "[_mv_resolve_sources_to_dfs] Data entity '{title}' kosong. "
                        "Pastikan field `raw` berisi data yang sesuai `schema` entity."
                    ).format(title=ename)
                )

            df = df.rename(columns={c: f"{alias}__{c}" for c in df.columns})
            dfs[alias] = df

            # Validasi key join jika didefinisikan
            key = src.get("key")
            if key and f"{alias}__{key}" not in df.columns:
                raise ValidationError(
                    _(
                        "[_mv_resolve_sources_to_dfs] Kolom key '{key}' tidak "
                        "ditemukan di entity '{title}' setelah rename "
                        "(diharapkan: '{alias_key}'). Cek schema entity & penamaan kolom."
                    ).format(key=key, title=ename, alias_key=f"{alias}__{key}")
                )
        return dfs

    # =========================
    # Step 2: Base DF
    # =========================
    def _mv_build_base_df(self, spec, dfs: dict) -> pd.DataFrame:
        if not dfs:
            raise ValidationError(
                _("[_mv_build_base_df] Tidak ada sumber yang ter-resolve.")
            )
        main_alias = spec["sources"][0]["alias"]
        base = dfs.get(main_alias)
        if base is None or base.empty:
            raise ValidationError(
                _(
                    "[_mv_build_base_df] DataFrame utama (alias '{alias}') "
                    "kosong/tidak ditemukan."
                ).format(alias=main_alias)
            )
        return base.copy()

    # =========================
    # Step 3: Apply JOINs
    # =========================
    def _mv_apply_joins(self, spec, dfs: dict, mv_df: pd.DataFrame) -> pd.DataFrame:
        if mv_df.empty:
            return mv_df
        for j in spec.get("join", []):
            if "left" not in j or "right" not in j:
                raise ValidationError(
                    _(
                        "[_mv_apply_joins] Definisi join harus memiliki 'left' dan 'right'."
                    )
                )

            try:
                l_alias, l_col = j["left"].split(".", 1)
                r_alias, r_col = j["right"].split(".", 1)
            except ValueError:
                raise ValidationError(
                    _(
                        "[_mv_apply_joins] Format join tidak valid: left='{left}', "
                        "right='{right}'. Gunakan 'alias.field'."
                    ).format(left=j.get("left"), right=j.get("right"))
                )

            lkey = f"{l_alias}__{l_col}"
            rkey = f"{r_alias}__{r_col}"

            if lkey not in mv_df.columns:
                raise ValidationError(
                    _(
                        "[_mv_apply_joins] Kolom join kiri '{col}' tidak "
                        "ditemukan di DF berjalan."
                    ).format(col=lkey)
                )
            right_df = dfs.get(r_alias)
            if right_df is None or right_df.empty:
                raise ValidationError(
                    _(
                        "[_mv_apply_joins] DataFrame kanan untuk alias '{alias}' "
                        "kosong/tidak ada."
                    ).format(alias=r_alias)
                )
            if rkey not in right_df.columns:
                raise ValidationError(
                    _(
                        "[_mv_apply_joins] Kolom join kanan '{col}' tidak ditemukan "
                        "di DF alias '{alias}'."
                    ).format(col=rkey, alias=r_alias)
                )

            how = "left" if (j.get("type") or "inner").lower() == "left" else "inner"
            mv_df = mv_df.merge(
                right_df,
                how=how,
                left_on=lkey,
                right_on=rkey,
            )

        return mv_df

    # =========================
    # Step 4: Apply FILTERs
    # =========================
    def _mv_apply_filters(self, spec, mv_df: pd.DataFrame) -> pd.DataFrame:
        if mv_df.empty:
            return mv_df
        for fexpr in spec.get("filters", []):
            if not isinstance(fexpr, str) or not fexpr.strip():
                continue
            safe = fexpr.replace(".", "__")
            try:
                mv_df = mv_df.query(safe, engine="python")
            except Exception as e:
                raise ValidationError(
                    _(
                        "[_mv_apply_filters] Ekspresi filter tidak valid: '{expr}' → {err}"
                    ).format(expr=fexpr, err=e)
                )
        return mv_df

    # =========================
    # Step 5: Aggregate & Select
    # =========================
    def _mv_aggregate_and_select(self, spec, mv_df: pd.DataFrame) -> pd.DataFrame:
        if mv_df.empty:
            raise ValidationError(
                _("[_mv_aggregate_and_select] DataFrame masuk kosong.")
            )

        group_cols = [g.replace(".", "__") for g in spec.get("group_by", [])]
        agg_map, rename_map, passthrough = self._mv_build_agg_and_passthrough(spec)

        # Validasi kolom select/passthrough ada di DF
        for c in passthrough:
            if c not in mv_df.columns:
                raise ValidationError(
                    _(
                        "[_mv_aggregate_and_select] Kolom non-agregat '{col}' "
                        "tidak ada di data. Cek 'select' dan nama kolom entity."
                    ).format(col=c)
                )

        # Validasi group_by harus mencakup semua kolom non-agregat
        missing_in_group = [c for c in passthrough if c not in group_cols]
        if group_cols and missing_in_group:
            raise ValidationError(
                _(
                    "[_mv_aggregate_and_select] Kolom non-agregat berikut harus masuk "
                    "ke 'group_by': {cols}"
                ).format(cols=", ".join(missing_in_group))
            )

        try:
            if group_cols:
                gb = mv_df.groupby(group_cols, dropna=False)
                out_df = (
                    gb.agg(agg_map).reset_index()
                    if agg_map
                    else gb.first().reset_index()
                )
                extra_passthrough = [c for c in passthrough if c not in group_cols]
                if extra_passthrough:
                    first_df = gb[extra_passthrough].first().reset_index()
                    out_df = out_df.merge(first_df, on=group_cols, how="inner")
            else:
                # tanpa group_by
                rows = {}
                for col, fn in agg_map.items():
                    if fn is pd.Series.nunique:
                        if col not in mv_df.columns:
                            raise ValidationError(
                                _(
                                    "[_mv_aggregate_and_select] Kolom untuk nunique "
                                    "'{col}' tidak ditemukan."
                                ).format(col=col)
                            )
                        rows[col] = mv_df[col].nunique()
                    else:
                        if col not in mv_df.columns:
                            raise ValidationError(
                                _(
                                    "[_mv_aggregate_and_select] Kolom untuk agregat "
                                    "'{col}' tidak ditemukan."
                                ).format(col=col)
                            )
                        rows[col] = getattr(mv_df[col], fn)()
                for c in passthrough:
                    rows[c] = (
                        mv_df[c].iloc[0]
                        if c in mv_df.columns and not mv_df.empty
                        else None
                    )
                out_df = pd.DataFrame([rows])
        except Exception as e:
            raise ValidationError(
                _("[_mv_aggregate_and_select] Gagal melakukan agregasi: {err}").format(
                    err=e
                )
            )

        # Rename kolom ke alias output
        out_df = out_df.rename(columns=rename_map)
        return out_df

    def _mv_build_agg_and_passthrough(self, spec):
        """
        Susun:
        - agg_map: mapping kolom (alias__) -> fungsi agregat
        - rename_map: mapping kolom (alias__/khusus) -> alias output
        - passthrough: list kolom non-agregat yang harus ikut tampil
        """
        agg_map, rename_map, passthrough = {}, {}, []
        for col in spec.get("select", []):
            expr, out = col["expr"], col["as"]
            if not isinstance(expr, str):
                continue
            # Agregat yang didukung:
            if expr.startswith(
                ("sum(", "avg(", "min(", "max(", "count(", "count_distinct(")
            ) and expr.endswith(")"):
                inner = expr.split("(", 1)[1][:-1]  # isi dalam tanda kurung
                if expr.startswith("sum("):
                    k = inner.replace(".", "__")
                    agg_map[k] = "sum"
                    rename_map[k] = out
                elif expr.startswith("avg("):
                    k = inner.replace(".", "__")
                    agg_map[k] = "mean"
                    rename_map[k] = out
                elif expr.startswith("min("):
                    k = inner.replace(".", "__")
                    agg_map[k] = "min"
                    rename_map[k] = out
                elif expr.startswith("max("):
                    k = inner.replace(".", "__")
                    agg_map[k] = "max"
                    rename_map[k] = out
                elif expr.startswith("count_distinct("):
                    k = inner.replace(".", "__")
                    agg_map[k] = pd.Series.nunique
                    rename_map[k] = out
                elif expr.startswith("count("):
                    # count(col) — (catatan: count(*) tak dipetakan di sini)
                    k = inner.replace(".", "__")
                    agg_map[k] = "count"
                    rename_map[k] = out
            else:
                # Kolom biasa → passthrough
                k = expr.replace(".", "__")
                passthrough.append(k)
                rename_map[k] = out
        return agg_map, rename_map, passthrough

    # =========================
    # Step 6: Urutan kolom sesuai SELECT
    # =========================
    def _mv_order_columns(self, spec, out_df: pd.DataFrame) -> pd.DataFrame:
        if out_df.empty:
            return out_df
        sel_order = [c["as"] for c in spec.get("select", []) if "as" in c]
        present = [c for c in sel_order if c in out_df.columns]
        others = [c for c in out_df.columns if c not in present]
        return out_df[present + others]

    def _mv_dataframe_to_csv(self, df: pd.DataFrame) -> str:
        """
        Konversi DataFrame ke CSV string dengan setiap nilai
        (termasuk header) dibungkus tanda kutip ganda "".
        """
        if df is None or df.empty:
            return ""

        # Ganti NaN/None dengan string kosong
        df = df.fillna("")

        buf = io.StringIO()
        df.to_csv(
            buf,
            index=False,
            # gunakan csv.QUOTE_ALL dari modul csv, bukan pandas.io.common
            quoting=csv.QUOTE_ALL,
            quotechar='"',
        )
        return buf.getvalue()

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

# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo import api, fields, models


class ConsultingMaterializedView(models.Model):
    _name = "consulting_materialized_view"
    _description = "Consulting Materialized View"
    _inherit = [
        "mixin.master_data",
    ]

    specification = fields.Text(
        string="Specification",
        required=True,
        help="YAML atau JSON yang mendefinisikan materialized view.",
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

    # ======================
    # Helpers (parse/valid)
    # ======================
    def _sql_comment_block(self, lines):
        header = ["/*"]
        body = [f"  {line}" for line in lines]
        footer = ["*/"]
        return "\n".join(header + body + footer)

    def _load_spec(self, text):
        """
        Parse specification as YAML first (if PyYAML available), then JSON.
        Return: (spec_dict or None, errors[list])
        """
        errors = []
        spec = None

        # Try YAML
        try:
            import yaml  # type: ignore

            try:
                spec = yaml.safe_load(text) if text else None
            except Exception as e:
                errors.append(f"YAML parse error: {e}")
        except Exception:
            pass

        # Try JSON
        if spec is None:
            try:
                spec = json.loads(text) if text else None
            except Exception as e:
                errors.append(f"JSON parse error: {e}")

        if not spec:
            errors.append("Specification is empty or cannot be parsed as YAML/JSON.")

        return spec, errors

    def _expect(self, cond, msg, errors):
        if not cond:
            errors.append(msg)

    def _get(self, data, path, default=None):
        cur = data
        for key in path.split("."):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                return default
        return cur

    def _validate_spec_generic(self, spec):
        """
        Validasi generik spesifikasi MV.
        """
        errors = []

        # name
        self._expect(bool(spec.get("name")), "Field 'name' wajib diisi.", errors)

        # sources
        sources = spec.get("sources")
        self._expect(
            isinstance(sources, dict) and len(sources) > 0,
            "Field 'sources' wajib dict dan tidak kosong.",
            errors,
        )
        if isinstance(sources, dict):
            for src_key, src_def in sources.items():
                self._expect(
                    isinstance(src_def, dict)
                    and "table" in src_def
                    and src_def["table"],
                    f"sources.{src_key}.table wajib ada.",
                    errors,
                )
                # FK type check: jika ada, wajib bigint
                fks = src_def.get("fk") or []
                if fks:
                    if not isinstance(fks, list):
                        errors.append(f"sources.{src_key}.fk harus berupa list.")
                    else:
                        for i, fk in enumerate(fks):
                            if isinstance(fk, dict) and fk.get("type"):
                                self._expect(
                                    fk.get("type") == "bigint",
                                    f"sources.{src_key}.fk[{i}].type harus 'bigint'.",
                                    errors,
                                )

        # columns
        cols = spec.get("columns")
        self._expect(
            isinstance(cols, list) and len(cols) > 0,
            "Field 'columns' wajib list dan tidak kosong.",
            errors,
        )

        col_names = []
        if isinstance(cols, list):
            for i, c in enumerate(cols):
                self._expect(isinstance(c, dict), f"columns[{i}] harus dict.", errors)
                name = (c or {}).get("name")
                self._expect(bool(name), f"columns[{i}].name wajib ada.", errors)
                if name:
                    col_names.append(name)
                # Either transform atau (source.ref + source.column)
                has_transform = bool((c or {}).get("transform"))
                src = (c or {}).get("source") or {}
                has_source = bool(src.get("ref") and src.get("column"))
                self._expect(
                    has_transform or has_source,
                    f"columns[{i}] harus punya 'transform' atau 'source.ref'+'source.column'.",
                    errors,
                )

        # primary_key
        pk = spec.get("primary_key")
        self._expect(
            isinstance(pk, list) and len(pk) > 0,
            "Field 'primary_key' wajib list dan tidak kosong.",
            errors,
        )
        if isinstance(pk, list):
            missing_pk = [k for k in pk if k not in col_names]
            self._expect(
                len(missing_pk) == 0,
                f"primary_key memuat kolom yang tidak ada: {', '.join(missing_pk)}.",
                errors,
            )

        # group_by (opsional)
        gb = spec.get("group_by") or []
        if gb:
            self._expect(
                isinstance(gb, list), "group_by harus list jika didefinisikan.", errors
            )
            if isinstance(gb, list):
                missing_gb = [g for g in gb if g not in col_names]
                self._expect(
                    len(missing_gb) == 0,
                    f"group_by memuat kolom yang tidak ada: {', '.join(missing_gb)}.",
                    errors,
                )

        return errors

    # ======================
    # SQL Generator (schema-aware)
    # ======================
    def _schema_name(self, spec):
        """
        Gunakan spec['schema'] jika ada; jika tidak, pakai placeholder '{{tenant_schema}}'
        agar bisa diganti di layer service.
        """
        s = spec.get("schema")
        if isinstance(s, str) and s.strip():
            return s.strip()
        return "{{tenant_schema}}"

    def _sql_literal(self, text):
        """
        Escape string untuk SQL literal (single-quoted).
        """
        s = text or ""
        s = s.replace("'", "''")
        return f"'{s}'"

    def _detect_main_ref(self, spec):
        """
        Tentukan source utama: prioritaskan kolom 'periode',
        kalau tidak ada pilih source pertama.
        """
        main_ref = None
        cols = spec.get("columns") or []
        for c in cols:
            if c.get("name") == "periode":
                src = c.get("source") or {}
                if src.get("ref"):
                    main_ref = src["ref"]
                    break
        if not main_ref:
            sources = spec.get("sources") or {}
            if sources:
                main_ref = list(sources.keys())[0]
        return main_ref

    def _build_select_list(self, spec):
        """
        Kembalikan list tuple (expr, alias, is_groupable).
        """
        select_items = []
        cols = spec.get("columns") or []
        for c in cols:
            alias = c.get("name")
            transform = c.get("transform")
            if transform:
                expr = transform.strip()
                select_items.append((expr, alias, False))
            else:
                src = c.get("source") or {}
                ref = src.get("ref")
                col = src.get("column")
                expr = f"{ref}.{col}"
                select_items.append((expr, alias, True))
        return select_items

    def _build_from_clause(self, spec, main_ref):
        """
        Bangun FROM + CROSS JOIN semua sources dengan schema qualification.
        """
        sources = spec.get("sources") or {}
        if not sources:
            return "", []

        order_keys = list(sources.keys())
        if main_ref in order_keys:
            order_keys.remove(main_ref)
            ordered = [main_ref] + order_keys
        else:
            ordered = order_keys

        schema = self._schema_name(spec)

        def qualify_table(t):
            t = str(t)
            return t if "." in t else f"{schema}.{t}"

        from_parts = []
        used_aliases = []
        for i, key in enumerate(ordered):
            raw_tbl = sources[key]["table"]
            tbl = qualify_table(raw_tbl)
            if i == 0:
                from_parts.append(f"FROM {tbl} {key}")
            else:
                from_parts.append(f"CROSS JOIN {tbl} {key}")
            used_aliases.append(key)

        return "\n".join(from_parts), used_aliases

    def _build_where_clause(self, spec):
        filters = spec.get("filters") or []
        exprs = []
        for f in filters:
            if isinstance(f, dict) and f.get("expression"):
                exprs.append(f.get("expression"))
            elif isinstance(f, str) and f.strip():
                exprs.append(f.strip())
        if exprs:
            return "WHERE " + "\n  AND ".join(exprs)
        return ""

    def _build_group_by_clause(self, spec, select_items):
        group_by = spec.get("group_by") or []
        if not group_by:
            return ""
        alias_to_idx = {}
        for idx, (_, alias, _) in enumerate(select_items, start=1):
            alias_to_idx[alias] = idx
        idx_list = [str(alias_to_idx[g]) for g in group_by if g in alias_to_idx]
        return "GROUP BY " + ", ".join(idx_list) if idx_list else ""

    def _generate_sql_generic(self, spec):
        """
        Generator SQL MV: schema-aware.
        """
        raw_name = spec.get("name")
        schema = self._schema_name(spec)
        fq_name = f"{schema}.{raw_name}"

        with_data = bool(self._get(spec, "refresh_policy.with_data_on_create", True))

        # SELECT
        select_items = self._build_select_list(spec)
        select_sql = ",\n".join(
            [f"    {expr} AS {alias}" for (expr, alias, _) in select_items]
        )

        # FROM
        main_ref = self._detect_main_ref(spec)
        from_sql, _ = self._build_from_clause(spec, main_ref)

        # WHERE / GROUP BY
        where_sql = self._build_where_clause(spec)
        group_by_sql = self._build_group_by_clause(spec, select_items)

        # WITH DATA / NO DATA
        with_data_sql = "WITH DATA" if with_data else "WITH NO DATA"

        # Indexes
        idxs = spec.get("indexes") or []
        idx_sql_lines = []
        if idxs and isinstance(idxs, list):
            for idx in idxs:
                if not isinstance(idx, dict):
                    continue
                idx_name = idx.get("name")
                idx_type = (idx.get("type") or "btree").lower()
                idx_cols = idx.get("columns") or []
                if not idx_name or not idx_cols:
                    continue
                # Penting: index name TIDAK di-schema-qualify
                cols_sql = ", ".join(idx_cols)
                if idx_type == "unique":
                    idx_sql_lines.append(
                        "CREATE UNIQUE INDEX IF NOT EXISTS {name} "
                        "ON {fq} ({cols});".format(
                            name=idx_name,
                            fq=fq_name,
                            cols=cols_sql,
                        )
                    )
                else:
                    idx_sql_lines.append(
                        f"CREATE INDEX IF NOT EXISTS {idx_name} ON {fq_name} ({cols_sql});"
                    )
        else:
            # Default: buat unique index dari primary_key (nama index tanpa schema)
            pk = spec.get("primary_key") or []
            if pk:
                idx_name = f"{raw_name}_pk"
                idx_sql_lines.append(
                    "CREATE UNIQUE INDEX IF NOT EXISTS {name} "
                    "ON {fq} ({cols});".format(
                        name=idx_name,
                        fq=fq_name,
                        cols=", ".join(pk),
                    )
                )

        indexes_sql = (
            "\n".join(idx_sql_lines) if idx_sql_lines else "-- (Lewati pembuatan index)"
        )

        # COMMENTS / PII
        desc = spec.get("description") or ""
        contains_pii = bool(self._get(spec, "security.pii.contains_pii", False))
        pii_cols = self._get(spec, "security.pii.columns", []) or []
        pii_note = ""
        if contains_pii and pii_cols:
            pii_note = f" Mengandung PII pada kolom: {', '.join(pii_cols)}."
        elif contains_pii:
            pii_note = " Mengandung PII."
        mv_comment = (desc + pii_note).strip() or raw_name

        sql = f"""
-- [AUTO-GENERATED] Materialized View: {fq_name}
CREATE MATERIALIZED VIEW IF NOT EXISTS {fq_name} AS
SELECT
{select_sql}
{from_sql}
{where_sql if where_sql else ""}
{group_by_sql if group_by_sql else ""}
{with_data_sql};

-- Indexes
{indexes_sql}

-- Comments
COMMENT ON MATERIALIZED VIEW {fq_name}
    IS {self._sql_literal(mv_comment)};

-- Contoh perintah refresh (jalankan via scheduler: pg_cron/n8n/systemd timer)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY {fq_name};
""".strip()

        return sql

    # ======================
    # Utilities (newline normalization)
    # ======================
    @staticmethod
    def _denormalize_newlines(text: str) -> str:
        """
        Ubah literal '\\n' / '\\r\\n' menjadi baris baru asli agar output tidak berisi
        karakter backslash-n yang menyebabkan error saat dieksekusi di PostgreSQL.
        """
        if not text:
            return ""
        text = text.replace("\\r\\n", "\n")
        text = text.replace("\\n", "\n")
        text = text.replace("\r\n", "\n")
        return text

    # ======================
    # Compute
    # ======================
    @api.depends("specification")
    def _compute_sql_script(self):
        for record in self:
            record.sql_script = ""

            spec, parse_errors = record._load_spec(record.specification or "")
            if parse_errors:
                record.sql_script = record._sql_comment_block(
                    ["Gagal mem-parsing specification."] + parse_errors
                )
                continue

            val_errors = record._validate_spec_generic(spec)
            if val_errors:
                record.sql_script = record._sql_comment_block(
                    ["Specification tidak valid:"] + val_errors
                )
                continue

            try:
                sql = record._generate_sql_generic(spec)
                # Normalisasi literal newline agar tidak ada '\n' escaped
                sql = self._denormalize_newlines(sql)
                # Biarkan multiline, jangan diflatten jadi single-line
                record.sql_script = sql
            except Exception as e:
                record.sql_script = record._sql_comment_block(
                    [f"Gagal menghasilkan SQL dari specification: {e}"]
                )

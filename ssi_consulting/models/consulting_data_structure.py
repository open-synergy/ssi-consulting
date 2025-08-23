# consulting_data_structure.py
# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
#
# Catatan: Mekanisme tenant-per-schema. Jika spec tidak menyediakan "schema",
#          gunakan placeholder {{tenant_schema}}.

import re
from typing import Any, Dict, List, Optional, Tuple

from odoo import api, fields, models

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def _as_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        v = val.strip().lower()
        if v in {"true", "yes", "y", "1"}:
            return True
        if v in {"false", "no", "n", "0"}:
            return False
    return default


def _norm_ident(s: str) -> str:
    """
    Normalisasi identifier menjadi snake_case aman.
    Tidak menambahkan quoting agar tetap sederhana & konsisten.
    """
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.lower().strip("_")


def _join_cols(cols: List[str]) -> str:
    return ", ".join(cols)


# -------------------------------------------------------------------------
# Tenant schema placeholder
# -------------------------------------------------------------------------
PLACEHOLDER_TENANT_SCHEMA = "{{tenant_schema}}"


def _get_schema(spec: Dict[str, Any]) -> str:
    """
    Ambil schema dari spec; jika tidak ada, gunakan placeholder tenant.
    """
    return spec.get("schema") or PLACEHOLDER_TENANT_SCHEMA


class ConsultingDataStructure(models.Model):
    _name = "consulting_data_structure"
    _description = "Consulting Data Structure"
    _inherit = [
        "mixin.master_data",
    ]

    specification = fields.Text(
        string="Specification",
        required=True,
        help="YAML specification describing the SQL entity, fields, constraints, and indexes.",
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

    # -------------------------------------------------------------------------
    # YAML -> Dict parser
    # -------------------------------------------------------------------------
    def _parse_spec(self, spec_text: str) -> Optional[Dict[str, Any]]:
        if not spec_text or not yaml:
            return None
        try:
            data = yaml.safe_load(spec_text) or {}
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Phase 1: CREATE TABLE (no FK)
    # -------------------------------------------------------------------------
    def _build_phase1_sql(self, spec: Dict[str, Any]) -> str:
        schema = _get_schema(spec)
        entity = spec.get("entity", {}) or {}
        entity_name = _norm_ident(
            entity.get("technical_name") or spec.get("technical_name") or ""
        )
        if not entity_name:
            return ""

        fields_spec = spec.get("fields") or []
        cols_parts: List[Tuple[str, List[str]]] = []
        pks: List[str] = []

        for f in fields_spec:
            fname = _norm_ident(f.get("technical_name") or "")
            if not fname:
                continue
            ftype = (f.get("type") or "text").strip()
            not_null = _as_bool(f.get("not_null"), False)
            default_val = f.get("default")
            is_pk = _as_bool(f.get("pk"), False)

            col_parts = [fname, ftype]
            if isinstance(default_val, str) and default_val.strip():
                col_parts.append(default_val.strip())
            if not_null:
                col_parts.append("NOT NULL")
            if is_pk:
                pks.append(fname)

            cols_parts.append((fname, col_parts))

        if len(pks) == 1:
            single_pk = pks[0]
            cols_sql = []
            for fname, parts in cols_parts:
                if fname == single_pk:
                    parts = parts + ["PRIMARY KEY"]
                cols_sql.append(" ".join(parts))
        elif len(pks) > 1:
            cols_sql = [" ".join(parts) for _, parts in cols_parts]
            cols_sql.append(f"PRIMARY KEY ({_join_cols(pks)})")
        else:
            cols_sql = [" ".join(parts) for _, parts in cols_parts]

        create_table = [
            f"CREATE TABLE IF NOT EXISTS {schema}.{entity_name} (",
            "    " + ",\n    ".join(cols_sql),
            ");",
        ]

        return "\n".join(create_table).strip() + "\n"

    # -------------------------------------------------------------------------
    # Phase 3: FK only
    # -------------------------------------------------------------------------
    def _build_phase3_sql(self, spec: Dict[str, Any]) -> str:
        schema = _get_schema(spec)
        entity = spec.get("entity", {}) or {}
        entity_name = _norm_ident(
            entity.get("technical_name") or spec.get("technical_name") or ""
        )
        if not entity_name:
            return ""

        fields_spec = spec.get("fields") or []
        stmts: List[str] = []

        for f in fields_spec:
            fname = _norm_ident(f.get("technical_name") or "")
            if not fname:
                continue
            fk = f.get("fk")
            if not fk:
                continue

            ref_schema = fk.get("ref_schema") or schema
            ref_table = _norm_ident(fk.get("ref_table") or "")
            ref_column = _norm_ident(fk.get("ref_column") or "id")

            if not ref_table:
                continue

            on_delete = (fk.get("on_delete") or "NO ACTION").upper().strip()
            on_update = (fk.get("on_update") or "NO ACTION").upper().strip()
            conname = _norm_ident(f"{entity_name}_{fname}_fk")

            fk_sql = f"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.contype = 'f'
          AND c.conname = '{conname}'
          AND n.nspname = '{schema}'
          AND t.relname = '{entity_name}'
    ) THEN
        ALTER TABLE {schema}.{entity_name}
            ADD CONSTRAINT {conname}
            FOREIGN KEY ({fname})
            REFERENCES {ref_schema}.{ref_table}({ref_column})
            ON DELETE {on_delete}
            ON UPDATE {on_update}
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END$$;
""".strip()
            stmts.append(fk_sql)

        return ("\n\n".join(stmts).strip() + "\n") if stmts else ""

    # -------------------------------------------------------------------------
    # Phase 4: Index + comments
    # -------------------------------------------------------------------------
    def _build_phase4_sql(self, spec: Dict[str, Any]) -> str:
        schema = _get_schema(spec)
        entity = spec.get("entity", {}) or {}
        entity_name = _norm_ident(
            entity.get("technical_name") or spec.get("technical_name") or ""
        )
        if not entity_name:
            return ""

        fields_spec: List[Dict[str, Any]] = spec.get("fields") or []
        indexes_spec: List[Dict[str, Any]] = spec.get("indexes") or []
        stmts: List[str] = []

        table_comment = entity.get("comment") or spec.get("comment")
        if isinstance(table_comment, str) and table_comment.strip():
            safe_comment = table_comment.replace("'", "''")
            stmts.append(
                f"COMMENT ON TABLE {schema}.{entity_name} IS '{safe_comment}';"
            )

        for f in fields_spec:
            fname = _norm_ident(f.get("technical_name") or "")
            if not fname:
                continue

            f_comment = f.get("comment")
            if isinstance(f_comment, str) and f_comment.strip():
                safe_c = f_comment.replace("'", "''")
                stmts.append(
                    f"COMMENT ON COLUMN {schema}.{entity_name}.{fname} IS '{safe_c}';"
                )

            if _as_bool(f.get("unique"), False):
                iname = _norm_ident(f"idxu_{entity_name}_{fname}")
                stmts.append(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {iname} "
                    f"ON {schema}.{entity_name}({fname});"
                )

        for idx in indexes_spec:
            cols = idx.get("columns") or []
            if not isinstance(cols, list) or not cols:
                continue
            cols_n = [_norm_ident(c) for c in cols if c]
            cols_n = [c for c in cols_n if c]
            if not cols_n:
                continue

            unique_idx = _as_bool(idx.get("unique"), False)
            base = "idxu" if unique_idx else "idx"
            iname = _norm_ident(f"{base}_{entity_name}_{'_'.join(cols_n)}")
            cols_expr = _join_cols(cols_n)
            unique_kw = "UNIQUE " if unique_idx else ""
            stmts.append(
                f"CREATE {unique_kw}INDEX IF NOT EXISTS {iname} "
                f"ON {schema}.{entity_name}({cols_expr});"
            )

        # Index otomatis untuk kolom FK
        for f in fields_spec:
            fname = _norm_ident(f.get("technical_name") or "")
            if not fname:
                continue
            fk = f.get("fk")
            if not fk:
                continue
            idx_name = _norm_ident(f"idx_{entity_name}_{fname}")
            stmts.append(
                f"CREATE INDEX IF NOT EXISTS {idx_name} "
                f"ON {schema}.{entity_name}({fname});"
            )

        return ("\n".join(stmts).strip() + "\n") if stmts else ""

    # -------------------------------------------------------------------------
    # COMPUTE FIELDS
    # -------------------------------------------------------------------------
    @api.depends("specification")
    def _compute_table_sql_script(self):
        for record in self:
            spec = self._parse_spec(record.specification)
            if not spec:
                record.table_sql_script = ""
                continue
            record.table_sql_script = self._build_phase1_sql(spec)

    @api.depends("specification")
    def _compute_fk_sql_script(self):
        for record in self:
            spec = self._parse_spec(record.specification)
            if not spec:
                record.fk_sql_script = ""
                continue
            record.fk_sql_script = self._build_phase3_sql(spec)

    @api.depends("specification")
    def _compute_additional_sql_script(self):
        for record in self:
            spec = self._parse_spec(record.specification)
            if not spec:
                record.additional_sql_script = ""
                continue
            record.additional_sql_script = self._build_phase4_sql(spec)

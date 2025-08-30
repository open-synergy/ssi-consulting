# Rebuild _compute_payload to follow new schema (Superset-native viz_type)
# Copyright 2025
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging
from typing import Any, Dict, List, Optional

import yaml
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Viz bawaan yang umum & stabil (sinkron dengan schema)
_SUPPORTED_VIZ_TYPES = {
    # Time-series (ECharts generic + mixed)
    "echarts_timeseries_line",
    "echarts_timeseries_area",
    "echarts_timeseries_bar",
    "mixed_timeseries",
    # Komposisi / distribusi
    "pie",
    "treemap",
    "sunburst",
    "histogram",
    "box_plot",
    "heatmap",
    "dist_bar",
    "funnel",
    # Tabel & angka
    "table",
    "pivot_table_v2",
    "big_number",
    "big_number_total",
    # Flow / network
    "sankey",
    "event_flow",
    "chord",
    # Geo
    "world_map",
    "country_map",
    # Lainnya
    "word_cloud",
    "echarts_gauge",
}

# Backward-compat optional (jika ada spec lama pakai label non-bawaan)
_KIND_TO_VIZ = {
    "timeseries_line": "echarts_timeseries_line",
    "timeseries_area": "echarts_timeseries_area",
    "timeseries_bar": "echarts_timeseries_bar",
    "mixed_chart": "mixed_timeseries",
    "bar": "dist_bar",
    "pie": "pie",
    "treemap": "treemap",
    "sunburst": "sunburst",
    "heatmap": "heatmap",
    "boxplot": "box_plot",
    "histogram": "histogram",
    "funnel": "funnel",
    "table": "table",
    "pivot_table": "pivot_table_v2",
    "big_number": "big_number",
    "big_number_total": "big_number_total",
    "word_cloud": "word_cloud",
    "world_map": "world_map",
    "country_map": "country_map",
    "gauge": "echarts_gauge",
    "sankey": "sankey",
    "chord": "chord",
    "event_flow": "event_flow",
}


def _build_metric(m: Dict[str, Any]):
    name = (m or {}).get("name")
    expr = (m or {}).get("expr")
    label = (m or {}).get("label") or name or "metric"
    if expr:
        return {"expressionType": "SQL", "label": label, "sqlExpression": expr}
    return name or "count"


def _as_int(val: Any, default: int) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _load_schema(env) -> Optional[Dict[str, Any]]:
    try:
        module = "ssi_consulting"  # sesuaikan jika modulmu beda
        base = env["ir.module.module"].get_module_path(module)
        if not base:
            return None
        path = f"{base}/schema/chart_schema.yaml"
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        _logger.debug("Gagal muat schema: %s", exc)
        return None


def _validate_spec(spec: Dict[str, Any], env) -> None:
    try:
        import jsonschema  # opsional
    except Exception:
        _logger.debug("jsonschema tidak ada; lewati validasi.")
        return
    schema = _load_schema(env)
    if schema:
        jsonschema.validate(instance=spec, schema=schema)
    else:
        _logger.debug("Schema tidak ditemukan; lewati validasi.")


def _normalize_time_grain(val: Any) -> Optional[str]:
    """
    Ubah 'month', 'MONTH', 'Month' → 'P1M'.
    Jika sudah ISO-8601 (P1M, P1Y, PT1H, dst.) langsung return.
    """
    if not val:
        return None
    if isinstance(val, str) and val.upper().startswith("P"):
        return val
    mapping = {
        "SECOND": "PT1S",
        "MINUTE": "PT1M",
        "HOUR": "PT1H",
        "DAY": "P1D",
        "WEEK": "P1W",
        "MONTH": "P1M",
        "QUARTER": "P3M",
        "YEAR": "P1Y",
    }
    return mapping.get(str(val).strip().upper())


class ConsultingChartTemplate(models.Model):
    _name = "consulting_chart_template"
    _description = "Consulting Chart Template"
    _inherit = ["mixin.master_data"]

    specification = fields.Text(
        string="Specification",
        required=True,
        help="YAML mengikuti ssi_consulting/schema/chart_schema.yaml",
    )
    materialized_view_id = fields.Many2one(
        comodel_name="consulting_materialized_view",
        string="Materialized View",
        required=True,
        help="Harus menyimpan superset_dataset_id (ID dataset di Superset).",
    )
    schema_parser_id = fields.Many2one(
        string="Schema Parser",
        comodel_name="consulting_schema_parser",
        required=True,
    )
    superset_chart_creation_payload = fields.Text(
        string="Payload",
        compute="_compute_superset_chart_creation_payload",
        store=True,
        help="JSON payload untuk POST /api/v1/chart di Superset.",
    )
    payload = fields.Text(
        string="Payload",
        compute="_compute_payload",
        store=True,
        help="JSON payload untuk POST /api/v1/chart di Superset.",
    )

    @api.depends(
        "specification",
        "schema_parser_id",
    )
    def _compute_superset_chart_creation_payload(self):
        for record in self:
            if record.specification and record.schema_parser_id:
                payload = record.schema_parser_id._parse_specification(
                    record.specification
                )
                record.superset_chart_creation_payload = json.dumps(
                    payload, ensure_ascii=False, indent=2
                )
            else:
                record.superset_chart_creation_payload = False

    def _compute_payload(self):  # noqa: C901
        for rec in self:
            rec.payload = ""
            # 1) Parse YAML
            try:
                spec = yaml.safe_load(rec.specification or "") or {}
            except Exception as exc:
                _logger.warning("Specification YAML invalid: %s", exc)
                spec = {}

            # 2) viz_type langsung; fallback dari type.kind jika perlu
            viz_type = (spec.get("viz_type") or "").strip()
            if not viz_type:
                kind = (spec.get("type", {}) or {}).get("kind") or ""
                if kind in _KIND_TO_VIZ:
                    viz_type = _KIND_TO_VIZ[kind]
                    spec["viz_type"] = viz_type  # normalisasi

            # 3) Validasi opsional
            try:
                _validate_spec(spec, self.env)
            except Exception as exc:
                _logger.warning("Spec tidak valid lawan schema: %s", exc)

            # 4) Ekstrak bagian umum
            title = spec.get("title") or spec.get("technical_name") or "Untitled"
            description = spec.get("description") or ""
            dataset_spec = spec.get("dataset") or {}
            time_spec = spec.get("time") or {}
            query = spec.get("query") or {}
            encoding = spec.get("encoding") or {}
            presentation = spec.get("presentation") or {}

            datasource_type = "table"
            datasource_id = (
                getattr(rec.materialized_view_id, "superset_dataset_id", None)
                or "__DATASOURCE_ID__"
            )

            group_by = list(query.get("group_by") or [])
            raw_metrics = list(query.get("metrics") or [])
            order_by = list(query.get("order_by") or [])
            row_limit = _as_int(query.get("row_limit"), 1000)
            filters = list(query.get("filters") or [])

            metrics = [_build_metric(m) for m in raw_metrics] or ["count"]
            adhoc_filters = []
            for f in filters:
                col = f.get("col")
                op = (f.get("op") or "").upper()
                val = f.get("val")
                if col and op:
                    adhoc_filters.append(
                        {
                            "expressionType": "SIMPLE",
                            "subject": col,
                            "operator": op,
                            "comparator": val,
                        }
                    )

            granularity_sqla = time_spec.get("column") or None
            time_grain_sqla = _normalize_time_grain(time_spec.get("grain"))
            time_range = time_spec.get("range") or "No filter"

            enc_x = (encoding.get("x") or {}).get("field")
            enc_y = (encoding.get("y") or {}).get("field")
            enc_color = (encoding.get("color") or {}).get("field")
            enc_size = (encoding.get("size") or {}).get("field")
            enc_pivot = encoding.get("pivot") or {}

            show_legend = bool(presentation.get("legend", True))
            stack = bool(presentation.get("stack", False))
            orientation = (presentation.get("orientation") or "vertical").lower()
            axis = presentation.get("axis") or {}
            label_cfg = presentation.get("label") or {}
            sort_mode = (presentation.get("sort_mode") or "none").lower()

            form_data: Dict[str, Any] = {
                "adhoc_filters": adhoc_filters,
                "row_limit": row_limit,
                "time_range": time_range,
                "query_mode": "aggregate",
            }
            if granularity_sqla:
                form_data["granularity_sqla"] = granularity_sqla
            if time_grain_sqla:
                form_data["time_grain_sqla"] = time_grain_sqla

            def _apply_order(fd: Dict[str, Any]):
                if not order_by:
                    return
                first = order_by[0]
                by = first.get("by")
                desc = bool(first.get("desc", True))
                fd["order_desc"] = desc
                if isinstance(by, str):
                    fd.setdefault("orderby", [])
                    fd["orderby"].append([by, desc])

            # 5) Branch per viz_type
            if viz_type == "table":
                all_cols: List[str] = []
                all_cols.extend(group_by)
                if enc_x and enc_x not in all_cols:
                    all_cols.append(enc_x)
                form_data.update(
                    {
                        "all_columns": all_cols,
                        "metrics": metrics if metrics else [],
                        "server_pagination": True,
                    }
                )
                _apply_order(form_data)

            elif viz_type in ("big_number_total", "big_number"):
                form_data.update({"metric": metrics[0] if metrics else "count"})

            elif viz_type in (
                "echarts_timeseries_line",
                "echarts_timeseries_area",
                "echarts_timeseries_bar",
                "mixed_timeseries",
            ):
                form_data.update(
                    {
                        "metrics": metrics,
                        "show_legend": show_legend,
                    }
                )
                _apply_order(form_data)

            elif viz_type == "dist_bar":
                is_long = bool(enc_x and enc_y and enc_color)
                if is_long:
                    x_axis = enc_x
                    groupby_cols = [enc_x, enc_color]
                    metric_label = enc_y or "value"
                    metrics_eff = [
                        {
                            "expressionType": "SQL",
                            "label": metric_label,
                            "sqlExpression": f"SUM({enc_y})",
                        }
                    ]
                else:
                    x_axis = enc_x or (group_by[0] if group_by else None)
                    groupby_cols = list(group_by)
                    metrics_eff = metrics
                    if x_axis and x_axis not in groupby_cols:
                        groupby_cols.insert(0, x_axis)

                form_data.update(
                    {
                        "x_axis": x_axis,
                        "groupby": groupby_cols,
                        "metrics": metrics_eff,
                        "stack": bool(stack),
                        "seriesType": "bar",
                        "orientation": (
                            "horizontal" if orientation == "horizontal" else "vertical"
                        ),
                        "show_legend": show_legend,
                    }
                )
                if sort_mode == "by_metric" and metrics_eff:
                    form_data["seriesLimitMetric"] = metrics_eff[0]
                _apply_order(form_data)

            elif viz_type == "pie":
                group = (
                    [enc_color]
                    if enc_color
                    else ([enc_x] if enc_x else (group_by[:1] if group_by else []))
                )
                form_data.update(
                    {
                        "groupby": group,
                        "metric": metrics[0] if metrics else "count",
                        "number_format": label_cfg.get("format"),
                        "show_legend": show_legend,
                    }
                )

            elif viz_type in ("treemap", "sunburst"):
                form_data.update(
                    {
                        "groupby": group_by or ([enc_x] if enc_x else []),
                        "metric": metrics[0] if metrics else "count",
                        "show_labels": bool(label_cfg.get("show_value", False)),
                        "number_format": label_cfg.get("format"),
                    }
                )

            elif viz_type == "heatmap":
                if enc_x and enc_color and enc_y:
                    form_data.update(
                        {
                            "groupby": [enc_x, enc_color],
                            "metric": {
                                "expressionType": "SQL",
                                "label": enc_y,
                                "sqlExpression": f"SUM({enc_y})",
                            },
                        }
                    )
                else:
                    form_data.update(
                        {
                            "groupby": group_by[:2],
                            "metric": metrics[0] if metrics else "count",
                        }
                    )

            elif viz_type == "histogram":
                target = enc_x or (group_by[0] if group_by else None)
                form_data.update(
                    {
                        "all_columns_x": [target] if target else [],
                        "row_limit": row_limit,
                    }
                )

            elif viz_type == "box_plot":
                columns = [enc_x] if enc_x else (group_by[:1] if group_by else [])
                form_data.update(
                    {
                        "columns": columns,
                        "metric": metrics[0] if metrics else "count",
                        "show_legend": show_legend,
                    }
                )

            elif viz_type == "funnel":
                form_data.update(
                    {
                        "groupby": group_by or ([enc_x] if enc_x else []),
                        "metric": metrics[0] if metrics else "count",
                    }
                )

            elif viz_type == "pivot_table_v2":
                rows = list(enc_pivot.get("rows") or [])
                cols = list(enc_pivot.get("columns") or [])
                pvt_metrics = list(enc_pivot.get("metrics") or []) or metrics
                form_data.update(
                    {
                        "groupbyRows": rows,
                        "groupbyColumns": cols,
                        "metrics": pvt_metrics,
                        "row_limit": row_limit,
                    }
                )

            elif viz_type == "word_cloud":
                col = enc_x or (group_by[0] if group_by else None)
                form_data.update(
                    {
                        "groupby": [col] if col else [],
                        "metric": metrics[0] if metrics else "count",
                    }
                )

            elif viz_type in ("world_map", "country_map"):
                geo_col = enc_x or (group_by[0] if group_by else None)
                form_data.update(
                    {
                        "entity": geo_col,
                        "metric": metrics[0] if metrics else "count",
                    }
                )

            elif viz_type == "echarts_gauge":
                form_data.update({"metric": metrics[0] if metrics else "count"})

            elif viz_type == "sankey":
                source = enc_x or (group_by[0] if group_by else None)
                target = enc_color or (group_by[1] if len(group_by) > 1 else None)
                form_data.update(
                    {
                        "source": source,
                        "target": target,
                        "metric": metrics[0] if metrics else "count",
                    }
                )

            elif viz_type == "chord":
                form_data.update(
                    {
                        "groupby": group_by[:2],
                        "metric": metrics[0] if metrics else "count",
                    }
                )

            elif viz_type == "event_flow":
                form_data.update(
                    {
                        "all_columns": group_by or ([enc_x] if enc_x else []),
                    }
                )

            else:
                _logger.warning(
                    "viz_type '%s' belum di-handle khusus; gunakan form_data minimal",
                    viz_type,
                )

            # Axis/label opsional
            if axis.get("x_label"):
                form_data["x_axis_label"] = axis.get("x_label")
            if axis.get("y_label"):
                form_data["y_axis_label"] = axis.get("y_label")
            if isinstance(axis.get("rotate_x"), int):
                form_data["xAxisLabelRotation"] = axis.get("rotate_x")

            # Hints (debug, tidak dipakai Superset)
            form_data["_dataset_hint"] = {
                "schema": dataset_spec.get("schema"),
                "table": dataset_spec.get("table"),
            }
            form_data["_encoding_hint"] = {
                "x": enc_x,
                "y": enc_y,
                "color": enc_color,
                "size": enc_size,
                "pivot": enc_pivot,
            }

            payload = {
                "slice_name": title,
                "viz_type": viz_type or "table",
                "datasource_id": datasource_id,
                "datasource_type": datasource_type,
                "description": description,
                "cache_timeout": 0,
                "params": json.dumps(form_data, ensure_ascii=False),
            }
            rec.payload = json.dumps(payload, ensure_ascii=False, indent=2)

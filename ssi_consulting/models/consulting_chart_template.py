# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

import yaml
from odoo import fields, models

_KIND_TO_VIZ = {
    "table": "table",
    "big_number_total": "big_number_total",
    "big_number_trend": "big_number",  # trend/with sparkline
    "timeseries_line": "echarts_timeseries_line",
    "timeseries_area": "echarts_timeseries_area",
    "timeseries_bar": "echarts_timeseries_bar",
    "bar": "echarts_bar",
    "bar_stacked": "echarts_bar",
    "stacked_bar": "echarts_bar",  # alias tambahan
    "pie": "echarts_pie",
    "treemap": "treemap_v2",
    "scatter": "echarts_scatter",
    "pivot_table": "pivot_table_v2",
    "boxplot": "box_plot",
    "histogram": "histogram",
}


def _build_adhoc_metric(spec_metric):
    """
    Return a metric entry acceptable by Superset form_data.
    - If spec_metric has 'expr' → adhoc SQL metric.
    - Else → reference saved metric by label (string).
    """
    name = (spec_metric or {}).get("name")
    expr = (spec_metric or {}).get("expr")
    if expr:
        return {
            "expressionType": "SQL",
            "label": name or "metric",
            "sqlExpression": expr,
        }
    # refer saved metric by name (string)
    return name or "count"


class ConsultingChartTemplate(models.Model):
    _name = "consulting_chart_template"
    _description = "Consulting Chart Template"
    _inherit = [
        "mixin.master_data",
    ]

    specification = fields.Text(
        string="Specification",
        required=True,
    )
    materialized_view_id = fields.Many2one(
        string="Materialized View",
        comodel_name="consulting_materialized_view",
        required=True,
    )
    payload = fields.Text(
        string="Payload",
        compute="_compute_payload",
        store=True,
    )

    def _compute_payload(self):
        for record in self:
            record.payload = ""
            try:
                spec = yaml.safe_load(record.specification or "") or {}
            except Exception:
                spec = {}

            # --- Ambil elemen spesifikasi umum ---
            technical_name = spec.get("technical_name") or ""
            title = spec.get("title") or technical_name or "Untitled"
            description = spec.get("description") or ""

            type_dict = spec.get("type") or {}
            kind = (type_dict.get("kind") or "bar_stacked").strip()
            viz_type = _KIND_TO_VIZ.get(kind, "echarts_bar")

            dataset_spec = spec.get("dataset") or {}
            time_spec = spec.get("time") or {}
            query = spec.get("query") or {}
            encoding = spec.get("encoding") or {}
            presentation = spec.get("presentation") or {}

            datasource_type = "table"
            # gunakan placeholder jika tidak ada
            datasource_id = getattr(
                record.materialized_view_id, "superset_dataset_id", None
            )
            if not datasource_id:
                datasource_id = "__DATASOURCE_ID__"

            # --- Query components ---
            group_by = list(query.get("group_by") or [])
            raw_metrics = list(query.get("metrics") or [])
            list(query.get("order_by") or [])
            row_limit = int(query.get("row_limit") or 1000)
            filters = list(query.get("filters") or [])

            metrics = [_build_adhoc_metric(m) for m in raw_metrics] or ["count"]

            adhoc_filters = []
            for f in filters:
                col = f.get("col")
                op = (f.get("op") or "").upper()
                val = f.get("val")
                if not col or not op:
                    continue
                adhoc_filters.append(
                    {
                        "expressionType": "SIMPLE",
                        "subject": col,
                        "operator": op,
                        "comparator": val,
                    }
                )

            granularity_sqla = time_spec.get("column") or None
            time_grain_sqla = time_spec.get("grain") or None
            time_range = time_spec.get("range") or "No filter"

            enc_x = (encoding.get("x") or {}).get("field")
            (encoding.get("y") or {}).get("field")
            (encoding.get("color") or {}).get("field")
            (encoding.get("size") or {}).get("field")
            encoding.get("pivot") or {}

            show_legend = bool(presentation.get("legend", True))
            stack = bool(
                presentation.get("stack", kind in ("bar_stacked", "stacked_bar"))
            )
            orientation = (presentation.get("orientation") or "vertical").lower()
            axis = presentation.get("axis") or {}
            presentation.get("label") or {}
            (presentation.get("sort_mode") or "none").lower()

            # ---------- Bentuk form_data dasar ----------
            form_data = {
                "adhoc_filters": adhoc_filters,
                "row_limit": row_limit,
                "time_range": time_range,
            }
            if granularity_sqla:
                form_data["granularity_sqla"] = granularity_sqla
            if time_grain_sqla:
                form_data["time_grain_sqla"] = time_grain_sqla

            # mapping ringkas untuk stacked bar (sesuai spek Anda)
            if viz_type == "echarts_bar":
                x_axis = enc_x or (group_by[0] if group_by else None)
                if x_axis and x_axis not in group_by:
                    group_by = [x_axis] + group_by
                form_data.update(
                    {
                        "x_axis": x_axis,
                        "groupby": group_by,
                        "metrics": metrics,
                        "stack": bool(stack),
                        "seriesType": "bar",
                        "orientation": (
                            "horizontal" if orientation == "horizontal" else "vertical"
                        ),
                        "show_legend": show_legend,
                    }
                )

            # label & axis opsional
            if axis.get("x_label"):
                form_data["x_axis_label"] = axis.get("x_label")
            if axis.get("y_label"):
                form_data["y_axis_label"] = axis.get("y_label")
            if isinstance(axis.get("rotate_x"), int):
                form_data["xAxisLabelRotation"] = axis.get("rotate_x")

            # Tambahkan hint dataset untuk audit (tidak dipakai Superset)
            form_data["_dataset_hint"] = {
                "schema": dataset_spec.get("schema"),
                "table": dataset_spec.get("table"),
            }

            payload_dict = {
                "slice_name": title,
                "viz_type": viz_type,
                "datasource_id": datasource_id,  # placeholder aman
                "datasource_type": datasource_type,
                "description": description,
                "cache_timeout": 0,
                "params": json.dumps(form_data, ensure_ascii=False),
            }

            record.payload = json.dumps(payload_dict, ensure_ascii=False, indent=2)

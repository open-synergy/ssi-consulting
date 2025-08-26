# Copyright 2025 OpenSynergy Indonesia
# Copyright 2025 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

import yaml
from odoo import fields, models

# ---------------------------------------------------------------------
# HANYA gunakan viz_type berikut (sesuai permintaan):
# Time-series    : line_chart, area_chart, bar_chart, mixed_chart
# Kuantitas/Kompo: pie, dist_bar, treemap, sunburst, heatmap, box_plot, funnel
# Tabel/Angka    : table, pivot_table, big_number, big_number_total
# Lainnya        : word_cloud, world_map, echarts_gauge, sankey, event_flow
# ---------------------------------------------------------------------

# Pemetaan "type.kind" → "viz_type" final Superset (versi naming yang kamu inginkan)
_KIND_TO_VIZ = {
    # time-series
    "timeseries_line": "line_chart",
    "timeseries_area": "area_chart",
    "timeseries_bar": "bar_chart",
    "mixed_chart": "mixed_chart",
    # bar kategori / distribusi (non-waktu)
    "bar": "dist_bar",
    "bar_stacked": "dist_bar",
    "stacked_bar": "dist_bar",
    # kuantitas & komposisi
    "pie": "pie",
    "treemap": "treemap",
    "sunburst": "sunburst",
    "heatmap": "heatmap",
    "boxplot": "box_plot",
    "funnel": "funnel",
    # tabel & angka
    "table": "table",
    "pivot_table": "pivot_table",
    "big_number": "big_number",
    "big_number_total": "big_number_total",
    # lainnya
    "word_cloud": "word_cloud",
    "world_map": "world_map",
    "gauge": "echarts_gauge",
    "echarts_gauge": "echarts_gauge",
    "sankey": "sankey",
    "event_flow": "event_flow",
}


def _build_adhoc_metric(spec_metric):
    """
    Bangun metric untuk Superset form_data.
    - Jika ada 'expr' → adhoc SQL metric.
    - Jika tidak ada → referensi nama saved metric ('name') atau fallback 'count'.
    """
    name = (spec_metric or {}).get("name")
    expr = (spec_metric or {}).get("expr")
    if expr:
        return {
            "expressionType": "SQL",
            "label": name or "metric",
            "sqlExpression": expr,
        }
    return name or "count"


class ConsultingChartTemplate(models.Model):
    _name = "consulting_chart_template"
    _description = "Consulting Chart Template"
    _inherit = ["mixin.master_data"]

    specification = fields.Text(
        string="Specification",
        required=True,
        help="""YAML spesifikasi chart mengikuti chart-schema
(type, dataset, time, query, encoding, presentation).""",
    )
    materialized_view_id = fields.Many2one(
        string="Materialized View",
        comodel_name="consulting_materialized_view",
        required=True,
        help="Objek MV yang menyimpan superset_dataset_id (ID dataset di Superset).",
    )
    payload = fields.Text(
        string="Payload",
        compute="_compute_payload",
        store=True,
        help="Payload JSON untuk POST /api/v1/chart Superset.",
    )

    def _compute_payload(self):  # noqa: C901
        for record in self:
            record.payload = ""
            try:
                spec = yaml.safe_load(record.specification or "") or {}
            except Exception:
                spec = {}

            # --- Elemen umum dari schema ---
            technical_name = spec.get("technical_name") or ""
            title = spec.get("title") or technical_name or "Untitled"
            description = spec.get("description") or ""

            type_dict = spec.get("type") or {}
            kind = (type_dict.get("kind") or "bar").strip()
            viz_type = _KIND_TO_VIZ.get(
                kind, "dist_bar"
            )  # default ke dist_bar (bar kategori)

            dataset_spec = spec.get("dataset") or {}
            time_spec = spec.get("time") or {}
            query = spec.get("query") or {}
            encoding = spec.get("encoding") or {}
            presentation = spec.get("presentation") or {}

            # Datasource (gunakan placeholder jika tidak ada)
            datasource_type = "table"
            datasource_id = getattr(
                record.materialized_view_id, "superset_dataset_id", None
            )
            if not datasource_id:
                datasource_id = "__DATASOURCE_ID__"

            # --- Query components ---
            group_by = list(query.get("group_by") or [])
            raw_metrics = list(query.get("metrics") or [])
            order_by = list(query.get("order_by") or [])
            row_limit = int(query.get("row_limit") or 1000)
            filters = list(query.get("filters") or [])

            # Metrics (wide-form default)
            metrics = [_build_adhoc_metric(m) for m in raw_metrics] or ["count"]

            # Adhoc filters sederhana
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

            # --- Time settings (sesuai chart-schema) ---
            granularity_sqla = time_spec.get("column") or None
            time_grain_sqla = time_spec.get("grain") or None
            time_range = time_spec.get("range") or "No filter"

            # --- Encoding (sesuai chart-schema) ---
            enc_x = (encoding.get("x") or {}).get("field")
            enc_y = (encoding.get("y") or {}).get("field")
            enc_color = (encoding.get("color") or {}).get("field")
            enc_size = (encoding.get("size") or {}).get("field")
            enc_pivot = encoding.get("pivot") or {}

            # --- Presentation ---
            show_legend = bool(presentation.get("legend", True))
            stack = bool(
                presentation.get("stack", kind in ("bar_stacked", "stacked_bar"))
            )
            orientation = (presentation.get("orientation") or "vertical").lower()
            axis = presentation.get("axis") or {}
            label_cfg = presentation.get("label") or {}
            sort_mode = (presentation.get("sort_mode") or "none").lower()

            # ---------- Form data dasar ----------
            form_data = {
                "adhoc_filters": adhoc_filters,
                "row_limit": row_limit,
                "time_range": time_range,
                "query_mode": "aggregate",
            }
            if granularity_sqla:
                form_data["granularity_sqla"] = granularity_sqla
            if time_grain_sqla:
                form_data["time_grain_sqla"] = time_grain_sqla

            # Helper: apply order (sederhana; ambil entri pertama)
            def _apply_order(fd):
                if not order_by:
                    return
                first = order_by[0]
                by = first.get("by")
                desc = bool(first.get("desc", True))
                fd["order_desc"] = desc
                if isinstance(by, str):
                    fd.setdefault("orderby", [])
                    fd["orderby"].append([by, desc])

            # ---------- Mapping per viz (disederhanakan & konsisten antar tipe) ----------
            if viz_type == "table":
                # tabel: pakai all_columns + metrics opsional
                all_cols = []
                if group_by:
                    all_cols.extend(group_by)
                if enc_x and enc_x not in all_cols:
                    all_cols.append(enc_x)
                form_data.update(
                    {
                        "all_columns": all_cols or (enc_x and [enc_x]) or [],
                        "metrics": metrics if metrics else [],
                        "server_pagination": True,
                    }
                )
                _apply_order(form_data)

            elif viz_type in ("big_number_total", "big_number"):
                single_metric = metrics[0] if metrics else "count"
                form_data.update({"metric": single_metric})

            elif viz_type in ("line_chart", "area_chart", "bar_chart", "mixed_chart"):
                # time-series: butuh granularity (kolom waktu) + metrics
                form_data.update(
                    {
                        "metrics": metrics,
                        "show_legend": show_legend,
                    }
                )
                _apply_order(form_data)

            elif viz_type == "dist_bar":
                # Bar/distribution (kategori, non-time)
                # Dukung 2 mode:
                # - Long-form jika encoding.y
                # & encoding.color ada → groupby [x, color], metric SUM(y)
                # - Wide-form default → groupby dari query, metrics dari query
                is_long_form = bool(enc_x) and bool(enc_y) and bool(enc_color)
                if is_long_form:
                    x_axis = enc_x
                    groupby_cols = [enc_x, enc_color]
                    metric_label = enc_y or "value"
                    metrics = [
                        {
                            "expressionType": "SQL",
                            "label": metric_label,
                            "sqlExpression": f"SUM({enc_y})",
                        }
                    ]
                else:
                    x_axis = enc_x or (group_by[0] if group_by else None)
                    groupby_cols = list(group_by)
                    if x_axis and x_axis not in groupby_cols:
                        groupby_cols = [x_axis] + groupby_cols

                # properti generik dist_bar
                form_data.update(
                    {
                        "x_axis": x_axis,
                        "groupby": groupby_cols,
                        "metrics": metrics,
                        "stack": bool(stack),
                        "seriesType": "bar",
                        "orientation": (
                            "horizontal" if orientation == "horizontal" else "vertical"
                        ),
                        "show_legend": show_legend,
                    }
                )
                if sort_mode == "by_metric" and metrics:
                    form_data["seriesLimitMetric"] = metrics[0]
                _apply_order(form_data)

            elif viz_type == "pie":
                pie_groupby = []
                if enc_color:
                    pie_groupby = [enc_color]
                elif enc_x:
                    pie_groupby = [enc_x]
                elif group_by:
                    pie_groupby = [group_by[0]]
                single_metric = metrics[0] if metrics else "count"
                form_data.update(
                    {
                        "groupby": pie_groupby,
                        "metric": single_metric,
                        "number_format": label_cfg.get("format"),
                        "show_legend": show_legend,
                    }
                )

            elif viz_type == "treemap":
                single_metric = metrics[0] if metrics else "count"
                form_data.update(
                    {
                        "groupby": group_by or ([enc_x] if enc_x else []),
                        "metric": single_metric,
                        "show_labels": bool(label_cfg.get("show_value", False)),
                        "number_format": label_cfg.get("format"),
                        "show_legend": show_legend,
                    }
                )

            elif viz_type == "sunburst":
                single_metric = metrics[0] if metrics else "count"
                # sunburst biasanya butuh hierarki groupby (parent->child)
                form_data.update(
                    {
                        "groupby": group_by or ([enc_x] if enc_x else []),
                        "metric": single_metric,
                        "show_labels": bool(label_cfg.get("show_value", False)),
                    }
                )

            elif viz_type == "heatmap":
                # fallback: gunakan x dan color sebagai dimensi, y sebagai nilai (SUM)
                is_long = bool(enc_x) and bool(enc_color) and bool(enc_y)
                if is_long:
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
                    # jika tak ada encoding lengkap, gunakan group_by dan metric pertama
                    form_data.update(
                        {
                            "groupby": group_by[:2],
                            "metric": metrics[0] if metrics else "count",
                        }
                    )

            elif viz_type == "box_plot":
                single_metric = metrics[0] if metrics else "count"
                columns = [enc_x] if enc_x else (group_by[:1] if group_by else [])
                form_data.update(
                    {
                        "columns": columns,
                        "metric": single_metric,
                        "show_legend": show_legend,
                    }
                )

            elif viz_type == "funnel":
                # funnel: gunakan order group_by sebagai tahapan; metric tunggal
                single_metric = metrics[0] if metrics else "count"
                form_data.update(
                    {
                        "groupby": group_by or ([enc_x] if enc_x else []),
                        "metric": single_metric,
                    }
                )

            elif viz_type == "pivot_table":
                rows = list(enc_pivot.get("rows") or [])
                cols = list(enc_pivot.get("columns") or [])
                pvt_metrics = list(enc_pivot.get("metrics") or [])
                pivot_metrics = pvt_metrics if pvt_metrics else metrics
                form_data.update(
                    {
                        "groupbyRows": rows,
                        "groupbyColumns": cols,
                        "metrics": pivot_metrics,
                        "row_limit": row_limit,
                    }
                )

            elif viz_type == "word_cloud":
                # word cloud: groupby 1 kolom + metric tunggal
                col = enc_x or (group_by[0] if group_by else None)
                single_metric = metrics[0] if metrics else "count"
                form_data.update(
                    {
                        "groupby": [col] if col else [],
                        "metric": single_metric,
                    }
                )

            elif viz_type == "world_map":
                # world_map: butuh kolom geografi + metric
                geo_col = enc_x or (group_by[0] if group_by else None)
                single_metric = metrics[0] if metrics else "count"
                form_data.update(
                    {
                        "entity": geo_col,
                        "metric": single_metric,
                    }
                )

            elif viz_type == "echarts_gauge":
                # gauge: butuh satu metric
                single_metric = metrics[0] if metrics else "count"
                form_data.update({"metric": single_metric})

            elif viz_type == "sankey":
                # sankey: source/target/value — fallback: [x,color] sebagai source/target
                single_metric = metrics[0] if metrics else "count"
                source = enc_x or (group_by[0] if group_by else None)
                target = enc_color or (group_by[1] if len(group_by) > 1 else None)
                form_data.update(
                    {
                        "source": source,
                        "target": target,
                        "metric": single_metric,
                    }
                )

            elif viz_type == "event_flow":
                # event_flow: groupby urutan event + waktu (jika ada)
                form_data.update(
                    {
                        "all_columns": group_by or ([enc_x] if enc_x else []),
                    }
                )

            # Label/axis opsional
            if axis.get("x_label"):
                form_data["x_axis_label"] = axis.get("x_label")
            if axis.get("y_label"):
                form_data["y_axis_label"] = axis.get("y_label")
            if isinstance(axis.get("rotate_x"), int):
                form_data["xAxisLabelRotation"] = axis.get("rotate_x")

            # Hint (tidak dibaca Superset; membantu audit)
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

            # Payload akhir untuk POST /api/v1/chart
            payload_dict = {
                "slice_name": title,
                "viz_type": viz_type,
                "datasource_id": datasource_id,  # bisa "__DATASOURCE_ID__"
                "datasource_type": datasource_type,
                "description": description,
                "cache_timeout": 0,
                "params": json.dumps(form_data, ensure_ascii=False),
            }

            record.payload = json.dumps(payload_dict, ensure_ascii=False, indent=2)

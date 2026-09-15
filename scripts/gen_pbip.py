"""Generate .pbip / TMDL Power BI project files for the 4 portfolio reports.

NEVER opened or validated in Power BI Desktop (see docs/final_release_audit_report.md
for why). The semantic model (tables/relationships/measures) is authored as
completely and correctly as this script's author has confidence in the current
TMDL schema; the Report side is deliberately minimal (pages present, no visuals)
since hand-authoring visual JSON blind is the highest-risk, least-verifiable part.
"""
import json
import os
import uuid

OUT_ROOT = r"H:\Claude\data-analytics-portfolio\powerbi"

PG_TO_TMDL = {
    "text": "string",
    "boolean": "boolean",
    "integer": "int64",
    "bigint": "int64",
    "double precision": "double",
    "numeric": "decimal",
    "date": "dateTime",
    "timestamp with time zone": "dateTime",
}


def guid():
    return str(uuid.uuid4())


def col_tmdl(name, pg_type, format_string=None):
    dtype = PG_TO_TMDL[pg_type]
    lines = [f"\tcolumn {name}", f"\t\tdataType: {dtype}", f"\t\tlineageTag: {guid()}", "\t\tsummarizeBy: none"]
    if format_string:
        lines.append(f"\t\tformatString: {format_string}")
    lines.append(f"\t\tsourceColumn: {name}")
    lines.append("")
    lines.append("\t\tannotation SummarizationSetBy = Automatic")
    return "\n".join(lines)


def measure_tmdl(name, expr, format_string=None):
    lines = [f"\tmeasure '{name}' = {expr}"]
    if format_string:
        lines.append(f"\t\tformatString: {format_string}")
    lines.append(f"\t\tlineageTag: {guid()}")
    return "\n".join(lines)


def table_tmdl(table_name, schema, view, columns, measures):
    """columns: list of (name, pg_type, format_string|None). measures: list of (name, expr, format_string|None)."""
    parts = [f"table {table_name}", f"\tlineageTag: {guid()}", ""]
    for name, pg_type, fmt in columns:
        parts.append(col_tmdl(name, pg_type, fmt))
        parts.append("")
    for name, expr, fmt in measures:
        parts.append(measure_tmdl(name, expr, fmt))
        parts.append("")
    col_list = ", ".join(name for name, _, _ in columns)
    m_alias = f"{schema}_{view}"
    parts.append(f"\tpartition {table_name} = m")
    parts.append("\t\tmode: import")
    parts.append("\t\tsource =")
    parts.append("\t\t\t\tlet")
    parts.append('\t\t\t\t\tSource = PostgreSQL.Database("localhost:5433", "analytics"),')
    parts.append(f'\t\t\t\t\t{m_alias} = Source{{[Schema="{schema}",Item="{view}"]}}[Data]')
    parts.append("\t\t\t\tin")
    parts.append(f"\t\t\t\t\t{m_alias}")
    parts.append("")
    parts.append("\tannotation PBI_ResultType = Table")
    return "\n".join(parts)


def relationship_tmdl(from_table, from_col, to_table, to_col):
    return "\n".join([
        f"relationship {guid()}",
        f"\tfromColumn: {from_table}.{from_col}",
        f"\ttoColumn: {to_table}.{to_col}",
    ])


def platform_json(item_type, display_name):
    return json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": item_type, "displayName": display_name},
        "config": {"version": "2.0", "logicalId": guid()},
    }, indent=2)


def build_project(project_key, display_name, tables, relationships, pages):
    """tables: list of dict(table_name, schema, view, columns, measures).
    relationships: list of (from_table, from_col, to_table, to_col).
    pages: list of page display names (Executive Overview first).
    """
    base = os.path.join(OUT_ROOT, project_key)
    sm_dir = os.path.join(base, f"{display_name}.SemanticModel")
    rpt_dir = os.path.join(base, f"{display_name}.Report")
    os.makedirs(os.path.join(sm_dir, "definition", "tables"), exist_ok=True)
    os.makedirs(os.path.join(sm_dir, "definition", "cultures"), exist_ok=True)
    os.makedirs(os.path.join(rpt_dir, "definition", "pages"), exist_ok=True)

    # .pbip pointer
    pbip = {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{display_name}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }
    with open(os.path.join(base, f"{display_name}.pbip"), "w", encoding="utf-8") as f:
        json.dump(pbip, f, indent=2)

    # SemanticModel/.platform + definition.pbism
    with open(os.path.join(sm_dir, ".platform"), "w", encoding="utf-8") as f:
        f.write(platform_json("SemanticModel", display_name))
    with open(os.path.join(sm_dir, "definition.pbism"), "w", encoding="utf-8") as f:
        json.dump({"version": "4.2", "settings": {}}, f, indent=2)

    # tables
    table_names = [t["table_name"] for t in tables]
    for t in tables:
        tmdl = table_tmdl(t["table_name"], t["schema"], t["view"], t["columns"], t["measures"])
        with open(os.path.join(sm_dir, "definition", "tables", f"{t['table_name']}.tmdl"), "w", encoding="utf-8") as f:
            f.write(tmdl + "\n")

    # model.tmdl
    model_lines = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(table_names)}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
    ]
    for tn in table_names:
        model_lines.append(f"ref table {tn}")
    model_lines.append("")
    model_lines.append("ref cultureInfo en-US")
    with open(os.path.join(sm_dir, "definition", "model.tmdl"), "w", encoding="utf-8") as f:
        f.write("\n".join(model_lines) + "\n")

    # relationships.tmdl
    if relationships:
        rel_blocks = [relationship_tmdl(*r) for r in relationships]
        with open(os.path.join(sm_dir, "definition", "relationships.tmdl"), "w", encoding="utf-8") as f:
            f.write("\n\n".join(rel_blocks) + "\n")

    # cultures/en-US.tmdl
    culture_tmdl = (
        "cultureInfo en-US\n\n"
        "\tlinguisticMetadata =\n"
        '\t\t\t{\n'
        '\t\t\t  "Version": "1.0.0",\n'
        '\t\t\t  "Language": "en-US"\n'
        '\t\t\t}\n'
        "\t\tcontentType: json\n"
    )
    with open(os.path.join(sm_dir, "definition", "cultures", "en-US.tmdl"), "w", encoding="utf-8") as f:
        f.write(culture_tmdl)

    # Report/.platform + definition.pbir
    with open(os.path.join(rpt_dir, ".platform"), "w", encoding="utf-8") as f:
        f.write(platform_json("Report", display_name))
    pbir = {
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{display_name}.SemanticModel"}, "byConnection": None},
    }
    with open(os.path.join(rpt_dir, "definition.pbir"), "w", encoding="utf-8") as f:
        json.dump(pbir, f, indent=2)

    # definition/report.json (minimal)
    report_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
        "layoutOptimization": "None",
    }
    with open(os.path.join(rpt_dir, "definition", "report.json"), "w", encoding="utf-8") as f:
        json.dump(report_json, f, indent=2)

    # pages
    page_ids = [f"page{i}" for i in range(len(pages))]
    pages_json = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesProperties/1.0.0/schema.json",
        "pageOrder": page_ids,
        "activePageName": page_ids[0],
    }
    with open(os.path.join(rpt_dir, "definition", "pages", "pages.json"), "w", encoding="utf-8") as f:
        json.dump(pages_json, f, indent=2)
    for pid, pname in zip(page_ids, pages):
        pdir = os.path.join(rpt_dir, "definition", "pages", pid)
        os.makedirs(pdir, exist_ok=True)
        page_json = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pageProperties/1.0.0/schema.json",
            "name": pid,
            "displayName": pname,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        }
        with open(os.path.join(pdir, "page.json"), "w", encoding="utf-8") as f:
            json.dump(page_json, f, indent=2)

    return sm_dir, rpt_dir


# ---------------------------------------------------------------------------
# Project 1: Climate Risk & Business Impact
# ---------------------------------------------------------------------------
climate_tables = [
    dict(table_name="Locations", schema="climate_risk", view="powerbi_summary",
         columns=[
             ("location_id", "text", None), ("name", "text", None), ("lat", "double precision", None),
             ("lon", "double precision", None), ("industry", "text", None),
             ("annual_revenue_usd", "numeric", '"\\$"#,0'), ("asset_value_usd", "numeric", '"\\$"#,0'),
             ("is_synthetic_business_data", "boolean", None), ("latest_year", "integer", "0"),
             ("latest_risk_score", "double precision", "0.0"), ("extreme_heat_days", "integer", "0"),
             ("heavy_precip_days", "integer", "0"), ("temp_anomaly_c", "double precision", "0.0"),
             ("moderate_scenario_impact_usd", "numeric", '"\\$"#,0'),
         ],
         measures=[
             ("Total Business Exposure", "SUM(Locations[asset_value_usd])", '"\\$"#,0'),
             ("Avg Risk Score", "AVERAGE(Locations[latest_risk_score])", "0.0"),
             ("High Risk Location Count", "COUNTROWS(FILTER(Locations, Locations[latest_risk_score] >= 60))", "0"),
         ]),
    dict(table_name="ClimateTrends", schema="climate_risk", view="powerbi_trends",
         columns=[
             ("location_id", "text", None), ("month", "date", "yyyy-mm"),
             ("avg_temp_max_c", "double precision", "0.0"), ("avg_temp_min_c", "double precision", "0.0"),
             ("total_precipitation_mm", "double precision", "0.0"), ("max_windspeed_kmh", "double precision", "0.0"),
         ],
         measures=[
             ("Avg Temp Max (C)", "AVERAGE(ClimateTrends[avg_temp_max_c])", "0.0"),
             ("Avg Temp Min (C)", "AVERAGE(ClimateTrends[avg_temp_min_c])", "0.0"),
             ("Total Precipitation (mm)", "SUM(ClimateTrends[total_precipitation_mm])", "0.0"),
             ("Avg Wind Speed (km/h)", "AVERAGE(ClimateTrends[max_windspeed_kmh])", "0.0"),
         ]),
    dict(table_name="FinancialImpact", schema="climate_risk", view="powerbi_financial_impact",
         columns=[
             ("location_id", "text", None), ("name", "text", None), ("industry", "text", None),
             ("year", "integer", "0"), ("scenario", "text", None),
             ("estimated_impact_usd", "numeric", '"\\$"#,0'), ("pct_of_asset_value", "double precision", "0.0000"),
         ],
         measures=[
             ("Total Estimated Impact", "SUM(FinancialImpact[estimated_impact_usd])", '"\\$"#,0'),
         ]),
]
climate_rels = [
    ("ClimateTrends", "location_id", "Locations", "location_id"),
    ("FinancialImpact", "location_id", "Locations", "location_id"),
]
climate_pages = ["Executive Overview", "Climate Trends", "Risk & Business Impact", "Detailed Analysis"]
build_project("01_climate_risk_business_impact", "ClimateRisk", climate_tables, climate_rels, climate_pages)

# ---------------------------------------------------------------------------
# Project 2: Dark Store Intelligence
# ---------------------------------------------------------------------------
darkstore_tables = [
    dict(table_name="Stores", schema="dark_store", view="stores",
         columns=[
             ("store_id", "text", None), ("name", "text", None), ("region", "text", None),
             ("country", "text", None), ("lat", "double precision", None), ("lon", "double precision", None),
             ("sqft", "integer", "#,0"), ("opening_date", "date", "yyyy-mm-dd"), ("is_synthetic", "boolean", None),
         ],
         measures=[]),
    dict(table_name="SalesSummary", schema="dark_store", view="powerbi_sales_summary",
         columns=[
             ("store_id", "text", None), ("store_name", "text", None), ("region", "text", None),
             ("country", "text", None), ("metric_date", "date", "yyyy-mm-dd"),
             ("revenue", "numeric", '"\\$"#,0'), ("orders_count", "integer", "#,0"),
             ("units_sold", "integer", "#,0"), ("avg_order_value", "numeric", '"\\$"#,0.00'),
         ],
         measures=[
             ("Total Revenue", "SUM(SalesSummary[revenue])", '"\\$"#,0'),
             ("Total Orders", "SUM(SalesSummary[orders_count])", "#,0"),
             ("Avg Order Value", "DIVIDE([Total Revenue], [Total Orders])", '"\\$"#,0.00'),
         ]),
    dict(table_name="InventorySummary", schema="dark_store", view="powerbi_inventory_summary",
         columns=[
             ("store_id", "text", None), ("store_name", "text", None), ("stock_code", "text", None),
             ("description", "text", None), ("avg_daily_demand", "double precision", "0.0"),
             ("avg_stock_on_hand", "double precision", "0.0"), ("days_of_supply", "double precision", "0.0"),
             ("stockout_days", "integer", "0"), ("turnover_ratio", "double precision", "0.00"),
         ],
         measures=[
             ("Avg Turnover Ratio", "AVERAGE(InventorySummary[turnover_ratio])", "0.00"),
             ("Total Stockout Days", "SUM(InventorySummary[stockout_days])", "#,0"),
             ("Avg Days of Supply", "AVERAGE(InventorySummary[days_of_supply])", "0.0"),
         ]),
    dict(table_name="StorePerformance", schema="dark_store", view="powerbi_store_performance",
         columns=[
             ("store_id", "text", None), ("store_name", "text", None), ("region", "text", None),
             ("country", "text", None), ("sqft", "integer", "#,0"), ("month", "date", "yyyy-mm"),
             ("revenue", "numeric", '"\\$"#,0'), ("cogs_estimate", "numeric", '"\\$"#,0'),
             ("opex_estimate", "numeric", '"\\$"#,0'), ("profit_estimate", "numeric", '"\\$"#,0'),
             ("roi_pct", "double precision", '0.0"%"'),
         ],
         measures=[
             ("Total Profit (Est.)", "SUM(StorePerformance[profit_estimate])", '"\\$"#,0'),
             ("Avg ROI %", "AVERAGE(StorePerformance[roi_pct])", '0.0"%"'),
         ]),
]
darkstore_rels = [
    ("SalesSummary", "store_id", "Stores", "store_id"),
    ("InventorySummary", "store_id", "Stores", "store_id"),
    ("StorePerformance", "store_id", "Stores", "store_id"),
]
darkstore_pages = ["Executive Overview", "Sales Performance", "Product & Inventory Intelligence", "Store Performance"]
build_project("02_dark_store_intelligence", "DarkStoreIntelligence", darkstore_tables, darkstore_rels, darkstore_pages)

# ---------------------------------------------------------------------------
# Project 3: AI Hiring Bias Detector
# ---------------------------------------------------------------------------
hiring_tables = [
    dict(table_name="FunnelSummary", schema="hiring_bias", view="powerbi_funnel_summary",
         columns=[
             ("role_family", "text", None), ("total_applications", "bigint", "#,0"),
             ("reached_screen", "bigint", "#,0"), ("reached_interview", "bigint", "#,0"),
             ("reached_offer", "bigint", "#,0"), ("reached_hire", "bigint", "#,0"),
         ],
         measures=[
             ("Total Applications", "SUM(FunnelSummary[total_applications])", "#,0"),
             ("Total Screened", "SUM(FunnelSummary[reached_screen])", "#,0"),
             ("Total Interviewed", "SUM(FunnelSummary[reached_interview])", "#,0"),
             ("Total Offered", "SUM(FunnelSummary[reached_offer])", "#,0"),
             ("Total Hired", "SUM(FunnelSummary[reached_hire])", "#,0"),
             ("Screen Rate", "DIVIDE([Total Screened], [Total Applications])", "0.00%"),
             ("Interview Rate", "DIVIDE([Total Interviewed], [Total Screened])", "0.00%"),
             ("Offer Rate", "DIVIDE([Total Offered], [Total Interviewed])", "0.00%"),
             ("Hire Rate", "DIVIDE([Total Hired], [Total Offered])", "0.00%"),
             ("Overall Selection Rate", "DIVIDE([Total Hired], [Total Applications])", "0.00%"),
         ]),
    dict(table_name="FairnessSummary", schema="hiring_bias", view="powerbi_fairness_summary",
         columns=[
             ("group_attribute", "text", None), ("group_value", "text", None), ("stage", "text", None),
             ("total_at_risk", "integer", "#,0"), ("passed", "integer", "#,0"),
             ("selection_rate", "double precision", "0.00%"), ("reference_group", "text", None),
             ("reference_selection_rate", "double precision", "0.00%"),
             ("adverse_impact_ratio", "double precision", "0.000"),
             ("computed_at", "timestamp with time zone", "yyyy-mm-dd hh:mm:ss"),
         ],
         measures=[]),
    dict(table_name="GroupComparison", schema="hiring_bias", view="powerbi_group_comparison",
         columns=[
             ("group_attribute", "text", None), ("group_value", "text", None), ("stage", "text", None),
             ("total_at_risk", "integer", "#,0"), ("passed", "integer", "#,0"),
             ("selection_rate", "double precision", "0.00%"), ("reference_group", "text", None),
             ("reference_selection_rate", "double precision", "0.00%"),
             ("adverse_impact_ratio", "double precision", "0.000"),
             ("rate_difference", "double precision", "0.00%"), ("fails_four_fifths_rule", "boolean", None),
         ],
         measures=[
             ("Groups Failing 4/5ths Rule",
              "CALCULATE(DISTINCTCOUNT(GroupComparison[group_value]), GroupComparison[fails_four_fifths_rule] = TRUE)",
              "0"),
         ]),
]
hiring_pages = ["Executive Overview", "Recruitment Funnel", "Fairness & Group Comparison", "Model & Decision Analysis"]
build_project("03_ai_hiring_bias_detector", "HiringBiasDetector", hiring_tables, [], hiring_pages)

# ---------------------------------------------------------------------------
# Project 4: Fraud Pattern Evolution Tracker
# ---------------------------------------------------------------------------
fraud_tables = [
    dict(table_name="RiskSummary", schema="fraud_pattern", view="powerbi_risk_summary",
         columns=[
             ("total_transactions", "bigint", "#,0"), ("flagged_transactions", "bigint", "#,0"),
             ("true_fraud_transactions", "bigint", "#,0"), ("true_fraud_amount", "numeric", '"\\$"#,0'),
             ("true_fraud_rate", "numeric", "0.00%"), ("model_name", "text", None),
             ("precision", "double precision", "0.00%"), ("recall", "double precision", "0.00%"),
             ("f1", "double precision", "0.000"), ("roc_auc", "double precision", "0.000"),
             ("threshold", "double precision", "0.00"),
         ],
         measures=[
             ("Total Transactions", "SUM(RiskSummary[total_transactions])", "#,0"),
             ("Flagged Transactions", "SUM(RiskSummary[flagged_transactions])", "#,0"),
             ("True Fraud Transactions", "SUM(RiskSummary[true_fraud_transactions])", "#,0"),
             ("True Fraud Rate", "AVERAGE(RiskSummary[true_fraud_rate])", "0.00%"),
             ("Model Precision", "AVERAGE(RiskSummary[precision])", "0.00%"),
             ("Model Recall", "AVERAGE(RiskSummary[recall])", "0.00%"),
             ("Model ROC AUC", "AVERAGE(RiskSummary[roc_auc])", "0.000"),
         ]),
    dict(table_name="Trends", schema="fraud_pattern", view="powerbi_trends",
         columns=[
             ("month", "date", "yyyy-mm"), ("total_transactions", "integer", "#,0"),
             ("fraud_transactions", "integer", "#,0"), ("fraud_rate", "double precision", "0.00%"),
             ("total_amount", "numeric", '"\\$"#,0'), ("fraud_amount", "numeric", '"\\$"#,0'),
         ],
         measures=[]),
    dict(table_name="NetworkSummary", schema="fraud_pattern", view="powerbi_network_summary",
         columns=[
             ("account_id", "text", None), ("account_type", "text", None), ("home_country", "text", None),
             ("is_fraud_ring_member", "boolean", None), ("ring_id", "text", None),
             ("component_id", "integer", "0"), ("component_size", "integer", "0"),
             ("degree", "integer", "0"), ("is_ring_candidate", "boolean", None),
         ],
         measures=[
             ("Ring Candidate Accounts",
              "CALCULATE(DISTINCTCOUNT(NetworkSummary[account_id]), NetworkSummary[is_ring_candidate] = TRUE)", "#,0"),
             ("Avg Cluster Size", "AVERAGE(NetworkSummary[component_size])", "0.0"),
         ]),
]
fraud_pages = ["Executive Overview", "Fraud Trends", "Detection Performance", "Pattern & Network Analysis"]
build_project("04_fraud_pattern_evolution", "FraudPatternEvolution", fraud_tables, [], fraud_pages)

print("Generated all 4 .pbip projects under", OUT_ROOT)

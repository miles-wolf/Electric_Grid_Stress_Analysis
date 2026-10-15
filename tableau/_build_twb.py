"""Generate a starter Tableau workbook (.twb) for the Grid Stress dashboard port.

Scope (reliable, low-risk): 7 text-file data connections + 3 parameters +
all calculated fields on the daily_stress source. No viz layout (build per BUILD-GUIDE.md).
Run:  .venv/Scripts/python.exe tableau/_build_twb.py
"""
import csv, os, xml.etree.ElementTree as ET
from xml.dom import minidom

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
VERSION = "18.1"

# --- CSVs to wire up: (caption, filename) ---
SOURCES = [
    ("daily_stress", "daily_stress.csv"),
    ("top_days", "top_days.csv"),
    ("page3_data", "page3_data.csv"),
    ("hourly_peak_days", "hourly_peak_days.csv"),
    ("k_selection", "k_selection_summary.csv"),
    ("cluster_centroids", "cluster_centroids.csv"),
    ("baseline_stats", "baseline_stats.csv"),
]

# columns that are numeric measures (everything else -> dimension/string)
MEASURE_HINTS = {
    "daily_peak_mw","daily_min_mw","daily_max_ramp_mw","daily_ramp_std","daily_energy_mwh",
    "daily_range_mw","z_daily_peak_mw","z_daily_max_ramp_mw","stress_z","stress_01",
    "value","silhouette","davies_bouldin","n_days","mean_onset_days","median_onset_days",
    "relative_day","mean_z_peak","mean_z_ramp","mean_stress_z","std_stress_z",
    "centroid_z_peak","centroid_z_ramp","mean","std","stress_01_x",
    "n_events_onset","n_events_composite","season_pct","silhouette_score",
    "centroid_z_peak","centroid_z_ramp","n_training_days","k_clusters","rank",
    "hours_observed","hour","cluster",
}

# Calculated fields for daily_stress: (caption, formula)
CALCS = [
    ("Stress_Z (Max)", "MAX([stress_z])"),
    ("Stress_01 (Avg)", "AVG([stress_01])"),
    ("Most Stressed Day",
     "{ FIXED [balancing_authority] : MAX( IF [stress_z] = "
     "{ FIXED [balancing_authority] : MAX([stress_z]) } THEN [date] END ) }"),
    ("High Stress Days", "SUM( IF [stress_01] > 0.7 THEN 1 ELSE 0 END )"),
    ("Is High Stress", "IF [stress_01] > 0.7 THEN 1 ELSE 0 END"),
    ("High Stress Days (30d)", "WINDOW_SUM( SUM([Is High Stress]), -29, 0 )"),
    # calculator baselines
    ("Peak Mean", 'IF [Calc BA] = "CISO" THEN 29561.6932 ELSE 109157.4548 END'),
    ("Peak Std", 'IF [Calc BA] = "CISO" THEN 4312.5014 ELSE 17697.646 END'),
    ("Ramp Mean", 'IF [Calc BA] = "CISO" THEN 2383.2767 ELSE 5749.3616 END'),
    ("Ramp Std", 'IF [Calc BA] = "CISO" THEN 635.3495 ELSE 1360.4761 END'),
    ("Input Z Peak", "([Peak MW Input] - [Peak Mean]) / [Peak Std]"),
    ("Input Z Ramp", "([Max Ramp MW Input] - [Ramp Mean]) / [Ramp Std]"),
    ("Input Stress Z", "[Input Z Peak] + [Input Z Ramp]"),
    ("cP_Stable", 'IF [Calc BA]="CISO" THEN -0.6457 ELSE -0.8337 END'),
    ("cP_Moderate", 'IF [Calc BA]="CISO" THEN -0.3120 ELSE -0.6521 END'),
    ("cP_Elevated", 'IF [Calc BA]="CISO" THEN 1.0891 ELSE 0.3664 END'),
    ("cP_Extreme", 'IF [Calc BA]="CISO" THEN 2.0691 ELSE 1.5823 END'),
    ("cR_Stable", 'IF [Calc BA]="CISO" THEN -0.8300 ELSE -1.3496 END'),
    ("cR_Moderate", 'IF [Calc BA]="CISO" THEN 0.4164 ELSE 0.4510 END'),
    ("cR_Elevated", 'IF [Calc BA]="CISO" THEN 0.3345 ELSE -0.0852 END'),
    ("cR_Extreme", 'IF [Calc BA]="CISO" THEN 2.0651 ELSE 1.1240 END'),
    ("d_Stable", "SQRT( POWER([Input Z Peak]-[cP_Stable],2) + POWER([Input Z Ramp]-[cR_Stable],2) )"),
    ("d_Moderate", "SQRT( POWER([Input Z Peak]-[cP_Moderate],2) + POWER([Input Z Ramp]-[cR_Moderate],2) )"),
    ("d_Elevated", "SQRT( POWER([Input Z Peak]-[cP_Elevated],2) + POWER([Input Z Ramp]-[cR_Elevated],2) )"),
    ("d_Extreme", "SQRT( POWER([Input Z Peak]-[cP_Extreme],2) + POWER([Input Z Ramp]-[cR_Extreme],2) )"),
    ("Identified Cluster",
     'IF [d_Stable] <= [d_Moderate] AND [d_Stable] <= [d_Elevated] AND [d_Stable] <= [d_Extreme] THEN "Stable" '
     'ELSEIF [d_Moderate] <= [d_Elevated] AND [d_Moderate] <= [d_Extreme] THEN "Moderate" '
     'ELSEIF [d_Elevated] <= [d_Extreme] THEN "Elevated" ELSE "Extreme" END'),
    ("Cluster Mean Stress Z",
     'CASE [Identified Cluster] '
     'WHEN "Stable" THEN IF [Calc BA]="CISO" THEN -1.4756 ELSE -2.1833 END '
     'WHEN "Moderate" THEN IF [Calc BA]="CISO" THEN 0.1044 ELSE -0.2011 END '
     'WHEN "Elevated" THEN IF [Calc BA]="CISO" THEN 1.4236 ELSE 0.2812 END '
     'WHEN "Extreme" THEN IF [Calc BA]="CISO" THEN 4.1342 ELSE 2.7064 END END'),
    ("Stress Percentile",
     "{ FIXED [balancing_authority] : SUM(IF [stress_z] <= [Input Stress Z] THEN 1 ELSE 0 END) } "
     "/ { FIXED [balancing_authority] : COUNT([date]) }"),
    ("BA = Calc BA", "[balancing_authority] = [Calc BA]"),
]

def datatype_for(col):
    if col == "date":
        return "date"
    if col in MEASURE_HINTS:
        return "real"
    return "string"

def col_meta(col):
    dt = datatype_for(col)
    if dt == "date":
        return "date", "dimension", "ordinal"
    if dt == "real":
        return "real", "measure", "quantitative"
    return "string", "dimension", "nominal"

def make_textscan_datasource(caption, filename):
    header = next(csv.reader(open(os.path.join(DATA, filename), encoding="utf-8-sig")))
    dsname = "federated." + caption
    conn_name = "textscan." + caption
    tablename = "[%s#csv]" % filename.replace(".csv", "")
    ds = ET.Element("datasource", {"caption": caption, "inline": "true",
                                   "name": dsname, "version": VERSION})
    conn = ET.SubElement(ds, "connection", {"class": "federated"})
    ncs = ET.SubElement(conn, "named-connections")
    nc = ET.SubElement(ncs, "named-connection", {"caption": caption, "name": conn_name})
    ET.SubElement(nc, "connection", {
        "class": "textscan", "directory": DATA, "filename": filename,
        "header": "yes", "locale": "en_US", "separator": ","})
    ET.SubElement(conn, "relation", {
        "connection": conn_name, "name": filename, "table": tablename, "type": "table"})
    # column metadata + calculated fields
    for col in header:
        dt, role, typ = col_meta(col)
        ET.SubElement(ds, "column", {
            "datatype": dt, "name": "[%s]" % col, "role": role, "type": typ})
    if caption == "daily_stress":
        for cap, formula in CALCS:
            dt = "string" if cap in ("Identified Cluster", "BA = Calc BA") else "real"
            if cap == "Most Stressed Day":
                dt = "date"
            if cap == "BA = Calc BA":
                dt = "boolean"
            role = "dimension" if dt in ("string", "boolean", "date") else "measure"
            typ = "nominal" if dt in ("string", "boolean") else ("ordinal" if dt == "date" else "quantitative")
            c = ET.SubElement(ds, "column", {
                "caption": cap, "datatype": dt,
                "name": "[%s]" % cap, "role": role, "type": typ})
            ET.SubElement(c, "calculation", {"class": "tableau", "formula": formula})
    return ds

def make_parameters():
    ds = ET.Element("datasource", {"hasconnection": "false", "inline": "true", "name": "Parameters"})
    ET.SubElement(ds, "aliases", {"enabled": "yes"})
    def param(cap, dt, value, domain, members=None, rng=None):
        col = ET.SubElement(ds, "column", {
            "caption": cap, "datatype": dt, "name": "[%s]" % cap,
            "param-domain-type": domain, "role": "measure" if dt == "real" else "dimension",
            "type": "quantitative" if dt == "real" else "nominal", "value": value})
        ET.SubElement(col, "calculation", {"class": "tableau", "formula": value})
        if domain == "list" and members:
            mem = ET.SubElement(col, "members")
            for m in members:
                ET.SubElement(mem, "member", {"value": '"%s"' % m})
        if domain == "range" and rng:
            ET.SubElement(col, "range", rng)
    param("Peak MW Input", "real", "40000", "range",
          rng={"granularity": "1", "max": "200000", "min": "0"})
    param("Max Ramp MW Input", "real", "3000", "range",
          rng={"granularity": "1", "max": "12000", "min": "0"})
    param("Calc BA", "string", '"CISO"', "list", members=["CISO", "PJM"])
    return ds

def main():
    wb = ET.Element("workbook", {"version": VERSION})
    ET.SubElement(wb, "preferences")
    dss = ET.SubElement(wb, "datasources")
    dss.append(make_parameters())
    for cap, fn in SOURCES:
        dss.append(make_textscan_datasource(cap, fn))
    # minimal empty worksheet so the workbook opens to a usable sheet
    wss = ET.SubElement(wb, "worksheets")
    ws = ET.SubElement(wss, "worksheet", {"name": "Start Here"})
    tbl = ET.SubElement(ws, "table")
    vw = ET.SubElement(tbl, "view")
    ET.SubElement(vw, "datasources")
    ET.SubElement(tbl, "panes")
    ET.SubElement(tbl, "rows")
    ET.SubElement(tbl, "cols")
    wins = ET.SubElement(wb, "windows", {"source-height": "30"})
    ET.SubElement(wins, "window", {"class": "worksheet", "name": "Start Here"})

    xmlstr = minidom.parseString(ET.tostring(wb, "utf-8")).toprettyxml(indent="  ")
    # inject the Tableau user namespace onto the workbook root
    xmlstr = xmlstr.replace(
        '<workbook version="%s">' % VERSION,
        "<workbook version='%s' xmlns:user='http://www.tableausoftware.com/xml/user'>" % VERSION)
    out = os.path.join(HERE, "Grid-Stress-Analysis.twb")
    with open(out, "w", encoding="utf-8") as f:
        f.write(xmlstr)
    # validate well-formedness
    ET.parse(out)
    print("WROTE", out, "(%d bytes)" % os.path.getsize(out))
    print("XML well-formed: OK")
    print("datasources:", len(SOURCES) + 1, " calc fields on daily_stress:", len(CALCS))

if __name__ == "__main__":
    main()

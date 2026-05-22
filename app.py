import streamlit as st
import pandas as pd
import tempfile
import os
from typing import Dict
import json
import html
import time
from io import BytesIO

# Sample data
from sample_data import get_sample_project, PROJECT_META, SAMPLE_DISCIPLINE_COLORS

# Default colors — now includes Finitions and VRD
DEFAULT_DISCIPLINE_COLORS = {
    "Préliminaires": "#FF6B6B",
    "Terrassement":  "#4ECDC4",
    "Fondations":    "#45B7D1",
    "GrosOeuvres":   "#96CEB4",
    "SecondOeuvres": "#FECA57",
    "Finitions":     "#E17055",
    "VRD":           "#A29BFE",
    "default":       "#BDC3C7",
}


def _validate_required_columns(df: pd.DataFrame, required: set, name: str = "DataFrame") -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name} missing required columns: {sorted(list(missing))}")


def _convert_schedule_dates(df: pd.DataFrame, start_col: str = "Start", end_col: str = "End") -> pd.DataFrame:
    df = df.copy()
    if start_col not in df.columns or end_col not in df.columns:
        if "Finish" in df.columns and end_col not in df.columns:
            end_col = "Finish"
    df["Start"] = pd.to_datetime(df[start_col], errors="coerce")
    df["End"]   = pd.to_datetime(df[end_col],   errors="coerce")
    if df["Start"].isna().any() or df["End"].isna().any():
        raise ValueError("Some Start or End values could not be parsed to datetime in schedule.")
    return df


def generate_interactive_gantt(
    schedule_df: pd.DataFrame,
    output_path: str,
    discipline_colors: Dict[str, str] = None,
) -> str:
    """Generate interactive Gantt chart HTML file."""
    if discipline_colors is None:
        discipline_colors = DEFAULT_DISCIPLINE_COLORS

    required = {"TaskID", "Discipline", "Start", "End"}
    _validate_required_columns(schedule_df, required, "schedule_df")

    df = _convert_schedule_dates(schedule_df).copy()
    df["TaskID"]       = df["TaskID"].astype(str)
    df["TaskName"]     = df.get("TaskName", df["TaskID"])
    df["TaskID_Legend"] = df["TaskID"].apply(lambda x: x.split("-")[0])
    df["TaskZone"]     = df.get("Zone", df["TaskID"].apply(lambda x: x.split("-")[-1] if "-" in x else ""))

    df["DisplayName"] = df.apply(
        lambda r: f"{r['TaskName']} {'-'.join(r['TaskID'].split('-')[1:]) if '-' in r['TaskID'] else r['TaskID']}",
        axis=1,
    )
    df = df.sort_values(["Start", "Discipline", "TaskZone", "TaskID_Legend"])
    df["DurationDays"] = (df["End"] - df["Start"]).dt.total_seconds() / (3600 * 24)

    # Color mapping
    unique_disc = df["Discipline"].astype(str).unique().tolist()
    import plotly.express as px
    fallback_colors = px.colors.qualitative.Plotly

    color_discrete_map = {}
    for i, d in enumerate(unique_disc):
        if d in discipline_colors:
            color_discrete_map[d] = discipline_colors[d]
        elif d in DEFAULT_DISCIPLINE_COLORS:
            color_discrete_map[d] = DEFAULT_DISCIPLINE_COLORS[d]
        else:
            color_discrete_map[d] = fallback_colors[i % len(fallback_colors)]

    traces_data = []
    trace_meta  = []
    all_tasks_data = []

    for _, row in df.iterrows():
        discipline   = str(row["Discipline"])
        zone         = str(row["TaskZone"])
        task_id      = str(row["TaskID"])
        task_name    = str(row["TaskName"])
        display_name = str(row["DisplayName"])
        start_date   = row["Start"].strftime("%Y-%m-%d")
        end_date     = row["End"].strftime("%Y-%m-%d")
        duration     = float(row["DurationDays"])
        color        = str(color_discrete_map.get(discipline, "blue"))

        end_dt = end_date
        if end_dt == start_date:
            end_dt = (pd.to_datetime(end_dt) + pd.Timedelta(days=0.3)).strftime("%Y-%m-%d %H:%M:%S")

        trace = {
            "x": [start_date, end_dt],
            "y": [display_name, display_name],
            "mode": "lines",
            "line": {"color": color, "width": 8},
            "name": f"{discipline} | {zone}" if zone else discipline,
            "hovertemplate": (
                f"<b>{html.escape(task_name)}</b><br>"
                f"ID: {html.escape(task_id)}<br>"
                f"Start: {start_date}<br>"
                f"End: {end_date}<br>"
                f"Duration: {duration:.1f} days<extra></extra>"
            ),
            "showlegend": False,
        }
        traces_data.append(trace)

        trace_meta.append({
            "trace_index": len(traces_data) - 1,
            "discipline":  discipline,
            "zone":        zone,
            "task_id":     task_id,
            "display_name": display_name,
            "task_name":   task_name,
            "selected":    True,
        })

        all_tasks_data.append({
            "TaskID":      task_id,
            "TaskName":    task_name,
            "DisplayName": display_name,
            "Discipline":  discipline,
            "Zone":        zone,
        })

    layout_data = {
        "title": {
            "text": "Interactive Project Schedule Gantt",
            "x": 0.5,
            "xanchor": "center",
            "y": 0.99,
            "yref": "paper",
            "font": {"size": 24, "family": "Arial Black, sans-serif", "color": "black"},
        },
        "height": max(600, len(df) * 25),
        "margin": {"l": 300, "r": 40, "t": 10, "b": 150},
        "xaxis": {
            "title": "Date",
            "type": "date",
            "rangeselector": {
                "buttons": [
                    {"count": 1,  "label": "1m",  "step": "month", "stepmode": "backward"},
                    {"count": 6,  "label": "6m",  "step": "month", "stepmode": "backward"},
                    {"count": 14, "label": "14m", "step": "month", "stepmode": "backward"},
                    {"count": 30, "label": "30m", "step": "month", "stepmode": "backward"},
                    {"step": "all", "label": "Fit"},
                ],
                "y": 0.98,
            },
            "showgrid":      True,
            "gridcolor":     "grey",
            "griddash":      "solid",
            "gridwidth":     1,
            "tickformat":    "%Y-%m-%d",
            "showticklabels": True,
            "tickangle":     -45,
            "tickmode":      "auto",
            "automargin":    True,
            "ticklabelmode": "period",
        },
        "yaxis": {
            "title":     "Tasks",
            "autorange": True,
            "showgrid":  True,
            "gridcolor": "lightgrey",
            "gridwidth": 1,
            "domain":    [0, 0.97],
        },
    }

    traces_data_json = json.dumps(traces_data)
    layout_data_json = json.dumps(layout_data)
    trace_meta_json  = json.dumps(trace_meta)
    all_tasks_json   = json.dumps(all_tasks_data)

    disciplines = sorted(df["Discipline"].astype(str).unique().tolist())
    zones       = sorted([z for z in df["TaskZone"].astype(str).unique().tolist() if z])

    html_content = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>Interactive Gantt - Split PNG</title>
<style>
body {{ font-family: Arial; margin:12px; }}
.controls {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:12px; align-items:center; }}
.plot-container {{ width:100vw; height:600px; overflow:auto; border:1px solid #ddd; border-radius:4px; }}
.task-legend-table {{ border-collapse: collapse; width: 100%; font-size:12px; max-height:400px; overflow:auto; display:block; }}
.task-legend-table th, .task-legend-table td {{ border:1px solid #ddd; padding:6px; text-align:left; }}
.task-legend-table th {{ background:#f4f4f4; position: sticky; top:0; z-index: 10; }}
.task-row {{ cursor:pointer; }}
.task-row:hover {{ background-color:#f0f8ff; }}
.task-row.selected {{ background-color:#e6f3ff; }}
.task-checkbox {{ margin:0; cursor:pointer; }}
.legend-panel {{ max-height:450px; overflow:auto; border:1px solid #eee; padding:8px; background:#fff; }}
.collapsible {{ cursor:pointer; padding:8px; background:#f7f7f7; border:1px solid #e8e8e8; margin-bottom:6px; border-radius:4px; }}
.small {{ font-size:12px; color:#555; }}
.btn {{ padding:6px 8px; border-radius:4px; border:1px solid #ccc; background:#fff; cursor:pointer; }}
.btn-primary {{ background:#007bff; color:white; border-color:#007bff; }}
input[type=text], input[type=number] {{ padding:6px; border:1px solid #ccc; border-radius:4px; width:60px; }}
.selection-controls {{ display:flex; gap:8px; margin:8px 0; flex-wrap:wrap; }}
</style>
</head>
<body>
<h2>Interactive Project Schedule</h2>
<div class="controls">
<div><label class="small">Discipline:</label>
<select id="discipline-filter" class="btn">
<option value="__all__">All</option>
{''.join(f'<option value="{html.escape(str(d))}">{html.escape(str(d))}</option>' for d in disciplines)}
</select></div>
<div><label class="small">Zone:</label>
<select id="zone-filter" class="btn">
<option value="__all__">All</option>
{''.join(f'<option value="{html.escape(str(z))}">{html.escape(str(z))}</option>' for z in zones)}
</select></div>
<div><label class="small">Jump to Task:</label>
<input id="jump-input" type="text" placeholder="e.g. 1.1_F0_A"/>
<button id="jump-btn" class="btn">Go</button></div>
<div>
<button id="toggle-legend" class="btn">Toggle Legend</button>
<button id="fit-btn" class="btn">Fit Timeline</button>
<button id="reset-view" class="btn">Reset View</button>
</div>
<div>
<label class="small">Tasks per PNG:</label><input id="tasks-per-section" type="number" value="50" min="1"/>
<button id="split-download" class="btn">Split & Download PNGs</button>
</div>
</div>

<div class="plot-container"><div id="plot" style="width:100%; height:100%;"></div></div>

<div style="margin-top:12px;">
<div class="collapsible" id="legend-toggle-header">📋 Task Selection (click to expand/collapse)</div>
<div class="legend-panel" id="legend-panel">
<div class="selection-controls">
<button id="select-all" class="btn">Select All</button>
<button id="deselect-all" class="btn">Deselect All</button>
<button id="apply-selection" class="btn btn-primary">Apply Selection</button>
<span id="selection-count" class="small" style="margin-left:auto;">{len(df)} tasks selected</span>
</div>
<table id="task-legend" class="task-legend-table">
<thead><tr><th>Show</th><th>Task ID</th><th>Task Name</th><th>Discipline</th><th>Zone</th></tr></thead>
<tbody>
{''.join(
    f'<tr class="task-row" data-task-id="{html.escape(str(r["TaskID"]))}" data-selected="true">'
    f'<td><input type="checkbox" class="task-checkbox" checked data-task-id="{html.escape(str(r["TaskID"]))}"></td>'
    f'<td>{html.escape(str(r["TaskID_Legend"]))}</td>'
    f'<td>{html.escape(str(r["TaskName"]))}</td>'
    f'<td>{html.escape(str(r["Discipline"]))}</td>'
    f'<td>{html.escape(str(r["TaskZone"]))}</td></tr>'
    for _, r in df.iterrows()
)}
</tbody>
</table>
</div>
</div>

<script src="https://cdn.plot.ly/plotly-2.24.1.min.js"></script>
<script>
const traceMeta={trace_meta_json};
const allTasks={all_tasks_json};
const allTracesData={traces_data_json};
const plotLayout={layout_data_json};

let selectedTasks = new Set(allTasks.map(t=>t.TaskID));
let currentVisibleTasks = new Set(selectedTasks);

function updateDateTicksAndGrid() {{
    if (!window.plotDiv) return;
    const visibleDates = [];
    allTracesData.forEach((trace, index) => {{
        if (trace.visible !== false) {{
            visibleDates.push(new Date(trace.x[0]), new Date(trace.x[1]));
        }}
    }});
    if (visibleDates.length === 0) return;
    const minDate = new Date(Math.min(...visibleDates));
    const maxDate = new Date(Math.max(...visibleDates));
    const timeRangeDays = (maxDate - minDate) / (1000 * 60 * 60 * 24);
    let tickIntervalMs, tickFormat;
    if (timeRangeDays <= 7)        {{ tickIntervalMs = 86400000;        tickFormat = '%b %d'; }}
    else if (timeRangeDays <= 30)  {{ tickIntervalMs = 86400000 * 7;    tickFormat = '%b %d'; }}
    else if (timeRangeDays <= 90)  {{ tickIntervalMs = 86400000 * 14;   tickFormat = '%b %d, %Y'; }}
    else if (timeRangeDays <= 180) {{ tickIntervalMs = 86400000 * 30;   tickFormat = '%b %Y'; }}
    else                           {{ tickIntervalMs = 86400000 * 91;   tickFormat = '%b %Y'; }}
    const firstTick = new Date(minDate);
    if (tickIntervalMs === 86400000 * 7) {{
        const dow = firstTick.getDay();
        firstTick.setDate(firstTick.getDate() - (dow === 0 ? 6 : dow - 1));
    }} else if (tickIntervalMs === 86400000 * 30) {{
        firstTick.setDate(1);
    }}
    const numTicks = Math.ceil((maxDate - firstTick) / tickIntervalMs) + 1;
    const tickvals = [];
    for (let i = 0; i < numTicks; i++) {{
        const t = new Date(firstTick.getTime() + i * tickIntervalMs);
        if (t <= maxDate || i === numTicks - 1) tickvals.push(t.toISOString().split('T')[0]);
    }}
    const chartWidth = document.querySelector('.plot-container')?.clientWidth || 1000;
    const fontSize = Math.max(8, Math.min(12, (chartWidth / tickvals.length) * 0.15));
    Plotly.relayout(window.plotDiv, {{
        'xaxis.tickmode': 'array',
        'xaxis.tickvals': tickvals,
        'xaxis.tickformat': tickFormat,
        'xaxis.tickangle': -45,
        'xaxis.tickfont.size': fontSize,
        'xaxis.gridcolor': 'grey',
        'xaxis.gridwidth': 1,
    }});
}}

function initializePlot() {{
    const initialCategoryArray = allTasks.map(t=>t.DisplayName);
    const initialHeight = Math.max(600, initialCategoryArray.length * 25);
    const plotLayoutDynamic = {{
        ...plotLayout,
        height: initialHeight,
        yaxis: {{
            ...plotLayout.yaxis,
            categoryarray: initialCategoryArray,
            tickvals: initialCategoryArray,
            ticktext: initialCategoryArray,
            range: [-0.5, initialCategoryArray.length - 0.5],
        }},
    }};
    Plotly.newPlot('plot', allTracesData, plotLayoutDynamic).then(plotDiv => {{
        window.plotDiv = plotDiv;
        updateDateTicksAndGrid();
        updateSelectionDisplay();
    }});
}}

function updateChartWithSelection() {{
    if (!window.plotDiv) return;
    currentVisibleTasks = new Set(selectedTasks);
    const visibleCategoryArray = allTasks
        .filter(t => currentVisibleTasks.has(t.TaskID))
        .map(t => t.DisplayName);
    if (visibleCategoryArray.length === 0) {{ console.warn("No tasks to display."); return; }}
    const maxLabelLength = Math.max(...visibleCategoryArray.map(v=>v.length), 10);
    const fontSize = Math.max(8, 20 - (maxLabelLength / 3));
    const newHeight = Math.max(600, visibleCategoryArray.length * 25);
    const visibilityUpdates = traceMeta.map(tm => currentVisibleTasks.has(tm.task_id));
    Plotly.restyle(window.plotDiv, {{visible: visibilityUpdates}}).then(() => {{
        return Plotly.relayout(window.plotDiv, {{
            'yaxis.categoryarray': visibleCategoryArray,
            'yaxis.tickvals': visibleCategoryArray,
            'yaxis.ticktext': visibleCategoryArray,
            'yaxis.tickfont.size': fontSize,
            'yaxis.range': [-0.5, visibleCategoryArray.length - 0.5],
            'height': newHeight,
            'margin.l': 290,
            'margin.r': 40,
            'margin.t': 30,
            'margin.b': 150,
            'xaxis.autorange': true,
        }});
    }}).then(() => {{
        updateDateTicksAndGrid();
        updateSelectionDisplay();
    }});
}}

function updateSelectionDisplay() {{
    const selectedCount = selectedTasks.size;
    const visibleCount  = currentVisibleTasks.size;
    document.getElementById('selection-count').textContent =
        `${{selectedCount}} selected, ${{visibleCount}} visible`;
    document.querySelectorAll('.task-row').forEach(row => {{
        const taskId   = row.getAttribute('data-task-id');
        const checkbox = row.querySelector('.task-checkbox');
        const isSel    = selectedTasks.has(taskId);
        checkbox.checked = isSel;
        row.setAttribute('data-selected', isSel);
        row.classList.toggle('selected', isSel);
        row.style.opacity = currentVisibleTasks.has(taskId) ? '1' : '0.4';
    }});
}}

function toggleTaskSelection(taskId, selected) {{
    if (selected) selectedTasks.add(taskId); else selectedTasks.delete(taskId);
}}
function selectAllTasks()   {{ allTasks.forEach(t => selectedTasks.add(t.TaskID)); updateChartWithSelection(); }}
function deselectAllTasks() {{ selectedTasks.clear(); updateChartWithSelection(); }}
function resetToFullView()  {{
    selectedTasks = new Set(allTasks.map(t => t.TaskID));
    document.getElementById('discipline-filter').value = '__all__';
    document.getElementById('zone-filter').value       = '__all__';
    updateChartWithSelection();
}}

function applyFilters() {{
    const selDisc = document.getElementById('discipline-filter').value;
    const selZone = document.getElementById('zone-filter').value;
    selectedTasks.clear();
    allTasks.forEach(t => {{
        if ((selDisc === '__all__' || t.Discipline === selDisc) &&
            (selZone === '__all__' || t.Zone === selZone))
            selectedTasks.add(t.TaskID);
    }});
    updateChartWithSelection();
}}

function splitAndDownloadCharts(tasksPerSection = 50) {{
    const visibleTasksArr = Array.from(currentVisibleTasks);
    let start = 0, sectionNum = 1;
    function processNextSection() {{
        if (start >= visibleTasksArr.length) return;
        const sectionTasks = visibleTasksArr.slice(start, start + tasksPerSection);
        const sectionCategoryArray = allTasks.filter(t => sectionTasks.includes(t.TaskID)).map(t => t.DisplayName);
        if (sectionCategoryArray.length === 0) {{ start += tasksPerSection; processNextSection(); return; }}
        const visibilityUpdates = traceMeta.map(tm => sectionTasks.includes(tm.task_id));
        const sectionDates = [];
        traceMeta.forEach((tm, index) => {{
            if (sectionTasks.includes(tm.task_id)) {{
                const trace = allTracesData[index];
                sectionDates.push(new Date(trace.x[0]), new Date(trace.x[1]));
            }}
        }});
        if (sectionDates.length === 0) {{ start += tasksPerSection; processNextSection(); return; }}
        const minDate = new Date(Math.min(...sectionDates));
        const maxDate = new Date(Math.max(...sectionDates));
        const tempDiv = document.createElement('div');
        tempDiv.style.cssText = 'position:absolute;left:-9999px;width:1200px;height:' +
            Math.max(600, sectionCategoryArray.length * 25) + 'px';
        document.body.appendChild(tempDiv);
        try {{
            const filteredTraces = allTracesData.map((trace, index) => ({{...trace, visible: visibilityUpdates[index]}}));
            const tempLayout = {{
                ...plotLayout,
                title: {{ ...plotLayout.title,
                    text: `Gantt Section ${{sectionNum}}: ${{minDate.toLocaleDateString('en-US', {{day:'numeric',month:'short',year:'numeric'}})}} to ${{maxDate.toLocaleDateString('en-US', {{day:'numeric',month:'short',year:'numeric'}})}}`
                }},
                yaxis: {{ ...plotLayout.yaxis, categoryarray: sectionCategoryArray, tickvals: sectionCategoryArray, ticktext: sectionCategoryArray, autorange: true }},
                xaxis: {{ ...plotLayout.xaxis, range: [minDate.toISOString().slice(0,10), maxDate.toISOString().slice(0,10)], autorange: false, tickmode: 'auto', tickformat: '%Y-%m-%d', tickangle: -45 }},
                height: tempDiv.offsetHeight,
                width:  tempDiv.offsetWidth,
                showlegend: false,
                margin: {{...plotLayout.margin, b: 150}},
            }};
            Plotly.newPlot(tempDiv, filteredTraces, tempLayout)
                .then(() => new Promise(r => setTimeout(r, 500)))
                .then(() => Plotly.toImage(tempDiv, {{format:'png', height: tempDiv.offsetHeight, width: tempDiv.offsetWidth}}))
                .then(dataUrl => {{
                    const a = document.createElement('a');
                    a.href = dataUrl;
                    a.download = `Gantt_Section_${{sectionNum}}_(${{sectionTasks.length}}_tasks).png`;
                    document.body.appendChild(a); a.click(); document.body.removeChild(a);
                    Plotly.purge(tempDiv); document.body.removeChild(tempDiv);
                    start += tasksPerSection; sectionNum++; processNextSection();
                }})
                .catch(error => {{
                    console.error('PNG error:', error);
                    alert(`Error generating section ${{sectionNum}}: ${{error.message}}`);
                    Plotly.purge(tempDiv); document.body.removeChild(tempDiv);
                    start += tasksPerSection; sectionNum++; processNextSection();
                }});
        }} catch (error) {{
            console.error('Setup error:', error);
            document.body.removeChild(tempDiv);
            start += tasksPerSection; sectionNum++; processNextSection();
        }}
    }}
    processNextSection();
}}

document.addEventListener('click', function(e) {{
    if (e.target.classList.contains('task-checkbox')) {{
        toggleTaskSelection(e.target.getAttribute('data-task-id'), e.target.checked);
        updateChartWithSelection();
    }}
    if (e.target.closest('.task-row') && !e.target.classList.contains('task-checkbox')) {{
        const row = e.target.closest('.task-row');
        const cb = row.querySelector('.task-checkbox');
        cb.checked = !cb.checked;
        toggleTaskSelection(row.getAttribute('data-task-id'), cb.checked);
        updateChartWithSelection();
    }}
}});

document.addEventListener('DOMContentLoaded', function() {{
    initializePlot();
    document.getElementById('select-all').addEventListener('click', selectAllTasks);
    document.getElementById('deselect-all').addEventListener('click', deselectAllTasks);
    document.getElementById('apply-selection').addEventListener('click', updateChartWithSelection);
    document.getElementById('discipline-filter').addEventListener('change', applyFilters);
    document.getElementById('zone-filter').addEventListener('change', applyFilters);
    document.getElementById('reset-view').addEventListener('click', resetToFullView);
    document.getElementById('jump-btn').addEventListener('click', function() {{
        const q = document.getElementById('jump-input').value.trim().toLowerCase();
        if (!q || !window.plotDiv) return;
        const found = allTasks.find(t => t.TaskID.toLowerCase().includes(q) || t.TaskName.toLowerCase().includes(q));
        if (found) {{
            const layout = window.plotDiv.layout || {{}};
            const ca = (layout.yaxis || {{}}).categoryarray || [];
            const idx = ca.indexOf(found.DisplayName);
            if (idx >= 0) {{
                const vc = 10;
                const si = Math.max(0, idx - Math.floor(vc / 2));
                const ei = Math.min(ca.length - 1, si + vc - 1);
                Plotly.relayout(window.plotDiv, {{'yaxis.range': [ei, si]}});
            }} else {{ alert('Task found but not in current view. Try resetting filters.'); }}
        }} else {{ alert('Task not found: ' + q); }}
    }});
    document.getElementById('toggle-legend').addEventListener('click', () => {{
        const p = document.getElementById('legend-panel');
        p.style.display = (p.style.display === 'none') ? 'block' : 'none';
    }});
    document.getElementById('fit-btn').addEventListener('click', () => {{
        if (window.plotDiv) {{
            Plotly.relayout(window.plotDiv, {{'xaxis.autorange': true, 'yaxis.autorange': true}});
            setTimeout(updateDateTicksAndGrid, 100);
        }}
    }});
    document.getElementById('split-download').addEventListener('click', () => {{
        const tps = parseInt(document.getElementById('tasks-per-section').value) || 50;
        splitAndDownloadCharts(tps);
    }});
    window.addEventListener('resize', function() {{
        if (window.plotDiv) setTimeout(updateDateTicksAndGrid, 100);
    }});
}});
</script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return output_path


# ══════════════════════════════════════════════════════════════════
# Streamlit App
# ══════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title="Gantt Chart Generator",
        page_icon="📊",
        layout="wide",
    )

    # ── Session state initialisation ──────────────────────────────
    for key, default in [
        ("df", None),
        ("discipline_colors", {}),
        ("uploaded_file_name", None),
        ("is_sample", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Sidebar ───────────────────────────────────────────────────
    with st.sidebar:
        st.title("📋 Instructions")
        st.markdown("""
### **Step-by-Step Guide:**

1. **Upload Excel File** — or load the built-in sample project
   - ✅ `TaskID` (e.g. `1.1_F0_A`)
   - ✅ `Discipline` (e.g. `Fondations`)
   - ✅ `Start` (date)
   - ✅ `End` (date)
   - Optional: `TaskName`, `Zone`, `floor`

2. **Configure Colors** — one color picker per discipline

3. **Generate & Download** — get the standalone HTML file

### **Interactive Features in the HTML:**
- Filter by Discipline / Zone
- Select / hide individual tasks
- Jump to any task by ID or name
- Split & export PNG sections
- Fully offline — no internet needed

### **Sample File Format:**
| TaskID | Discipline | Start | End | TaskName | Zone |
|--------|-----------|-------|-----|----------|------|
| 1.1_F-1_A | Terrassement | 2024-01-01 | 2024-01-10 | Tranchées | A |
        """)

        st.divider()
        st.subheader("📁 Blank Template")

        sample_template = pd.DataFrame({
            "TaskID":     ["1.1_F-1_A", "1.2_F-1_B", "2.1_F0_A"],
            "Discipline": ["Terrassement", "Terrassement", "Fondations"],
            "Start":      ["2024-01-01", "2024-01-05", "2024-01-12"],
            "End":        ["2024-01-10", "2024-01-15", "2024-01-20"],
            "TaskName":   ["Tranchées des semelles", "Tranchées des semelles", "Béton de propreté"],
            "Zone":       ["A", "B", "A"],
            "floor":      [-1, -1, 0],
        })
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            sample_template.to_excel(w, index=False, sheet_name="Schedule")
        st.download_button(
            label="📥 Download Template",
            data=buf.getvalue(),
            file_name="gantt_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ── Main title ────────────────────────────────────────────────
    st.title("📊 Interactive Gantt Chart Generator")
    st.markdown("Transform your project planning Excel file into an interactive, fully offline Gantt chart.")

    tab1, tab2, tab3 = st.tabs(["📤 Upload / Load Data", "🎨 Configure Colors", "🚀 Generate & Download"])

    # ════════════════════════════════════════════════════════════════
    # TAB 1 — Upload / Sample Data
    # ════════════════════════════════════════════════════════════════
    with tab1:
        st.header("1. Load Your Project Schedule")

        # ── Option A: Upload your own file ────────────────────────
        st.subheader("Option A — Upload your Excel file")
        col_up, col_meta = st.columns([2, 1])
        with col_up:
            uploaded_file = st.file_uploader(
                "Drag & drop or click to browse",
                type=["xlsx", "xls"],
                help="Upload your project planning Excel file",
                key="file_upload",
            )
        with col_meta:
            st.metric("Required Columns", "4", help="TaskID, Discipline, Start, End")
            st.metric("Optional Columns", "3", help="TaskName, Zone, floor")

        if uploaded_file:
            try:
                file_details = {"Filename": uploaded_file.name, "Size": f"{uploaded_file.size / 1024:.1f} KB"}
                st.json(file_details, expanded=False)

                with st.expander("🔍 Preview Uploaded Data", expanded=True):
                    df = pd.read_excel(uploaded_file)
                    st.session_state.df = df
                    st.session_state.uploaded_file_name = uploaded_file.name
                    st.session_state.is_sample = False
                    st.session_state.discipline_colors = {}

                    st.dataframe(df.head(10), use_container_width=True)

                    required_columns = {"TaskID", "Discipline", "Start", "End"}
                    missing = required_columns - set(df.columns)
                    if missing:
                        st.error(f"❌ Missing columns: {', '.join(missing)}")
                    else:
                        st.success("✅ All required columns found!")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("Total Tasks", len(df))
                        with c2:
                            st.metric("Disciplines", df["Discipline"].nunique())
                        with c3:
                            try:
                                df["Start"] = pd.to_datetime(df["Start"])
                                df["End"]   = pd.to_datetime(df["End"])
                                dr = f"{df['Start'].min():%Y-%m-%d} → {df['End'].max():%Y-%m-%d}"
                            except Exception:
                                dr = "Check date format"
                            st.metric("Date Range", dr)
            except Exception as e:
                st.error(f"❌ Error processing file: {e}")

        # ── Divider ───────────────────────────────────────────────
        st.divider()

        # ── Option B: Built-in sample project ─────────────────────
        st.subheader("Option B — Try the built-in sample project")

        # Info card
        with st.container(border=True):
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.markdown(
                    "**🏗️ Résidence Les Acacias — R+4 + 2 Sous-Sols  /  Acacia Residences — G+4 + 2 Basements**"
                )
                st.caption(
                    "Reinforced-concrete residential building · 2 construction zones (North A / South B) · "
                    "7 disciplines · ~280 bilingual tasks · 13-month schedule"
                )

                # Discipline badge row
                badge_html = " ".join(
                    f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:10px;'
                    f'font-size:11px;margin:2px;display:inline-block;">{d}</span>'
                    for d, c in SAMPLE_DISCIPLINE_COLORS.items()
                )
                st.markdown(badge_html, unsafe_allow_html=True)

                # Stats
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("Tasks",       "~280")
                s2.metric("Disciplines", "7")
                s3.metric("Floors",      "7  (F-2 → F+4)")
                s4.metric("Duration",    "~13 months")

            with col_btn:
                st.write("")   # spacer
                st.write("")
                if st.button(
                    "🏗️ Load Sample Project",
                    type="primary",
                    use_container_width=True,
                    help="Load the built-in bilingual construction schedule",
                ):
                    with st.spinner("Building sample schedule…"):
                        sample_df = get_sample_project()
                        st.session_state.df                = sample_df
                        st.session_state.uploaded_file_name = f"📋 Sample — {PROJECT_META['name']}"
                        st.session_state.is_sample          = True
                        st.session_state.discipline_colors  = dict(SAMPLE_DISCIPLINE_COLORS)
                    st.success(f"✅ Sample project loaded — {len(sample_df)} tasks ready!")
                    st.rerun()

        # ── Show sample preview if loaded ─────────────────────────
        if st.session_state.is_sample and st.session_state.df is not None:
            df = st.session_state.df
            st.success(
                f"✅ **Sample project active** — {len(df)} tasks across "
                f"{df['Discipline'].nunique()} disciplines  |  "
                f"{df['Start'].min()} → {df['End'].max()}"
            )
            with st.expander("🔍 Preview sample data (first 15 rows)", expanded=False):
                st.dataframe(df.head(15), use_container_width=True)

        elif not uploaded_file and not st.session_state.is_sample:
            st.info("👆 Upload an Excel file above, or click **Load Sample Project** to explore the app instantly.")

    # ════════════════════════════════════════════════════════════════
    # TAB 2 — Colors
    # ════════════════════════════════════════════════════════════════
    with tab2:
        st.header("2. Configure Discipline Colors")
        st.info("💡 Colors help distinguish disciplines in the Gantt chart")

        if st.session_state.df is not None:
            df          = st.session_state.df
            disciplines = sorted(df["Discipline"].astype(str).unique().tolist())

            # Initialise missing disciplines
            for disc in disciplines:
                if disc not in st.session_state.discipline_colors:
                    st.session_state.discipline_colors[disc] = DEFAULT_DISCIPLINE_COLORS.get(disc, "#BDC3C7")

            if st.session_state.is_sample:
                st.caption("🎨 Colors are pre-set for the sample project — feel free to change them.")

            cols = st.columns(3)
            for idx, disc in enumerate(disciplines):
                with cols[idx % 3]:
                    count = len(df[df["Discipline"] == disc])
                    st.session_state.discipline_colors[disc] = st.color_picker(
                        label=f"**{disc}** ({count} tasks)",
                        value=st.session_state.discipline_colors.get(disc, "#BDC3C7"),
                        key=f"color_{disc}",
                    )

            st.subheader("🎨 Color Legend Preview")
            legend_cols = st.columns(min(5, len(disciplines)))
            for idx, disc in enumerate(disciplines):
                col_idx = idx % 5
                with legend_cols[col_idx]:
                    color = st.session_state.discipline_colors.get(disc, "#BDC3C7")
                    st.markdown(
                        f"<div style='background:{color};padding:10px;border-radius:5px;"
                        f"color:white;text-align:center;'><strong>{disc}</strong><br>{color}</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.warning("⚠️ Please load a project in the **Upload / Load Data** tab first.")

    # ════════════════════════════════════════════════════════════════
    # TAB 3 — Generate & Download
    # ════════════════════════════════════════════════════════════════
    with tab3:
        st.header("3. Generate & Download")

        if st.session_state.df is not None and st.session_state.uploaded_file_name:
            label = st.session_state.uploaded_file_name
            st.success(f"✅ **{label}**")
            if st.session_state.is_sample:
                st.info(
                    "🏗️ You are using the **built-in sample project**.  "
                    "The generated HTML is fully functional — great for a demo or to explore the interactive features."
                )
            else:
                st.info("⚠️ The generated HTML file contains full interactive features. Open it in any modern browser.")

            c1, c2, c3 = st.columns(3)
            c1.metric("Step 1", "Upload ✓")
            c2.metric("Step 2", "Colors ✓" if st.session_state.discipline_colors else "Colors")
            c3.metric("Step 3", "Ready")

            if st.button(
                "🚀 **Generate Interactive Gantt Chart**",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Generating interactive chart…"):
                    try:
                        bar = st.progress(0)
                        for i in range(3):
                            time.sleep(0.3)
                            bar.progress((i + 1) * 33)

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                            out_path = tmp.name

                        generate_interactive_gantt(
                            st.session_state.df,
                            out_path,
                            st.session_state.discipline_colors,
                        )

                        with open(out_path, "rb") as f:
                            html_bytes = f.read()

                        st.success("✅ Generation complete!")
                        fname = (
                            "sample_gantt_acacia_residences.html"
                            if st.session_state.is_sample
                            else f"gantt_chart_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.html"
                        )
                        st.download_button(
                            label="📥 **Download Interactive Gantt Chart**",
                            data=html_bytes,
                            file_name=fname,
                            mime="text/html",
                            type="primary",
                            use_container_width=True,
                        )

                        with st.expander("📖 How to use the downloaded file", expanded=True):
                            st.markdown("""
1. **Save** the downloaded HTML file to your computer
2. **Open** it in any modern web browser (Chrome, Firefox, Edge) — no internet needed
3. **Interactive features available inside:**
   - Filter by Discipline / Zone using dropdowns
   - Select / hide individual tasks via the legend table
   - Jump to any task by ID or name
   - Use **Split & Download PNGs** to export image sections for reports
   - Resize the timeline with range buttons or the Fit button
4. **Export PNGs:** Adjust *Tasks per PNG* count, then click the button
                            """)

                        os.unlink(out_path)

                    except Exception as e:
                        st.error(f"❌ Error generating chart: {e}")
        else:
            st.warning("⚠️ Please load a project in the **Upload / Load Data** tab first.")

    # ── Footer ────────────────────────────────────────────────────
    st.divider()
    fc1, fc2, fc3 = st.columns(3)
    fc1.caption("📊 **Gantt Chart Generator v1.1**")
    fc2.caption("💡 Need help? Check the sidebar instructions")
    with fc3:
        if st.button("🔄 Reset — start over"):
            for k in ["df", "discipline_colors", "uploaded_file_name", "is_sample"]:
                st.session_state[k] = {} if k == "discipline_colors" else None if k != "is_sample" else False
            st.rerun()


if __name__ == "__main__":
    main()
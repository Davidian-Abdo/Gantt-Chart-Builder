import streamlit as st
import pandas as pd
import tempfile
import os
from typing import Dict
import json
import html
import time
from io import BytesIO

# Default colors
DEFAULT_DISCIPLINE_COLORS = {
    "Préliminaires": "#FF6B6B",
    "Terrassement": "#4ECDC4",
    "Fondations": "#45B7D1",
    "GrosOeuvres": "#96CEB4",
    "SecondOeuvres": "#FECA57",
    "default": "#BDC3C7"
}

def _validate_required_columns(df: pd.DataFrame, required: set, name: str = "DataFrame") -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name} missing required columns: {sorted(list(missing))}")

def _convert_schedule_dates(df: pd.DataFrame, start_col: str = 'Start', end_col: str = 'End') -> pd.DataFrame:
    df = df.copy()
    if start_col not in df.columns or end_col not in df.columns:
        if 'Finish' in df.columns and end_col not in df.columns:
            end_col = 'Finish'
    df['Start'] = pd.to_datetime(df[start_col], errors='coerce')
    df['End'] = pd.to_datetime(df[end_col], errors='coerce')
    if df['Start'].isna().any() or df['End'].isna().any():
        raise ValueError("Some Start or End values could not be parsed to datetime in schedule.")
    return df

def generate_interactive_gantt(schedule_df: pd.DataFrame, output_path: str, discipline_colors: Dict[str, str] = None) -> str:
    """
    Generate interactive Gantt chart HTML file
    """
    if discipline_colors is None:
        discipline_colors = DEFAULT_DISCIPLINE_COLORS
    
    required = {"TaskID", "Discipline", "Start", "End"}
    _validate_required_columns(schedule_df, required, "schedule_df")

    df = _convert_schedule_dates(schedule_df).copy()
    df['TaskID'] = df['TaskID'].astype(str)
    df['TaskName'] = df.get('TaskName', df['TaskID'])
    df['TaskID_Legend'] = df['TaskID'].apply(lambda x: x.split('-')[0])
    df['TaskZone'] = df.get('Zone', df['TaskID'].apply(lambda x: x.split('-')[-1] if '-' in x else ''))

    df['DisplayName'] = df.apply(lambda r: f"{r['TaskName']} {'-'.join(r['TaskID'].split('-')[1:]) if '-' in r['TaskID'] else r['TaskID']}", axis=1)
    df = df.sort_values(['Start','Discipline','TaskZone','TaskID_Legend'])
    df['DurationDays'] = (df['End'] - df['Start']).dt.total_seconds() / (3600 * 24)

    # Color mapping
    unique_disc = df['Discipline'].astype(str).unique().tolist()
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
    trace_meta = []
    all_tasks_data = []
    
    for _, row in df.iterrows():
        discipline = str(row['Discipline'])
        zone = str(row['TaskZone'])
        task_id = str(row['TaskID'])
        task_name = str(row['TaskName'])
        display_name = str(row['DisplayName'])
        start_date = row['Start'].strftime('%Y-%m-%d')
        end_date = row['End'].strftime('%Y-%m-%d')
        duration = float(row['DurationDays'])
        color = str(color_discrete_map.get(discipline, 'blue'))
        
        if end_date == start_date:
            end_date = pd.to_datetime(end_date) + pd.Timedelta(days=0.3)
            end_date = end_date.strftime('%Y-%m-%d %H:%M:%S')
        
        trace = {
            'x': [start_date, end_date],
            'y': [display_name, display_name],
            'mode': 'lines',
            'line': {'color': color, 'width': 8},
            'name': f"{discipline} | {zone}" if zone else discipline,
            'hovertemplate': (
                f"<b>{html.escape(task_name)}</b><br>"
                f"ID: {html.escape(task_id)}<br>"
                f"Start: {start_date}<br>"
                f"End: {end_date}<br>"
                f"Duration: {duration:.1f} days<extra></extra>"
            ),
            'showlegend': False
        }
        traces_data.append(trace)
        
        trace_meta.append({
            'trace_index': len(traces_data)-1,
            'discipline': discipline,
            'zone': zone,
            'task_id': task_id,
            'display_name': display_name,
            'task_name': task_name,
            'selected': True
        })
        
        all_tasks_data.append({
            'TaskID': task_id,
            'TaskName': task_name,
            'DisplayName': display_name,
            'Discipline': discipline,
            'Zone': zone
        })
    
    # Layout - KEY CHANGE: Modified xaxis configuration for better grid alignment
    layout_data = {
        'title': {
            'text': 'Interactive Project Schedule Gantt',
            'x': 0.5,
            'xanchor': 'center',
            'y': 0.99,
            'yref': 'paper',
            'font': {'size': 24, 'family': 'Arial Black, sans-serif', 'color': 'black'}
        },
        'height': max(600, len(df)*25),
        'margin': {'l': 300, 'r': 40, 't': 10, 'b': 150},  # Increased bottom margin for date labels
        'xaxis': {
            'title': 'Date',
            'type': 'date',
            'rangeselector': {
                'buttons': [
                    {'count': 1, 'label': '1m', 'step': 'month', 'stepmode': 'backward'},
                    {'count': 6, 'label': '6m', 'step': 'month', 'stepmode': 'backward'},
                    {'count': 14, 'label': '14m', 'step': 'month', 'stepmode': 'backward'},
                    {'count': 30, 'label': '30m', 'step': 'month', 'stepmode': 'backward'},
                    {'step': 'all', 'label': 'Fit'}
                ],
                'y': 0.98
            },
            'showgrid': True,
            'gridcolor': 'grey',
            'griddash': 'solid',
            'gridwidth': 1,
            # CHANGES: Better x-axis configuration for grid alignment
            'tickformat': '%Y-%m-%d',  # Added format for labels
            'showticklabels': True,  # Enabled tick labels instead of annotations
            'tickangle': -45,  # Rotate labels for better readability
            'tickmode': 'auto',  # Let Plotly decide tick placement dynamically
            'automargin': True,  # Auto-adjust margins for labels
            'ticklabelmode': 'period',  # Better label positioning
            # REMOVED: 'dtick': 604800000, - Fixed interval was causing misalignment
            # REMOVED: 'showticklabels': False - Now showing x-axis labels
        },
        'yaxis': {
            'title': 'Tasks',
            'autorange': True,
            'yaxis.automargin': False,
            'showgrid': True,
            'gridcolor': 'lightgrey',
            'gridwidth': 1,
            'domain': [0, 0.97]
        }
    }

    traces_data_json = json.dumps(traces_data)
    layout_data_json = json.dumps(layout_data)
    trace_meta_json = json.dumps(trace_meta)
    all_tasks_json = json.dumps(all_tasks_data)

    disciplines = sorted(df['Discipline'].astype(str).unique().tolist())
    zones = sorted([z for z in df['TaskZone'].astype(str).unique().tolist() if z])

    # HTML content
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

<div class="plot-container"><div id="plot"style="width:100%; height:100%;"></div></div>

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
{''.join(f'<tr class="task-row" data-task-id="{html.escape(str(r["TaskID"]))}" data-selected="true">\
<td><input type="checkbox" class="task-checkbox" checked data-task-id="{html.escape(str(r["TaskID"]))}"></td>\
<td>{html.escape(str(r["TaskID_Legend"]))}</td>\
<td>{html.escape(str(r["TaskName"]))}</td>\
<td>{html.escape(str(r["Discipline"]))}</td>\
<td>{html.escape(str(r["TaskZone"]))}</td></tr>' for _, r in df.iterrows())}
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
    
    // Calculate time range in days
    const timeRangeMs = maxDate - minDate;
    const timeRangeDays = timeRangeMs / (1000 * 60 * 60 * 24);
    
    // Determine appropriate tick interval based on timeline size
    let tickIntervalMs;
    let tickFormat;
    
    if (timeRangeDays <= 7) {{
        // For very short timelines (≤ 7 days): daily ticks
        tickIntervalMs = 86400000; // 1 day
        tickFormat = '%b %d';
    }} else if (timeRangeDays <= 30) {{
        // For short timelines (≤ 30 days): weekly ticks
        tickIntervalMs = 86400000 * 7; // 7 days
        tickFormat = '%b %d';
    }} else if (timeRangeDays <= 90) {{
        // For medium timelines (≤ 90 days): bi-weekly ticks
        tickIntervalMs = 86400000 * 14; // 14 days
        tickFormat = '%b %d, %Y';
    }} else if (timeRangeDays <= 180) {{
        // For medium-long timelines (≤ 180 days): monthly ticks
        tickIntervalMs = 86400000 * 30; // Approx 30 days
        tickFormat = '%b %Y';
    }} else {{
        // For long timelines (> 180 days): quarterly ticks
        tickIntervalMs = 86400000 * 91; // Approx 3 months
        tickFormat = '%b %Y';
    }}
    
    // Calculate first tick that aligns with a logical date
    // For weekly ticks, align to Monday
    const firstTick = new Date(minDate);
    if (tickIntervalMs === 86400000 * 7) {{
        // Align to Monday for weekly ticks
        const dayOfWeek = firstTick.getDay();
        const daysToMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // 0=Sunday, 1=Monday, etc.
        firstTick.setDate(firstTick.getDate() - daysToMonday);
    }} else if (tickIntervalMs === 86400000 * 30) {{
        // Align to first day of month for monthly ticks
        firstTick.setDate(1);
    }}
    
    // Calculate number of ticks needed
    const numTicks = Math.ceil((maxDate - firstTick) / tickIntervalMs) + 1;
    
    // Generate tick positions
    const tickvals = [];
    for (let i = 0; i < numTicks; i++) {{
        const tickDate = new Date(firstTick.getTime() + i * tickIntervalMs);
        if (tickDate <= maxDate || i === numTicks - 1) {{
            tickvals.push(tickDate.toISOString().split('T')[0]);
        }}
    }}
    
    // Calculate appropriate font size based on chart width and number of ticks
    const chartWidth = document.querySelector('.plot-container')?.clientWidth || 1000;
    const pixelsPerTick = chartWidth / tickvals.length;
    const fontSize = Math.max(8, Math.min(12, pixelsPerTick * 0.15));
    
    // Update the x-axis with dynamic ticks
    Plotly.relayout(window.plotDiv, {{
        'xaxis.tickmode': 'array',
        'xaxis.tickvals': tickvals,
        'xaxis.tickformat': tickFormat,
        'xaxis.tickangle': -45,
        'xaxis.tickfont.size': fontSize,
        'xaxis.dtick': undefined, // Clear any fixed dtick
        'xaxis.tick0': firstTick.toISOString().split('T')[0],
        'xaxis.gridcolor': 'grey',
        'xaxis.gridwidth': 1
    }});
}}

function initializePlot(){{
    const initialCategoryArray = allTasks.map(t=>t.DisplayName);
    const initialHeight = Math.max(600, initialCategoryArray.length*25);
    const plotLayoutDynamic = {{
        ...plotLayout,
        height: initialHeight,
        yaxis: {{
            ...plotLayout.yaxis,
            categoryarray: initialCategoryArray,
            tickvals: initialCategoryArray,
            ticktext: initialCategoryArray,
            range: [-0.5, initialCategoryArray.length - 0.5] 
        }}
    }};
    Plotly.newPlot('plot', allTracesData, plotLayoutDynamic).then(plotDiv => {{
        window.plotDiv = plotDiv;
        updateDateTicksAndGrid();  // CHANGED: Call new function instead of updateWeeklyAnnotations
        updateSelectionDisplay();
    }});
}}

function updateChartWithSelection(){{
    if(!window.plotDiv) return;

    currentVisibleTasks = new Set(selectedTasks);

    const visibleCategoryArray = allTasks
        .filter(t => currentVisibleTasks.has(t.TaskID))
        .map(t => t.DisplayName);

    if(visibleCategoryArray.length===0){{
        console.warn("No tasks to display after filtering.");
        return;
    }}

    const maxLabelLength = Math.max(...visibleCategoryArray.map(v=>v.length),10);
    const fontSize = Math.max(8, 20 - (maxLabelLength/3));
    const newHeight = Math.max(600, visibleCategoryArray.length*25);

    const visibilityUpdates = traceMeta.map(tm => currentVisibleTasks.has(tm.task_id));
    const fixedDistanceTop = 30;
    const plotAreaTopMargin = fixedDistanceTop;
    Plotly.restyle(window.plotDiv, {{visible: visibilityUpdates}}).then(()=>{{
        return Plotly.relayout(window.plotDiv, {{
            'yaxis.categoryarray': visibleCategoryArray,
            'yaxis.tickvals': visibleCategoryArray,
            'yaxis.ticktext': visibleCategoryArray,
            'yaxis.tickfont.size': fontSize,
            'yaxis.range': [-0.5, visibleCategoryArray.length - 0.5],
            'height': newHeight,
            'margin.l': 290,
            'margin.r': 40,
            'margin.t': plotAreaTopMargin,
            'margin.b': 150,  // CHANGED: Increased bottom margin
            'xaxis.autorange': true
        }});
    }}).then(()=>{{ 
        updateDateTicksAndGrid();  // CHANGED: Call new function
        updateSelectionDisplay(); 
    }});
}}

function updateSelectionDisplay(){{
    const selectedCount = selectedTasks.size;
    const visibleCount = currentVisibleTasks.size;
    document.getElementById('selection-count').textContent = `${{selectedCount}} selected, ${{visibleCount}} visible`;
    document.querySelectorAll('.task-row').forEach(row=>{{
        const taskId = row.getAttribute('data-task-id');
        const checkbox = row.querySelector('.task-checkbox');
        const isSelected = selectedTasks.has(taskId);
        const isVisible = currentVisibleTasks.has(taskId);
        checkbox.checked = isSelected;
        row.setAttribute('data-selected', isSelected);
        row.classList.toggle('selected', isSelected);
        row.style.opacity = isVisible?'1':'0.4';
    }});
}}

function toggleTaskSelection(taskId, selected){{
    if(selected) selectedTasks.add(taskId);
    else selectedTasks.delete(taskId);
}}
function selectAllTasks(){{ allTasks.forEach(t=>selectedTasks.add(t.TaskID)); updateChartWithSelection(); }}
function deselectAllTasks(){{ selectedTasks.clear(); updateChartWithSelection(); }}
function resetToFullView(){{
    selectedTasks = new Set(allTasks.map(t=>t.TaskID));
    document.getElementById('discipline-filter').value='__all__';
    document.getElementById('zone-filter').value='__all__';
    updateChartWithSelection();
    updateDateTicksAndGrid();  // CHANGED: Call new function
}}

function applyFilters(){{
    const selDisc = document.getElementById('discipline-filter').value;
    const selZone = document.getElementById('zone-filter').value;
    selectedTasks.clear();
    allTasks.forEach(t=>{{
        if((selDisc==='__all__'||t.Discipline===selDisc) && (selZone==='__all__'||t.Zone===selZone))
            selectedTasks.add(t.TaskID);
    }});
    updateChartWithSelection();
}}

function splitAndDownloadCharts(tasksPerSection=50){{
    const visibleTasksArr = Array.from(currentVisibleTasks);
    let start = 0, sectionNum = 1;

    function processNextSection() {{
        if (start >= visibleTasksArr.length) return;
        
        const sectionTasks = visibleTasksArr.slice(start, start + tasksPerSection);
        const sectionCategoryArray = allTasks
            .filter(t => sectionTasks.includes(t.TaskID))
            .map(t => t.DisplayName);

        if (sectionCategoryArray.length === 0) {{
            start += tasksPerSection;
            processNextSection();
            return;
        }}

        const visibilityUpdates = traceMeta.map(tm => sectionTasks.includes(tm.task_id));

        const sectionDates = [];
        traceMeta.forEach((tm, index) => {{
            if (sectionTasks.includes(tm.task_id)) {{
                const trace = allTracesData[index];
                sectionDates.push(new Date(trace.x[0]), new Date(trace.x[1]));
            }}
        }});

        if (sectionDates.length === 0) {{
            start += tasksPerSection;
            processNextSection();
            return;
        }}

        const minDate = new Date(Math.min(...sectionDates));
        const maxDate = new Date(Math.max(...sectionDates));

        const tempDiv = document.createElement('div');
        tempDiv.style.position = 'absolute';
        tempDiv.style.left = '-9999px';
        tempDiv.style.width = '1200px';
        tempDiv.style.height = Math.max(600, sectionCategoryArray.length * 25) + 'px';
        document.body.appendChild(tempDiv);

        try {{
            const filteredTraces = allTracesData.map((trace, index) => ({{
                ...trace,
                visible: visibilityUpdates[index]
            }}));

            const tempLayout = {{
                ...plotLayout,
                title: {{ ...plotLayout.title, 
                    text: `Gantt Section ${{sectionNum}}: ${{minDate.toLocaleDateString('en-US', {{day:'numeric', month:'short', year:'numeric'}})}} to ${{maxDate.toLocaleDateString('en-US', {{day:'numeric', month:'short', year:'numeric'}})}}`
                   }},
                yaxis: {{
                    ...plotLayout.yaxis,
                    categoryarray: sectionCategoryArray,
                    tickvals: sectionCategoryArray,
                    ticktext: sectionCategoryArray,
                    autorange: true
                }},
                xaxis: {{
                    ...plotLayout.xaxis,
                    range: [minDate.toISOString().slice(0,10), maxDate.toISOString().slice(0,10)],
                    autorange: false,
                    tickmode: 'auto',  // Ensure auto ticks for PNG export
                    tickformat: '%Y-%m-%d',
                    tickangle: -45
                }},
                height: tempDiv.offsetHeight,
                width: tempDiv.offsetWidth,
                showlegend: false,
                margin: {{...plotLayout.margin, b: 150}}  // Increased bottom margin
            }};

            Plotly.newPlot(tempDiv, filteredTraces, tempLayout)
                .then(() => {{
                    return new Promise(resolve => setTimeout(resolve, 500));
                }})
                .then(() => {{
                    return Plotly.toImage(tempDiv, {{
                        format: 'png',
                        height: tempDiv.offsetHeight,
                        width: tempDiv.offsetWidth
                    }});
                }})
                .then(dataUrl => {{
                    const a = document.createElement('a');
                    a.href = dataUrl;
                    a.download = `Gantt_Section_${{sectionNum}}_(${{sectionTasks.length}}_tasks).png`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    
                    Plotly.purge(tempDiv);
                    document.body.removeChild(tempDiv);
                    
                    start += tasksPerSection;
                    sectionNum++;
                    processNextSection();
                }})
                .catch(error => {{
                    console.error('Error generating PNG:', error);
                    alert(`Error generating section ${{sectionNum}}: ${{error.message}}`);
                    
                    Plotly.purge(tempDiv);
                    document.body.removeChild(tempDiv);
                    
                    start += tasksPerSection;
                    sectionNum++;
                    processNextSection();
                }});
                
        }} catch (error) {{
            console.error('Error setting up plot:', error);
            document.body.removeChild(tempDiv);
            start += tasksPerSection;
            sectionNum++;
            processNextSection();
        }}
    }}

    processNextSection();
}}

document.addEventListener('click', function(e){{
    if(e.target.classList.contains('task-checkbox')){{
        toggleTaskSelection(e.target.getAttribute('data-task-id'), e.target.checked);
        updateChartWithSelection();
    }}
    if(e.target.closest('.task-row') && !e.target.classList.contains('task-checkbox')){{
        const row = e.target.closest('.task-row');
        const checkbox = row.querySelector('.task-checkbox');
        const newState = !checkbox.checked;
        checkbox.checked = newState;
        toggleTaskSelection(row.getAttribute('data-task-id'), newState);
        updateChartWithSelection();
    }}
}});

document.addEventListener('DOMContentLoaded', function(){{
    initializePlot();
    document.getElementById('select-all').addEventListener('click', selectAllTasks);
    document.getElementById('deselect-all').addEventListener('click', deselectAllTasks);
    document.getElementById('apply-selection').addEventListener('click', updateChartWithSelection);
    document.getElementById('discipline-filter').addEventListener('change', applyFilters);
    document.getElementById('zone-filter').addEventListener('change', applyFilters);
    document.getElementById('reset-view').addEventListener('click', resetToFullView);
    document.getElementById('jump-btn').addEventListener('click', function(){{
        const q=document.getElementById('jump-input').value.trim().toLowerCase();
        if(!q || !window.plotDiv) return;
        const foundTask = allTasks.find(t => t.TaskID.toLowerCase().includes(q) || t.TaskName.toLowerCase().includes(q));
        if(foundTask){{
            const layout = window.plotDiv.layout || {{}};
            const yaxis = layout.yaxis || {{}};
            const currentCategoryArray = yaxis.categoryarray || [];
            const idx = currentCategoryArray.indexOf(foundTask.DisplayName);
            if(idx>=0){{
                const visibleCount = 10;
                const startIdx = Math.max(0, idx - Math.floor(visibleCount/2));
                const endIdx = Math.min(currentCategoryArray.length-1, startIdx + visibleCount -1);
                Plotly.relayout(window.plotDiv, {{'yaxis.range':[endIdx, startIdx]}});
            }} else {{ alert('Task found but not in current view. Try resetting filters.'); }}
        }} else {{ alert('Task not found: '+q); }}
    }});
    document.getElementById('toggle-legend').addEventListener('click', ()=>{{ const panel=document.getElementById('legend-panel'); panel.style.display=(panel.style.display==='none')?'block':'none'; }});
    document.getElementById('fit-btn').addEventListener('click', ()=>{{ 
        if(window.plotDiv) {{
            Plotly.relayout(window.plotDiv, {{'xaxis.autorange':true,'yaxis.autorange':true}});
            setTimeout(updateDateTicksAndGrid, 100);  // Update ticks after autorange
        }}
    }});
    document.getElementById('split-download').addEventListener('click', ()=>{{
        const tps = parseInt(document.getElementById('tasks-per-section').value) || 50;
        splitAndDownloadCharts(tps);
    }});
    
    // Add resize listener to update ticks when window is resized
    window.addEventListener('resize', function() {{
        if (window.plotDiv) {{
            setTimeout(updateDateTicksAndGrid, 100);
        }}
    }});
}});
</script>
</body>
</html>
    """

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_path

# Streamlit App
def main():
    st.set_page_config(
        page_title="Gantt Chart Generator",
        page_icon="📊",
        layout="wide"
    )
    
    # Initialize session state
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'discipline_colors' not in st.session_state:
        st.session_state.discipline_colors = {}
    if 'uploaded_file_name' not in st.session_state:
        st.session_state.uploaded_file_name = None
    
    # Sidebar with instructions
    with st.sidebar:
        st.title("📋 Instructions")
        st.markdown("""
        ### **Step-by-Step Guide:**
        
        1. **Upload Excel File**
           - Must contain these columns:
           - ✅ `TaskID` (e.g., "1.1_F0_A")
           - ✅ `Discipline` (e.g., "Fondations")
           - ✅ `Start` (date)
           - ✅ `End` (date)
           - Optional: `TaskName`, `Zone`, `floor`
        
        2. **Configure Colors**
           - Set colors for each discipline
           - Click color pickers to change
        
        3. **Generate & Download**
           - Click 'Generate Gantt Chart'
           - Download HTML file
           - Open in browser to use interactive features
        
        ### **Interactive Features:**
        - Filter by Discipline/Zone
        - Jump to specific tasks
        - Split into multiple PNGs
        - Adjust timeline view
        - Task selection panel
        
        ### **Sample File Format:**
        | TaskID | Discipline | Start | End | TaskName | Zone | floor |
        |--------|------------|-------|-----|----------|------|-------|
        | 1.1_F-1_A | Terrassement | 2024-01-01 | 2024-01-10 | Tranchées | A | -1 |
        | 1.2_F-1_B | Terrassement | 2024-01-05 | 2024-01-15 | Tranchées | B | -1 |
        """)
        
        # Add download sample button
        st.divider()
        st.subheader("📁 Sample File")
        
        # Create sample DataFrame with floor column
        sample_data = pd.DataFrame({
            'TaskID': ['1.1_F-1_A', '1.2_F-1_B', '2.1_F-1_A', '2.1_F-1_B', '2.2_F-1_A', '2.2_F-1_B', '2.3_F-1_A', '2.3_F-1_B', '3.1_F-1_A', '3.2_F-1_A', '3.3_F-1_A','3.4_F-1_A','3.5_F-1_A','3.6_F-1_A','3.1_F0_A'],
            'Discipline': ['Terrassement', 'Terrassement', 'Fondations','Fondations','Fondations','Fondations','Fondations','Fondations', 'GrosOeuvres','GrosOeuvres','GrosOeuvres','GrosOeuvres','GrosOeuvres','GrosOeuvres','GrosOeuvres'],
            'Start': ['2024-01-01', '2024-01-05', '2024-01-10', '2024-01-15','2024-01-11', '2024-01-16','2024-01-12', '2024-01-17','2024-01-11','2024-01-20','2024-01-22','2024-01-24','2024-01-27','2024-01-28', '2024-02-01'],
            'End': ['2024-01-10', '2024-01-15', '2024-01-11', '2024-01-16','2024-01-12', '2024-01-17', '2024-01-14', '2024-01-19','2024-01-12','2024-01-22','2024-01-24','2024-01-27','2024-01-28','2024-02-01','2024-02-02'],
            'TaskName': ['Tranchées des semelles', 'Tranchées des semelles','Préparation du ferraillage des semmelles','Préparation du ferraillage des semmelles','Coufrage + pose des armartures des semelles','Coullage + decoufrage des semelles' ,'Coufrage + pose des armartures des semelles','Coullage + decoufrage des semelles',
                         'Préparation du ferraillage des poteaux', 'Coufrage + pose des armartures des poteaux','Coullage + decoufrage des poteaux','Coufrage du planchers sup','Pose du armatures du planchers sup','Coullage + decoufrage du planchers sup','Préparation du ferraillage des poteaux'],
            'Zone': ['A', 'B','A', 'B','A', 'B','A', 'B','A', 'A','A','A','A','A', 'A'],
            'floor': [-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,0]
        })
        
        # Convert to Excel in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            sample_data.to_excel(writer, index=False, sheet_name='Sample')
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 Download Sample Excel",
            data=excel_data,
            file_name="gantt_sample.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Download sample file to see required format"
        )
    
    st.title("📊 Interactive Gantt Chart Generator")
    st.markdown("Transform your project planning Excel file into an interactive Gantt chart")
    
    # Create tabs for better organization
    tab1, tab2, tab3 = st.tabs(["📤 Upload File", "🎨 Configure Colors", "🚀 Generate & Download"])
    
    with tab1:
        st.header("1. Upload Your Excel File")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_file = st.file_uploader(
                "Drag & drop or click to browse",
                type=['xlsx', 'xls'],
                help="Upload your project planning file",
                key="file_upload"
            )
        
        with col2:
            st.metric("Required Columns", "4+", help="TaskID, Discipline, Start, End are mandatory")
            
        if uploaded_file:
            try:
                # Show file info
                file_details = {
                    "Filename": uploaded_file.name,
                    "File size": f"{uploaded_file.size / 1024:.1f} KB"
                }
                st.json(file_details, expanded=False)
                
                # Preview data
                with st.expander("🔍 Preview Uploaded Data", expanded=True):
                    df = pd.read_excel(uploaded_file)
                    
                    # Store in session state
                    st.session_state.df = df
                    st.session_state.uploaded_file_name = uploaded_file.name
                    
                    st.dataframe(df.head(10), use_container_width=True)
                    
                    # Show column validation
                    required_columns = {"TaskID", "Discipline", "Start", "End"}
                    available_columns = set(df.columns)
                    missing = required_columns - available_columns
                    
                    if missing:
                        st.error(f"❌ Missing columns: {', '.join(missing)}")
                    else:
                        st.success(f"✅ All required columns found!")
                        
                        # Show statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Tasks", len(df))
                        with col2:
                            st.metric("Disciplines", df['Discipline'].nunique())
                        with col3:
                            # Handle potential date parsing issues
                            try:
                                df['Start'] = pd.to_datetime(df['Start'])
                                df['End'] = pd.to_datetime(df['End'])
                                date_range = f"{df['Start'].min():%Y-%m-%d} to {df['End'].max():%Y-%m-%d}"
                            except:
                                date_range = "Check date format"
                            st.metric("Date Range", date_range)
                            
                        # Show warning for large files
                        if uploaded_file.size > 10 * 1024 * 1024:  # 10MB
                            st.warning("""
                            ⚠️ **Large File Detected**
                            
                            Files over 10MB may take longer to process.
                            Consider:
                            - Filtering unnecessary rows
                            - Removing unused columns
                            - Splitting into smaller files
                            """)
            except Exception as e:
                st.error(f"❌ Error processing file: {str(e)}")
                st.info("Please check that your Excel file has the correct format and data types.")
        else:
            # Show instructions when no file is uploaded
            st.info("👆 Upload an Excel file to get started. You can download the sample file from the sidebar to see the required format.")

    with tab2:
        st.header("2. Configure Discipline Colors")
        st.info("💡 Colors help distinguish different disciplines in the Gantt chart")
        
        # Check if data exists in session state
        if st.session_state.df is not None:
            df = st.session_state.df
            
            # Color configuration with better layout
            disciplines = sorted(df['Discipline'].astype(str).unique().tolist())
            
            # Initialize discipline colors if not already done
            if not st.session_state.discipline_colors:
                for discipline in disciplines:
                    st.session_state.discipline_colors[discipline] = DEFAULT_DISCIPLINE_COLORS.get(discipline, "#BDC3C7")
            
            # Group color pickers in columns
            num_cols = 3
            cols = st.columns(num_cols)
            
            for idx, discipline in enumerate(disciplines):
                col = cols[idx % num_cols]
                with col:
                    # Color picker with discipline info
                    count = len(df[df['Discipline'] == discipline])
                    
                    # Update color in session state
                    st.session_state.discipline_colors[discipline] = st.color_picker(
                        label=f"**{discipline}** ({count} tasks)",
                        value=st.session_state.discipline_colors.get(discipline, "#BDC3C7"),
                        key=f"color_{discipline}"
                    )
            
            # Show color legend preview
            st.subheader("🎨 Color Legend Preview")
            legend_cols = st.columns(min(5, len(disciplines)))
            for idx, discipline in enumerate(disciplines):
                col_idx = idx % 5
                with legend_cols[col_idx]:
                    color = st.session_state.discipline_colors.get(discipline, "#BDC3C7")
                    st.markdown(
                        f"<div style='background-color:{color}; padding:10px; border-radius:5px; color:white; text-align:center;'>"
                        f"<strong>{discipline}</strong><br>{color}</div>",
                        unsafe_allow_html=True
                    )
        else:
            st.warning("⚠️ Please upload a file in the 'Upload File' tab first.")
            st.info("Once you upload a file, you'll be able to configure colors for each discipline found in your data.")
    
    with tab3:
        st.header("3. Generate & Download")
        
        if st.session_state.df is not None and st.session_state.uploaded_file_name:
            st.success(f"✅ File '{st.session_state.uploaded_file_name}' uploaded successfully")
            st.info("⚠️ The generated HTML file contains full interactive features. Open it in your browser.")
            
            # Progress and status
            with st.container():
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Step", "1/3", "Upload ✓")
                with col2:
                    # Check if colors are configured
                    if st.session_state.discipline_colors:
                        st.metric("Step", "2/3", "Colors ✓")
                    else:
                        st.metric("Step", "2/3", "Colors")
                with col3:
                    st.metric("Step", "3/3", "Ready")
            
            # Generate button with loading state
            if st.button("🚀 **Generate Interactive Gantt Chart**", 
                        type="primary", 
                        use_container_width=True,
                        help="Click to generate downloadable HTML file"):
                
                with st.spinner("Generating interactive chart..."):
                    try:
                        progress_bar = st.progress(0)
                        
                        # Simulate steps
                        for i in range(3):
                            time.sleep(0.5)
                            progress_bar.progress((i + 1) * 33)
                        
                        # Generate file
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as tmp_file:
                            output_path = tmp_file.name
                        
                        # Use session state data
                        generate_interactive_gantt(
                            st.session_state.df, 
                            output_path, 
                            st.session_state.discipline_colors
                        )
                        
                        # Read and provide download
                        with open(output_path, 'rb') as f:
                            html_bytes = f.read()
                        
                        st.success("✅ Generation complete!")
                        
                        # Download section
                        st.download_button(
                            label="📥 **Download Interactive Gantt Chart**",
                            data=html_bytes,
                            file_name=f"gantt_chart_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.html",
                            mime="text/html",
                            type="primary",
                            use_container_width=True
                        )
                        
                        # Instructions for use
                        with st.expander("📖 How to use the downloaded file", expanded=True):
                            st.markdown("""
                            1. **Save** the downloaded HTML file to your computer
                            2. **Open** it in any modern web browser (Chrome, Firefox, Edge)
                            3. **Use interactive features**:
                               - Filter by discipline/zone using dropdowns
                               - Click tasks to select/deselect
                               - Use "Split & Download PNGs" to export images
                               - Adjust timeline with buttons
                               - Search tasks with "Jump to Task"
                            4. **Export PNGs**: Adjust "Tasks per PNG" and click button
                            5. **Note**: Date labels now align properly with vertical grid lines
                            """)
                        
                        # Clean up
                        os.unlink(output_path)
                        
                    except Exception as e:
                        st.error(f"❌ Error generating chart: {str(e)}")
                        st.info("Please check your data format and try again.")
        else:
            st.warning("⚠️ Please upload a file in the 'Upload File' tab first.")
            st.info("Once you upload a file and configure colors, you can generate the Gantt chart here.")
    
    # Footer
    st.divider()
    footer_col1, footer_col2, footer_col3 = st.columns(3)
    with footer_col1:
        st.caption("📊 **Gantt Chart Generator v1.0**")
    with footer_col2:
        st.caption("💡 Need help? Check instructions in sidebar")
    with footer_col3:
        if st.button("🔄 Refresh page to start over"):
            st.session_state.df = None
            st.session_state.discipline_colors = {}
            st.session_state.uploaded_file_name = None
            st.rerun()

if __name__ == "__main__":
    main()

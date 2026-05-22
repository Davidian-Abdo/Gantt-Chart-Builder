## What the App Does
This is a single-file Streamlit web application that converts a structured Excel project schedule into a fully interactive, offline-capable Gantt chart exported as a standalone HTML file — no software installation required beyond a web browser.

## Core Workflow
Input → Assigne discilines to colors → Processing → Interactive downloadable Output

Upload an Excel file with columns: TaskID, Discipline, Start, End (plus optional TaskName, Zone, floor)
Configure per-discipline colors via color pickers
Generate & Download a self-contained HTML Gantt chart powered by Plotly.js


## Key Technical Features
Backend (Python/Streamlit)

Date parsing and validation with informative error messages
Dynamic color mapping with fallback to Plotly's qualitative palette
Plotly trace generation per task (line-mode bars for performance)
Full HTML/JS generation via string templating — no server needed at runtime
Session state management across the 3-tab UI

The Generated HTML File (the real star)
The exported file is a completely self-contained offline interactive dashboard embedding all data as JSON and Plotly.js via CDN. Its capabilities:

Filter panel: Dropdown filters by Discipline and Zone — updates chart in real time
Task selection table: Checkbox per task with Select All / Deselect All / Apply
Jump to task: Search by TaskID or TaskName, auto-scrolls the Y-axis
Dynamic date ticks: Adapts grid and tick interval (daily → weekly → bi-weekly → monthly → quarterly) based on visible timeline range — ticks align with vertical gridlines
Fit / Reset view: One-click timeline normalization
Split & Download PNGs: Splits the visible tasks into N-task batches, renders each in a hidden off-screen div, and exports sequential PNG files — critical for printing or reporting
Responsive resize: Tick recalculation on window resize


## App Architecture
Single file: app.py
├── DEFAULT_DISCIPLINE_COLORS       # Preset palette
├── _validate_required_columns()    # Input guard
├── _convert_schedule_dates()       # Date normalization
├── generate_interactive_gantt()    # Core: builds full HTML string
│   ├── Trace builder loop          # One Plotly trace per task
│   ├── Layout config (JSON)        # Axis, margins, rangeselector
│   └── HTML template               # Inlines all JSON + JS logic
└── main()                          # Streamlit UI
    ├── Tab 1: File upload + preview + validation
    ├── Tab 2: Per-discipline color pickers
    └── Tab 3: Generate + download button

## Why It's Valuable for Civil Engineering
Construction projects involve dozens of disciplines (earthworks, foundations, structural, finishing), hundreds of tasks, and stakeholders who don't have MS Project or Primavera. This app turns a simple Excel file — already the universal language on construction sites — into a shareable, interactive, printable schedule that works offline in any browser.
# SketchUp MCP Prototype

This prototype shows both halves of a local SketchUp integration:

1. A SketchUp 2017-compatible Ruby extension that polls a file queue.
2. A TypeScript MCP server that exposes SketchUp actions as MCP tools.

The design keeps the MCP server outside SketchUp, while SketchUp remains the only process that touches the SketchUp Ruby API.

## Folder layout

```text
sketchup-mcp-prototype/
  README.md
  .gitignore
  sketchup-extension/
    sketchup_mcp_bridge.rb
    sketchup_mcp_bridge/
      config.rb
      catalog.rb
      support.rb
      analysis.rb
      bridge.rb
      reporting.rb
      services.rb
      ui.rb
      templates/
        report_builder.html
        result_dialog.html
      main.rb
  server/
    package.json
    tsconfig.json
    src/
      index.ts
      fileQueueBridge.ts
      config.ts
```

## Queue contract

The bridge uses a simple file queue:

- Command files: `QUEUE_ROOT/commands/<id>.json`
- Result files: `QUEUE_ROOT/results/<id>.json`
- Failed command files: `QUEUE_ROOT/failed/<id>.json`

Command shape:

```json
{
  "id": "example-id",
  "tool": "get_model_summary",
  "args": {},
  "createdAt": "2026-04-17T10:00:00Z"
}
```

Result shape:

```json
{
  "id": "example-id",
  "ok": true,
  "data": {
    "title": "Demo Model"
  },
  "completedAt": "2026-04-17T10:00:01Z"
}
```

## SketchUp side

The SketchUp extension auto-starts a repeating timer and watches a queue folder. It supports these commands:

- `ping`
- `get_model_summary`
- `list_layers`
- `list_tags`
- `list_scenes`
- `get_selection_info`
- `list_components`
- `export_component_list`
- `get_selection_metrics`
- `filter_entities_by_tag`
- `summarize_component_quantities`
- `export_bom_report`
- `export_bilingual_site_report`
- `export_current_view_png`
- `save_model_copy`
- `create_demo_group`
- `show_component_quantities_dialog`
- `show_selection_metrics_dialog`
- `show_component_list_dialog`
- `show_report_builder_dialog`
- `show_tag_totals_dialog`

### Install the extension

Copy these two items into your SketchUp `Plugins` folder:

- `sketchup_mcp_bridge.rb`
- `sketchup_mcp_bridge/`

For SketchUp 2017 on Windows this is typically:

```text
C:\Users\<you>\AppData\Roaming\SketchUp\SketchUp 2017\SketchUp\Plugins
```

### Configure the queue folder

By default the extension uses:

```text
%LOCALAPPDATA%\SketchUpMCPBridge
```

If you want a fixed path, edit `QUEUE_ROOT` in `sketchup-extension/sketchup_mcp_bridge/config.rb`.

### SketchUp menu commands

After SketchUp loads the extension, look under:

```text
Extensions > SketchUp MCP Bridge
```

Available actions:

- Show queue root
- Bridge status
- Process queue now
- GOBeam X Span

## MCP server side

The TypeScript server exposes MCP tools over `stdio`, which is the standard transport for local MCP servers.

### Install

```bash
cd sketchup-mcp-prototype/server
npm install
```

### Build

```bash
npm run build
```

### Run

```bash
npm start
```

Or for development:

```bash
npm run dev
```

### Environment variables

- `SKETCHUP_MCP_QUEUE_ROOT`
  Defaults to `%LOCALAPPDATA%\SketchUpMCPBridge` on Windows.
- `SKETCHUP_MCP_TIMEOUT_MS`
  Defaults to `15000`.
- `SKETCHUP_MCP_POLL_MS`
  Defaults to `250`.

## Example MCP client config

Example for a local MCP client that starts the server with stdio:

```json
{
  "mcpServers": {
    "sketchup-local": {
      "command": "node",
      "args": [
        "C:/Users/g_np2/OneDrive/Programe/sketchup-mcp-prototype/server/dist/index.js"
      ],
      "env": {
        "SKETCHUP_MCP_QUEUE_ROOT": "C:/Users/g_np2/AppData/Local/SketchUpMCPBridge"
      }
    }
  }
}
```

## Notes

- SketchUp Ruby API calls must happen inside SketchUp, on the SketchUp side.
- This prototype uses a queue instead of sockets because it is simple and reliable on SketchUp 2017.
- For production, add stronger locking, write confirmations, and audit logging.

## Ruby architecture

The SketchUp bridge is now split into small modules so new features can be added without growing one giant file:

- `config.rb`
  Constants, queue paths, unit conversions, density presets, and report presets.
- `catalog.rb`
  Data-driven metadata for presets, views, density option labels, and bilingual field labels.
- `support.rb`
  Shared helpers for parsing, formatting, export helpers, density resolution, and queue writes.
- `analysis.rb`
  Entity inspection, filtering, dimensions, surface area, volume, and metric extraction.
- `gobeam.rb`
  Continuous beam analysis for GOBeam X Span, including span/load validation, stiffness analysis, Save/Load JSON, and printable HTML reports.
- `bridge.rb`
  Queue polling, tool dispatch, startup, and menu wiring.
- `reporting.rb`
  Read-only reporting tools, aggregation, BOM exports, and tag totals.
- `services.rb`
  View routing and report orchestration used by the dialogs and future automation hooks.
- `ui.rb`
  SketchUp dialogs and template-driven rendering.
- `templates/`
  HTML templates for the report builder, result dialogs, GOBeam dialog, and GOBeam report.
- `main.rb`
  Thin bootstrap that wires the modules together and starts the bridge.

## GOBeam X Span

Open the tool from:

```text
Extensions > SketchUp MCP Bridge > GOBeam X Span
```

GOBeam X Span analyzes a continuous beam with unlimited spans using a rotational stiffness model with simple supports at each node. It supports per-span length, uniform load, point loads, and EI, then displays the loading sketch, shear diagram, bending moment diagram, and deflection diagram.

Use `Save` and `Load` to round-trip `.gobeam.json` project files. Use `Report` to open a printable HTML report; the report uses print page breaks so long beams can flow across as many pages as needed.

The dialog and exports now use bilingual labels from the shared catalog so UI text and column headers stay consistent.

## Practical model tools

The prototype now includes a set of tools that are more useful on real project models:

- `list_components`
  Returns component and group instances with name, definition, tag, dimensions, volume, material, and nesting path.
- `export_component_list`
  Writes a component inventory to `.csv` or `.json` depending on the output file extension.
- `get_selection_metrics`
  Summarizes dimensions and volume for the current selection and also returns the total selection volume.
- `filter_entities_by_tag`
  Returns entities that match one or more tags.
- `summarize_component_quantities`
  Aggregates quantities for fabrication-style takeoffs, with grouping by fields such as `definitionName`, `tag`, `material`, or `type`.
- `export_bom_report`
  Writes an aggregated BOM report to `.csv` or `.json`.
- `summarize_tag_totals`
  Aggregates totals by tag with quantity, average dimensions, total volume, total surface area, and total estimated weight.
- `export_tag_totals_report`
  Exports the tag-based summary to `.csv`, `.json`, or Excel XML (`.xls` / `.xml`).
- `summarize_edge_metrics`
  Aggregates edge counts and lengths by tag, including short edges, loose edges, hidden edges, and smoothing flags.
- `export_edge_metrics_report`
  Exports the edge metrics summary to `.csv`, `.json`, or Excel XML.
- `summarize_component_categories`
  Groups components into practical categories such as doors, windows, beams, columns, footings, walls, slabs, and generic items.
- `export_component_categories_report`
  Exports the category summary to `.csv`, `.json`, or Excel XML.
- `summarize_model_audit`
  Produces a model-check summary focused on raw top-level geometry, short edges, loose edges, Layer0 usage, unnamed groups, and non-solid items.
- `export_model_audit_report`
  Exports the model audit to `.json`, `.csv`, or a multi-sheet Excel XML workbook with summary, top-level geometry, issues, and category sheets.
- `summarize_boq_thai`
  Builds a Thai BOQ summary from model takeoff data, matching components/groups to editable global price rules plus project overrides and separating material and labor costs.
- `export_boq_thai_report`
  Exports a BOQ THAI workbook. The MCP server writes real `.xlsx`; the SketchUp Ruby side can preview HTML and export `.csv`, `.json`, or Excel XML (`.xls` / `.xml`).
- `export_boq_unmatched_template`
  Exports unmatched model items as a CSV rule template so an estimator can complete mapping and pricing.
- `append_boq_project_override`
  Adds or replaces one project-level BOQ rule in the project override CSV.
- `export_bilingual_site_report`
  Builds a multi-sheet Excel workbook for site use with Thai/English headers.

### Tag compatibility

SketchUp 2017 still uses layers internally, but the MCP layer accepts `tag_filter` so the same workflow can be reused later on newer SketchUp versions.

### Shared filters

Most component-oriented tools now accept these filters:

- `preset`
- `tag_filter`
- `exclude_tag_filter`
- `name_filter`
- `material_filter`
- `definition_filter`
- `min_depth`
- `max_depth`
- `solid_only`
- `include_groups`
- `selected_only`
- `density_preset`
- `density_kg_m3`

This makes it possible to reuse the same query pattern for inventory, BOM export, and selection analysis.

Additional edge-check filters:

- `include_hidden`
- `short_edge_threshold_mm`

Additional presentation filter:

- `locale`
  Supported values: `th`, `en`, `bilingual`

### Units

The dialog and reports now expose explicit metric fields:

- `lengthM`, `widthM`, `heightM`
- `surfaceAreaM2`
- `volumeM3`
- `estimatedWeightKg`

The compact `dimensions` text is a bounding-box summary in millimeters. Raw internal SketchUp values are still kept in some JSON fields for compatibility, but the reporting fields above are the ones intended for actual use.

## Model checking additions

The report builder now supports extra views for model inspection:

- `Categories / หมวดชิ้นงาน`
- `Edge Metrics / ตรวจเส้น`
- `Model Audit / ตรวจเช็กโมเดล`

These are intended to help with:

- spotting short or loose edges before cleanup
- finding raw top-level geometry that should be grouped
- reviewing default-tag usage (`Layer0`)
- separating doors, windows, structural items, and generic model objects
- catching unnamed or untagged door/window objects
- flagging large generic objects that should probably be categorized more clearly

### Presets

Built-in presets:

- `beam`
- `column`
- `footing`

These presets automatically:

- target the matching structural tag
- exclude `GRID LINE` and `DIMENSIONS`
- set `solid_only=true`
- default density to `reinforced_concrete`

If no density is specified, the bridge can also infer density automatically from material, tag, name, and definition keywords. Current auto matches include `steel`, `rc`, `beam`, `column`, `footing`, `concrete`, `timber`, and `aluminum`.

### Site workbook output

`export_bilingual_site_report` writes a `.xlsx` workbook with separate sheets:

- `01_Summary`
- `02_Inventory`
- `03_BOM`
- `04_Tags`
- `05_Selection`
- `06_Steel`
- `07_Rigging`
- `08_Lifting`

The workbook includes:

- Thai/English column headers
- density-based estimated weights
- categorized sheets for steel, rigging, and lifting-point style items
- BOM grouping by fields such as `definitionName`, `tag`, and `material`
- optional `density_overrides` for project-specific materials

### Typical examples

- Export all components on the `STEEL` tag to a CSV file
- List selected component instances with dimensions and volume
- Filter the model to find all entities on `LIFTING`, `RIGGING`, or `TEMP`
- Build a quick inventory of grouped fabrication items
- Build a BOM grouped by `definitionName,tag,material`
- Export only solid steel components up to nested depth `2`
- Export a bilingual `.xlsx` report for site review and fabrication handoff
- Estimate concrete or steel weight directly from volume using `density_preset`
- Generate a Thai BOQ with material/labor split from editable price rules

### SketchUp dialog helpers

If reading JSON in the Ruby Console feels awkward, use these dialog helpers:

```ruby
Codex::SketchUpMCPBridge.show_component_quantities_dialog(
  'exclude_tag_filter' => ['GRID LINE', 'DIMENSIONS'],
  'solid_only' => true,
  'density_preset' => 'reinforced_concrete'
)
```

```ruby
Codex::SketchUpMCPBridge.show_selection_metrics_dialog(
  'density_preset' => 'steel'
)
```

```ruby
Codex::SketchUpMCPBridge.show_component_list_dialog(
  'tag_filter' => ['Structure-RC_BEAM'],
  'exclude_tag_filter' => ['GRID LINE', 'DIMENSIONS']
)
```

```ruby
Codex::SketchUpMCPBridge.show_preset_quantities_dialog('beam')
```

```ruby
Codex::SketchUpMCPBridge.show_tag_totals_dialog(
  'exclude_tag_filter' => ['GRID LINE', 'DIMENSIONS'],
  'density_preset' => 'reinforced_concrete'
)
```

```ruby
Codex::SketchUpMCPBridge.show_report_builder_dialog
```

```ruby
Codex::SketchUpMCPBridge.show_boq_thai_dialog
```

### BOQ THAI price rules

Use `sketchup-extension/sketchup_mcp_bridge/templates/boq_thai_price_rules.csv` as a starting template. The supported columns are:

```text
enabled, priority, rule_id, match_type, match_value, category, item_code, description_th, unit,
quantity_source, material_unit_cost, labor_unit_cost, waste_percent, note
```

Supported `quantity_source` values include `volumeM3`, `surfaceAreaM2`, `lengthM`, `count`, and `estimatedWeightKg`. The `.xlsx` exporter creates sheets for `01_BOQ_THAI`, `02_Raw_Takeoff`, `03_Price_Rules`, `04_Unmatched_Items`, and `05_Model_Audit`.

Use `Extensions > SketchUp MCP Bridge > Open BOQ Thai Manager` for the estimator workflow. It lets you choose a global price library, save project override rules, review unmatched items, and export unmatched-rule templates without working in the Ruby Console.

The report builder dialog includes:

- preset buttons for `Beam`, `Column`, `Footing`
- filters for `tag` and `name`
- automatic exclusion for `GRID LINE` and `DIMENSIONS`
- export buttons for CSV and Excel XML

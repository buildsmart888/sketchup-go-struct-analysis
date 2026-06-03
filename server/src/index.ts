import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { FileQueueBridge } from "./fileQueueBridge.js";
import { config } from "./config.js";
import { exportBilingualSiteReport } from "./reporting.js";
import { exportBoqThaiWorkbook, loadBoqThaiRules } from "./boqThai.js";
import type { ComponentRecord, ModelSummary, QuantitySummaryRow, SelectionMetric, TagInfo } from "./types.js";

const bridge = new FileQueueBridge();

const server = new McpServer({
  name: "sketchup-local-bridge",
  version: "0.1.0",
});

function resultToText(result: unknown): string {
  return JSON.stringify(result, null, 2);
}

async function callSketchUpTool(
  tool: string,
  args: Record<string, string | number | boolean | null | string[] | number[]>,
): Promise<{ content: Array<{ type: "text"; text: string }>; isError?: true }> {
  const result = await bridge.call(tool, args);
  if (!result.ok) {
    return {
      content: [
        {
          type: "text",
          text: result.error,
        },
      ],
      isError: true,
    };
  }

  return {
    content: [
      {
        type: "text",
        text: resultToText(result.data),
      },
    ],
  };
}

async function callBridgeData<T>(
  tool: string,
  args: Record<string, string | number | boolean | null | string[] | number[]> = {},
): Promise<T> {
  const result = await bridge.call<T>(tool, args);
  if (!result.ok) {
    throw new Error(result.error);
  }
  return result.data;
}

server.tool("ping_sketchup_bridge", {}, async () => {
  return callSketchUpTool("ping", {});
});

server.tool("get_model_summary", {}, async () => {
  return callSketchUpTool("get_model_summary", {});
});

server.tool("list_layers", {}, async () => {
  return callSketchUpTool("list_layers", {});
});

server.tool("list_tags", {}, async () => {
  return callSketchUpTool("list_tags", {});
});

server.tool("list_scenes", {}, async () => {
  return callSketchUpTool("list_scenes", {});
});

server.tool("get_selection_info", {}, async () => {
  return callSketchUpTool("get_selection_info", {});
});

server.tool(
  "list_components",
  {
    include_groups: z.boolean().optional(),
    selected_only: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    include_groups,
    selected_only,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("list_components", {
      include_groups: include_groups ?? null,
      selected_only: selected_only ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "export_component_list",
  {
    path: z.string().describe("Absolute output path for CSV or JSON."),
    include_groups: z.boolean().optional(),
    selected_only: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    path,
    include_groups,
    selected_only,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("export_component_list", {
      path,
      include_groups: include_groups ?? null,
      selected_only: selected_only ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "get_selection_metrics",
  {
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    include_non_solids: z.boolean().optional(),
    preset: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    tag_filter,
    exclude_tag_filter,
    include_non_solids,
    preset,
    material_filter,
    definition_filter,
    name_filter,
    min_depth,
    max_depth,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("get_selection_metrics", {
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      include_non_solids: include_non_solids ?? null,
      preset: preset ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      name_filter: name_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "filter_entities_by_tag",
  {
    tag_filter: z.union([z.string(), z.array(z.string())]),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    include_groups: z.boolean().optional(),
    selected_only: z.boolean().optional(),
    preset: z.string().optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    tag_filter,
    exclude_tag_filter,
    include_groups,
    selected_only,
    preset,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("filter_entities_by_tag", {
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      include_groups: include_groups ?? null,
      selected_only: selected_only ?? null,
      preset: preset ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "summarize_component_quantities",
  {
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    group_by: z.union([z.string(), z.array(z.string())]).optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    group_by,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("summarize_component_quantities", {
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      group_by: Array.isArray(group_by) ? group_by : group_by ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "export_bom_report",
  {
    path: z.string().describe("Absolute output path for CSV or JSON."),
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    group_by: z.union([z.string(), z.array(z.string())]).optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    path,
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    group_by,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("export_bom_report", {
      path,
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      group_by: Array.isArray(group_by) ? group_by : group_by ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "summarize_tag_totals",
  {
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("summarize_tag_totals", {
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "export_tag_totals_report",
  {
    path: z.string().describe("Absolute output path for CSV, JSON, or Excel XML."),
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    path,
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("export_tag_totals_report", {
      path,
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "summarize_edge_metrics",
  {
    selected_only: z.boolean().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    include_hidden: z.boolean().optional(),
    short_edge_threshold_mm: z.number().positive().optional(),
  },
  async ({ selected_only, tag_filter, exclude_tag_filter, name_filter, include_hidden, short_edge_threshold_mm }) => {
    return callSketchUpTool("summarize_edge_metrics", {
      selected_only: selected_only ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      include_hidden: include_hidden ?? null,
      short_edge_threshold_mm: short_edge_threshold_mm ?? null,
    });
  },
);

server.tool(
  "export_edge_metrics_report",
  {
    path: z.string().describe("Absolute output path for CSV, JSON, or Excel XML."),
    selected_only: z.boolean().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    include_hidden: z.boolean().optional(),
    short_edge_threshold_mm: z.number().positive().optional(),
  },
  async ({ path, selected_only, tag_filter, exclude_tag_filter, name_filter, include_hidden, short_edge_threshold_mm }) => {
    return callSketchUpTool("export_edge_metrics_report", {
      path,
      selected_only: selected_only ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      include_hidden: include_hidden ?? null,
      short_edge_threshold_mm: short_edge_threshold_mm ?? null,
    });
  },
);

server.tool(
  "summarize_component_categories",
  {
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("summarize_component_categories", {
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "export_component_categories_report",
  {
    path: z.string().describe("Absolute output path for CSV, JSON, or Excel XML."),
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    path,
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
  }) => {
    return callSketchUpTool("export_component_categories_report", {
      path,
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    });
  },
);

server.tool(
  "summarize_model_audit",
  {
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    include_hidden: z.boolean().optional(),
    short_edge_threshold_mm: z.number().positive().optional(),
  },
  async ({
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    include_hidden,
    short_edge_threshold_mm,
  }) => {
    return callSketchUpTool("summarize_model_audit", {
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      include_hidden: include_hidden ?? null,
      short_edge_threshold_mm: short_edge_threshold_mm ?? null,
    });
  },
);

server.tool(
  "export_model_audit_report",
  {
    path: z.string().describe("Absolute output path for CSV, JSON, or Excel XML."),
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    include_hidden: z.boolean().optional(),
    short_edge_threshold_mm: z.number().positive().optional(),
    locale: z.string().optional(),
  },
  async ({
    path,
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    include_hidden,
    short_edge_threshold_mm,
    locale,
  }) => {
    return callSketchUpTool("export_model_audit_report", {
      path,
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      include_hidden: include_hidden ?? null,
      short_edge_threshold_mm: short_edge_threshold_mm ?? null,
      locale: locale ?? null,
    });
  },
);

server.tool(
  "summarize_boq_thai",
  {
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
    price_rules_path: z.string().optional().describe("Optional CSV price rules path for SketchUp-side preview."),
    global_price_rules_path: z.string().optional().describe("Optional global CSV price rules path."),
    project_overrides_path: z.string().optional().describe("Optional project override CSV path."),
  },
  async ({
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
    price_rules_path,
    global_price_rules_path,
    project_overrides_path,
  }) => {
    return callSketchUpTool("summarize_boq_thai", {
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
      price_rules_path: price_rules_path ?? null,
      global_price_rules_path: global_price_rules_path ?? null,
      project_overrides_path: project_overrides_path ?? null,
    });
  },
);

server.tool(
  "export_boq_thai_report",
  {
    path: z.string().describe("Absolute output .xlsx path for the BOQ THAI workbook."),
    price_rules_path: z.string().optional().describe("Optional .csv or .xlsx price rules path."),
    global_price_rules_path: z.string().optional().describe("Optional global .csv or .xlsx price rules path."),
    project_overrides_path: z.string().optional().describe("Optional project override .csv or .xlsx path."),
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    preset: z.string().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    exclude_tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    density_preset: z.string().optional(),
    density_kg_m3: z.number().positive().optional(),
  },
  async ({
    path,
    price_rules_path,
    global_price_rules_path,
    project_overrides_path,
    selected_only,
    include_groups,
    preset,
    tag_filter,
    exclude_tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    density_preset,
    density_kg_m3,
  }) => {
    const commonArgs = {
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      preset: preset ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      exclude_tag_filter: Array.isArray(exclude_tag_filter) ? exclude_tag_filter : exclude_tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
      density_preset: density_preset ?? null,
      density_kg_m3: density_kg_m3 ?? null,
    };

    const inventoryResponse = await callBridgeData<{ items: ComponentRecord[] }>("list_components", commonArgs);
    const auditResponse = await callBridgeData<{ issues: Array<Record<string, unknown>> }>("summarize_model_audit", commonArgs);
    const rules = await loadBoqThaiRules(global_price_rules_path ?? price_rules_path, project_overrides_path);
    const report = await exportBoqThaiWorkbook({
      outputPath: path,
      records: inventoryResponse.items,
      rules,
      auditIssues: auditResponse.issues,
    });

    return {
      content: [
        {
          type: "text",
          text: resultToText(report),
        },
      ],
    };
  },
);

server.tool(
  "export_boq_unmatched_template",
  {
    path: z.string().describe("Absolute output CSV path for unmatched BOQ rule suggestions."),
    price_rules_path: z.string().optional(),
    global_price_rules_path: z.string().optional(),
    project_overrides_path: z.string().optional(),
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    solid_only: z.boolean().optional(),
  },
  async ({
    path,
    price_rules_path,
    global_price_rules_path,
    project_overrides_path,
    selected_only,
    include_groups,
    tag_filter,
    name_filter,
    solid_only,
  }) => {
    return callSketchUpTool("export_boq_unmatched_template", {
      path,
      price_rules_path: price_rules_path ?? null,
      global_price_rules_path: global_price_rules_path ?? null,
      project_overrides_path: project_overrides_path ?? null,
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      name_filter: name_filter ?? null,
      solid_only: solid_only ?? null,
    });
  },
);

server.tool(
  "append_boq_project_override",
  {
    project_overrides_path: z.string().optional(),
    enabled: z.union([z.string(), z.boolean()]).optional(),
    priority: z.number().optional(),
    rule_id: z.string(),
    match_type: z.string(),
    match_value: z.string(),
    category: z.string().optional(),
    item_code: z.string().optional(),
    description_th: z.string().optional(),
    unit: z.string().optional(),
    quantity_source: z.string().optional(),
    material_unit_cost: z.number().optional(),
    labor_unit_cost: z.number().optional(),
    waste_percent: z.number().optional(),
    note: z.string().optional(),
  },
  async ({
    project_overrides_path,
    enabled,
    priority,
    rule_id,
    match_type,
    match_value,
    category,
    item_code,
    description_th,
    unit,
    quantity_source,
    material_unit_cost,
    labor_unit_cost,
    waste_percent,
    note,
  }) => {
    return callSketchUpTool("append_boq_project_override", {
      project_overrides_path: project_overrides_path ?? null,
      enabled: typeof enabled === "boolean" ? String(enabled) : enabled ?? null,
      priority: priority ?? null,
      rule_id,
      match_type,
      match_value,
      category: category ?? null,
      item_code: item_code ?? null,
      description_th: description_th ?? null,
      unit: unit ?? null,
      quantity_source: quantity_source ?? null,
      material_unit_cost: material_unit_cost ?? null,
      labor_unit_cost: labor_unit_cost ?? null,
      waste_percent: waste_percent ?? null,
      note: note ?? null,
    });
  },
);

server.tool(
  "export_current_view_png",
  {
    path: z.string().describe("Absolute output PNG path on the local machine."),
    width: z.number().int().positive().optional(),
    height: z.number().int().positive().optional(),
  },
  async ({ path, width, height }) => {
    return callSketchUpTool("export_current_view_png", { path, width: width ?? null, height: height ?? null });
  },
);

server.tool(
  "save_model_copy",
  {
    path: z.string().describe("Absolute output SKP path for the copy."),
  },
  async ({ path }) => {
    return callSketchUpTool("save_model_copy", { path });
  },
);

server.tool(
  "create_demo_group",
  {
    size: z.number().positive().optional().describe("Cube edge length in SketchUp model units."),
    origin: z
      .array(z.number())
      .length(3)
      .optional()
      .describe("Origin point as [x, y, z]."),
  },
  async ({ size, origin }) => {
    return callSketchUpTool("create_demo_group", {
      size: size ?? null,
      origin: origin ?? null,
    });
  },
);

server.tool("bridge_info", {}, async () => {
  return {
    content: [
      {
        type: "text",
        text: resultToText({
          queueRoot: config.queueRoot,
          timeoutMs: config.timeoutMs,
          pollMs: config.pollMs,
        }),
      },
    ],
  };
});

server.tool(
  "export_bilingual_site_report",
  {
    path: z.string().describe("Absolute output .xlsx path for the workbook."),
    report_title: z.string().optional(),
    report_subtitle: z.string().optional(),
    selected_only: z.boolean().optional(),
    include_groups: z.boolean().optional(),
    tag_filter: z.union([z.string(), z.array(z.string())]).optional(),
    name_filter: z.string().optional(),
    material_filter: z.union([z.string(), z.array(z.string())]).optional(),
    definition_filter: z.union([z.string(), z.array(z.string())]).optional(),
    min_depth: z.number().int().min(0).optional(),
    max_depth: z.number().int().min(0).optional(),
    solid_only: z.boolean().optional(),
    group_by: z.union([z.string(), z.array(z.string())]).optional(),
    density_overrides: z.record(z.number()).optional(),
  },
  async ({
    path,
    report_title,
    report_subtitle,
    selected_only,
    include_groups,
    tag_filter,
    name_filter,
    material_filter,
    definition_filter,
    min_depth,
    max_depth,
    solid_only,
    group_by,
    density_overrides,
  }) => {
    const commonArgs = {
      selected_only: selected_only ?? null,
      include_groups: include_groups ?? null,
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      solid_only: solid_only ?? null,
    };

    const groupBy = Array.isArray(group_by)
      ? group_by
      : typeof group_by === "string"
        ? group_by.split(",").map((value) => value.trim()).filter(Boolean)
        : ["definitionName", "tag", "material"];

    const modelSummary = await callBridgeData<ModelSummary>("get_model_summary");
    const tags = await callBridgeData<TagInfo[]>("list_tags");
    const inventoryResponse = await callBridgeData<{ items: ComponentRecord[] }>("list_components", commonArgs);
    const bomResponse = await callBridgeData<{ rows: QuantitySummaryRow[] }>("summarize_component_quantities", {
      ...commonArgs,
      group_by: groupBy,
    });
    const selectionResponse = await callBridgeData<{ items: SelectionMetric[] }>("get_selection_metrics", {
      tag_filter: Array.isArray(tag_filter) ? tag_filter : tag_filter ?? null,
      name_filter: name_filter ?? null,
      material_filter: Array.isArray(material_filter) ? material_filter : material_filter ?? null,
      definition_filter: Array.isArray(definition_filter) ? definition_filter : definition_filter ?? null,
      min_depth: min_depth ?? null,
      max_depth: max_depth ?? null,
      include_non_solids: solid_only ? false : true,
    });

    const report = await exportBilingualSiteReport({
      modelSummary,
      tags,
      inventory: inventoryResponse.items,
      bom: bomResponse.rows,
      selection: selectionResponse.items,
      options: {
        outputPath: path,
        reportTitle: report_title,
        reportSubtitle: report_subtitle,
        groupBy,
        densityOverrides: density_overrides,
      },
    });

    return {
      content: [
        {
          type: "text",
          text: resultToText(report),
        },
      ],
    };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);

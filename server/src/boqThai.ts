import fs from "node:fs/promises";
import path from "node:path";
import ExcelJS from "exceljs";
import type { ComponentRecord } from "./types.js";

export interface BoqThaiRule {
  enabled?: string | boolean;
  priority?: number;
  rule_id: string;
  match_type: string;
  match_value: string;
  category: string;
  item_code: string;
  description_th: string;
  unit: string;
  quantity_source: string;
  material_unit_cost: number;
  labor_unit_cost: number;
  waste_percent: number;
  note: string;
}

interface BoqThaiRow {
  no: number;
  category: string;
  item_code: string;
  description_th: string;
  unit: string;
  quantity: number;
  material_unit_cost: number;
  material_amount: number;
  labor_unit_cost: number;
  labor_amount: number;
  total_amount: number;
  source: string;
  note: string;
}

interface UnmatchedItem {
  entityID: number;
  name: string;
  definitionName: string;
  category: string;
  tag: string;
  material: string;
  quantity_hint: string;
  reason: string;
}

const RULE_HEADERS = [
  "enabled",
  "priority",
  "rule_id",
  "match_type",
  "match_value",
  "category",
  "item_code",
  "description_th",
  "unit",
  "quantity_source",
  "material_unit_cost",
  "labor_unit_cost",
  "waste_percent",
  "note",
] as const;

const DEFAULT_RULES: BoqThaiRule[] = [
  ["RC_BEAM", "category", "beam", "Structural", "STR-RC-BEAM", "RC beam", "m3", "volumeM3"],
  ["RC_COLUMN", "category", "column", "Structural", "STR-RC-COLUMN", "RC column", "m3", "volumeM3"],
  ["RC_FOOTING", "category", "footing", "Structural", "STR-RC-FOOTING", "RC footing", "m3", "volumeM3"],
  ["WALL", "category", "wall", "Wall", "ARC-WALL", "Wall", "m2", "surfaceAreaM2"],
  ["SLAB", "category", "slab", "Floor", "STR-SLAB", "Slab/floor", "m2", "surfaceAreaM2"],
  ["ROOF", "category", "roof", "Roof", "ARC-ROOF", "Roof", "m2", "surfaceAreaM2"],
  ["DOOR", "category", "door", "Opening", "ARC-DOOR", "Door", "set", "count"],
  ["WINDOW", "category", "window", "Opening", "ARC-WINDOW", "Window", "set", "count"],
  ["STEEL", "keyword", "steel", "Steel", "STR-STEEL", "Structural steel", "kg", "estimatedWeightKg"],
].map(([rule_id, match_type, match_value, category, item_code, description_th, unit, quantity_source]) => ({
  enabled: true,
  priority: 0,
  rule_id,
  match_type,
  match_value,
  category,
  item_code,
  description_th,
  unit,
  quantity_source,
  material_unit_cost: 0,
  labor_unit_cost: 0,
  waste_percent: 0,
  note: "Set material and labor cost in price rules",
}));

function text(value: unknown): string {
  return String(value ?? "").trim();
}

function lower(value: unknown): string {
  return text(value).toLowerCase();
}

function num(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function round(value: number, digits = 2): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"' && line[index + 1] === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      values.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  values.push(current);
  return values;
}

function normalizeRule(row: Record<string, unknown>): BoqThaiRule {
  return {
    enabled: text(row.enabled) || true,
    priority: num(row.priority),
    rule_id: text(row.rule_id),
    match_type: text(row.match_type) || "keyword",
    match_value: text(row.match_value),
    category: text(row.category) || "Unspecified",
    item_code: text(row.item_code) || text(row.rule_id),
    description_th: text(row.description_th) || "Unspecified item",
    unit: text(row.unit) || "set",
    quantity_source: text(row.quantity_source) || "count",
    material_unit_cost: num(row.material_unit_cost),
    labor_unit_cost: num(row.labor_unit_cost),
    waste_percent: num(row.waste_percent),
    note: text(row.note),
  };
}

async function readCsvRules(filePath: string): Promise<BoqThaiRule[]> {
  const raw = await fs.readFile(filePath, "utf8");
  const lines = raw.replace(/^\uFEFF/, "").split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length < 2) {
    return [];
  }
  const headers = splitCsvLine(lines[0]).map(text);
  return lines.slice(1).map((line) => {
    const values = splitCsvLine(line);
    const row: Record<string, unknown> = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });
    return normalizeRule(row);
  });
}

async function readXlsxRules(filePath: string): Promise<BoqThaiRule[]> {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(filePath);
  const worksheet = workbook.worksheets[0];
  if (!worksheet) {
    return [];
  }
  const headers = (worksheet.getRow(1).values as unknown[]).slice(1).map(text);
  const rules: BoqThaiRule[] = [];
  worksheet.eachRow((row, rowNumber) => {
    if (rowNumber === 1) {
      return;
    }
    const values = (row.values as unknown[]).slice(1);
    const raw: Record<string, unknown> = {};
    headers.forEach((header, index) => {
      raw[header] = values[index] ?? "";
    });
    if (Object.values(raw).some((value) => text(value))) {
      rules.push(normalizeRule(raw));
    }
  });
  return rules;
}

async function readRulesIfPresent(priceRulesPath?: string): Promise<BoqThaiRule[]> {
  if (!priceRulesPath) {
    return [];
  }
  try {
    await fs.access(priceRulesPath);
    const ext = path.extname(priceRulesPath).toLowerCase();
    return ext === ".xlsx" ? await readXlsxRules(priceRulesPath) : await readCsvRules(priceRulesPath);
  } catch {
    return [];
  }
}

function enabled(rule: BoqThaiRule): boolean {
  const value = text(rule.enabled).toLowerCase();
  return value === "" || ["1", "true", "yes", "on"].includes(value);
}

export async function loadBoqThaiRules(priceRulesPath?: string, projectOverridesPath?: string): Promise<BoqThaiRule[]> {
  const projectRules = await readRulesIfPresent(projectOverridesPath);
  const globalRules = await readRulesIfPresent(priceRulesPath);
  const rules = [
    ...projectRules.map((rule) => ({ ...rule, priority: (rule.priority ?? 0) + 2000 })),
    ...globalRules.map((rule) => ({ ...rule, priority: (rule.priority ?? 0) + 1000 })),
    ...DEFAULT_RULES,
  ].filter(enabled);
  const seen = new Set<string>();
  return rules
    .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))
    .filter((rule) => {
      const key = rule.rule_id || `${rule.match_type}|${rule.match_value}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
}

function recordCategory(record: ComponentRecord): string {
  return text(record.category);
}

function recordHaystack(record: ComponentRecord): string {
  return [
    record.tag,
    record.material,
    record.definitionName,
    record.name,
    recordCategory(record),
    ...(Array.isArray(record.path) ? record.path : []),
  ].map(lower).join(" | ");
}

function ruleMatches(rule: BoqThaiRule, record: ComponentRecord): boolean {
  const matchType = lower(rule.match_type);
  const matchValue = lower(rule.match_value);
  if (matchType === "any") {
    return true;
  }
  if (!matchValue) {
    return false;
  }
  if (matchType === "tag") {
    return lower(record.tag) === matchValue;
  }
  if (matchType === "material") {
    return lower(record.material).includes(matchValue);
  }
  if (matchType === "definition" || matchType === "definitionname") {
    return lower(record.definitionName).includes(matchValue);
  }
  if (matchType === "category") {
    return lower(recordCategory(record)) === matchValue;
  }
  if (matchType === "name") {
    return lower(record.name).includes(matchValue);
  }
  return recordHaystack(record).includes(matchValue);
}

function quantityFor(record: ComponentRecord, source: string): number {
  if (source === "count") {
    return 1;
  }
  const value = (record as unknown as Record<string, unknown>)[source];
  return num(value);
}

function sourceName(record: ComponentRecord): string {
  return [record.tag, record.definitionName, record.name].map(text).filter(Boolean).join(" / ");
}

function quantityHint(record: ComponentRecord): string {
  for (const key of ["volumeM3", "surfaceAreaM2", "lengthM", "estimatedWeightKg"]) {
    const value = num((record as unknown as Record<string, unknown>)[key]);
    if (value > 0) {
      return `${key}: ${round(value, 3)}`;
    }
  }
  return "count: 1";
}

export function buildBoqThai(records: ComponentRecord[], rules: BoqThaiRule[]): {
  rows: BoqThaiRow[];
  unmatchedItems: UnmatchedItem[];
  totals: { materialAmount: number; laborAmount: number; totalAmount: number; unmatchedCount: number };
} {
  const buckets = new Map<string, { rule: BoqThaiRule; quantity: number; sources: Set<string> }>();
  const unmatchedItems: UnmatchedItem[] = [];

  for (const record of records) {
    const rule = rules.find((candidate) => ruleMatches(candidate, record));
    if (!rule) {
      unmatchedItems.push({
        entityID: record.entityID,
        name: record.name,
        definitionName: record.definitionName,
        category: recordCategory(record),
        tag: record.tag,
        material: text(record.material),
        quantity_hint: quantityHint(record),
        reason: "No matching price rule",
      });
      continue;
    }

    const quantity = quantityFor(record, rule.quantity_source);
    if (quantity <= 0) {
      unmatchedItems.push({
        entityID: record.entityID,
        name: record.name,
        definitionName: record.definitionName,
        category: recordCategory(record),
        tag: record.tag,
        material: text(record.material),
        quantity_hint: quantityHint(record),
        reason: `No usable quantity for ${rule.quantity_source}`,
      });
      continue;
    }

    const key = rule.rule_id || rule.item_code;
    const bucket = buckets.get(key) ?? { rule, quantity: 0, sources: new Set<string>() };
    bucket.quantity += quantity;
    bucket.sources.add(sourceName(record));
    buckets.set(key, bucket);
  }

  const rows = Array.from(buckets.values()).map((bucket, index) => {
    const materialAmount = bucket.quantity * bucket.rule.material_unit_cost * (1 + bucket.rule.waste_percent / 100);
    const laborAmount = bucket.quantity * bucket.rule.labor_unit_cost;
    return {
      no: index + 1,
      category: bucket.rule.category,
      item_code: bucket.rule.item_code,
      description_th: bucket.rule.description_th,
      unit: bucket.rule.unit,
      quantity: round(bucket.quantity, 3),
      material_unit_cost: round(bucket.rule.material_unit_cost),
      material_amount: round(materialAmount),
      labor_unit_cost: round(bucket.rule.labor_unit_cost),
      labor_amount: round(laborAmount),
      total_amount: round(materialAmount + laborAmount),
      source: Array.from(bucket.sources).filter(Boolean).slice(0, 10).join(" | "),
      note: bucket.rule.note,
    };
  });

  return {
    rows,
    unmatchedItems,
    totals: {
      materialAmount: round(rows.reduce((sum, row) => sum + row.material_amount, 0)),
      laborAmount: round(rows.reduce((sum, row) => sum + row.labor_amount, 0)),
      totalAmount: round(rows.reduce((sum, row) => sum + row.total_amount, 0)),
      unmatchedCount: unmatchedItems.length,
    },
  };
}

function addSheet(
  workbook: ExcelJS.Workbook,
  name: string,
  columns: Array<{ key: string; header: string; width?: number }>,
  rows: Array<Record<string, unknown>>,
): void {
  const worksheet = workbook.addWorksheet(name);
  worksheet.columns = columns.map((column) => ({ ...column, width: column.width ?? 18 }));
  worksheet.getRow(1).font = { bold: true };
  worksheet.getRow(1).alignment = { vertical: "middle", horizontal: "center", wrapText: true };
  worksheet.getRow(1).fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFD9EAF7" } };
  rows.forEach((row) => worksheet.addRow(row));
  worksheet.views = [{ state: "frozen", ySplit: 1 }];
  worksheet.autoFilter = { from: "A1", to: `${worksheet.getColumn(columns.length).letter}1` };
}

export async function exportBoqThaiWorkbook(params: {
  outputPath: string;
  records: ComponentRecord[];
  rules: BoqThaiRule[];
  auditIssues?: Array<Record<string, unknown>>;
}): Promise<{ path: string; sheetNames: string[]; boqCount: number; unmatchedCount: number; totals: Record<string, number> }> {
  const result = buildBoqThai(params.records, params.rules);
  const workbook = new ExcelJS.Workbook();
  workbook.creator = "OpenAI Codex";
  workbook.created = new Date();
  workbook.modified = new Date();

  addSheet(workbook, "01_BOQ_THAI", [
    { key: "no", header: "No.", width: 8 },
    { key: "category", header: "Category", width: 18 },
    { key: "item_code", header: "Item Code", width: 18 },
    { key: "description_th", header: "Description", width: 28 },
    { key: "unit", header: "Unit", width: 10 },
    { key: "quantity", header: "Quantity", width: 12 },
    { key: "material_unit_cost", header: "Material / Unit", width: 16 },
    { key: "material_amount", header: "Material Amount", width: 16 },
    { key: "labor_unit_cost", header: "Labor / Unit", width: 16 },
    { key: "labor_amount", header: "Labor Amount", width: 16 },
    { key: "total_amount", header: "Total Amount", width: 16 },
    { key: "source", header: "Source", width: 36 },
    { key: "note", header: "Note", width: 28 },
  ], result.rows as unknown as Array<Record<string, unknown>>);

  addSheet(workbook, "02_Raw_Takeoff", [
    { key: "type", header: "Type" },
    { key: "entityID", header: "Entity ID" },
    { key: "name", header: "Name" },
    { key: "definitionName", header: "Definition" },
    { key: "category", header: "Category" },
    { key: "tag", header: "Tag" },
    { key: "dimensions", header: "Dimensions", width: 18 },
    { key: "lengthM", header: "Length (m)" },
    { key: "volumeM3", header: "Volume (m3)" },
    { key: "surfaceAreaM2", header: "Surface Area (m2)" },
    { key: "estimatedWeightKg", header: "Weight (kg)" },
    { key: "material", header: "Material" },
    { key: "isSolid", header: "Solid" },
  ], params.records as unknown as Array<Record<string, unknown>>);

  addSheet(workbook, "03_Price_Rules", RULE_HEADERS.map((key) => ({ key, header: key, width: 18 })), params.rules as unknown as Array<Record<string, unknown>>);
  addSheet(workbook, "04_Unmatched_Items", [
    { key: "entityID", header: "Entity ID" },
    { key: "name", header: "Name" },
    { key: "definitionName", header: "Definition", width: 22 },
    { key: "category", header: "Category" },
    { key: "tag", header: "Tag" },
    { key: "material", header: "Material" },
    { key: "quantity_hint", header: "Quantity Hint", width: 18 },
    { key: "reason", header: "Reason", width: 26 },
  ], result.unmatchedItems as unknown as Array<Record<string, unknown>>);
  addSheet(workbook, "05_Model_Audit", [
    { key: "severity", header: "Severity" },
    { key: "code", header: "Code", width: 28 },
    { key: "label", header: "Label", width: 36 },
    { key: "count", header: "Count" },
    { key: "sampleNames", header: "Sample Names", width: 36 },
  ], params.auditIssues ?? []);

  await fs.mkdir(path.dirname(params.outputPath), { recursive: true });
  await workbook.xlsx.writeFile(params.outputPath);
  return {
    path: params.outputPath,
    sheetNames: workbook.worksheets.map((worksheet) => worksheet.name),
    boqCount: result.rows.length,
    unmatchedCount: result.unmatchedItems.length,
    totals: result.totals,
  };
}

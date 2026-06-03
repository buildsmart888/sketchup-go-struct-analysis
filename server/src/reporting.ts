import fs from "node:fs/promises";
import path from "node:path";
import ExcelJS from "exceljs";
import type { ComponentRecord, Dimensions, ModelSummary, QuantitySummaryRow, SelectionMetric, TagInfo } from "./types.js";

const CUBIC_INCH_TO_M3 = 0.000016387064;

interface DensityRule {
  label: string;
  densityKgM3: number;
  keywords: string[];
}

interface DensityMatch {
  label: string;
  densityKgM3: number | null;
}

interface EnrichedRecord extends ComponentRecord {
  volumeM3: number | null;
  densityLabel: string;
  densityKgM3: number | null;
  estimatedWeightKg: number | null;
}

interface EnrichedQuantityRow extends QuantitySummaryRow {
  totalVolumeM3: number;
  estimatedWeightKg: number;
}

interface BilingualHeader {
  key: string;
  th: string;
  en: string;
  width?: number;
}

interface SiteReportOptions {
  outputPath: string;
  reportTitle?: string;
  reportSubtitle?: string;
  groupBy: string[];
  densityOverrides?: Record<string, number>;
}

const BASE_DENSITY_RULES: DensityRule[] = [
  { label: "Steel / เหล็ก", densityKgM3: 7850, keywords: ["steel", "เหล็ก", "beam", "column", "plate", "brace", "truss", "pipe"] },
  { label: "Rigging Steel / เหล็กยก", densityKgM3: 7850, keywords: ["shackle", "hook", "spreader", "padeye", "lug", "trunnion"] },
  { label: "Aluminum / อลูมิเนียม", densityKgM3: 2700, keywords: ["aluminum", "อลูมิเนียม"] },
  { label: "Concrete / คอนกรีต", densityKgM3: 2400, keywords: ["concrete", "คอนกรีต"] },
  { label: "Timber / ไม้", densityKgM3: 650, keywords: ["wood", "timber", "plywood", "ไม้"] },
];

function normalizeText(value: unknown): string {
  return String(value ?? "").trim();
}

function normalizeLower(value: unknown): string {
  return normalizeText(value).toLowerCase();
}

function volumeToM3(volume: number | null | undefined): number | null {
  if (typeof volume !== "number" || !Number.isFinite(volume)) {
    return null;
  }
  return volume * CUBIC_INCH_TO_M3;
}

function round(value: number | null | undefined, digits = 3): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function dimensionValue(record: ComponentRecord, key: keyof Dimensions): number | null {
  return typeof record.dimensions === "object" && record.dimensions !== null
    ? round(record.dimensions[key], 3)
    : null;
}

function withDensityOverrides(overrides?: Record<string, number>): DensityRule[] {
  if (!overrides || Object.keys(overrides).length === 0) {
    return BASE_DENSITY_RULES;
  }

  const customRules = Object.entries(overrides).map(([keyword, densityKgM3]) => ({
    label: `Custom / กำหนดเอง: ${keyword}`,
    densityKgM3,
    keywords: [keyword],
  }));

  return [...customRules, ...BASE_DENSITY_RULES];
}

function inferDensity(record: ComponentRecord, densityRules: DensityRule[]): DensityMatch {
  const haystack = [
    record.material,
    record.tag,
    record.name,
    record.definitionName,
    record.type,
    ...record.path,
  ]
    .map(normalizeLower)
    .join(" ");

  const matched = densityRules.find((rule) =>
    rule.keywords.some((keyword) => haystack.includes(keyword.toLowerCase())),
  );

  if (!matched) {
    return { label: "Unknown / ไม่ระบุ", densityKgM3: null };
  }

  return {
    label: matched.label,
    densityKgM3: matched.densityKgM3,
  };
}

function enrichRecord(record: ComponentRecord, densityRules: DensityRule[]): EnrichedRecord {
  const density = inferDensity(record, densityRules);
  const volumeM3 = volumeToM3(record.volume);
  const estimatedWeightKg =
    volumeM3 !== null && density.densityKgM3 !== null ? volumeM3 * density.densityKgM3 : null;

  return {
    ...record,
    volumeM3: round(volumeM3, 6),
    densityLabel: density.label,
    densityKgM3: density.densityKgM3,
    estimatedWeightKg: round(estimatedWeightKg, 2),
  };
}

function enrichQuantityRows(
  rows: QuantitySummaryRow[],
  densityRules: DensityRule[],
): EnrichedQuantityRow[] {
  return rows.map((row) => {
    const recordLike: ComponentRecord = {
      type: normalizeText(row.type),
      entityID: 0,
      name: normalizeText(row.name),
      definitionName: normalizeText(row.definitionName),
      tag: normalizeText(row.tag),
      path: [],
      depth: 0,
      volume: typeof row.totalVolume === "number" ? row.totalVolume : null,
      dimensions: { width: 0, height: 0, depth: 0 },
      material: normalizeText(row.material) || null,
      isSolid: Number(row.solidCount ?? 0) > 0,
    };
    const density = inferDensity(recordLike, densityRules);
    const totalVolumeM3 = volumeToM3(typeof row.totalVolume === "number" ? row.totalVolume : null) ?? 0;
    const estimatedWeightKg =
      density.densityKgM3 !== null ? totalVolumeM3 * density.densityKgM3 : 0;

    return {
      ...row,
      totalVolumeM3: round(totalVolumeM3, 6) ?? 0,
      estimatedWeightKg: round(estimatedWeightKg, 2) ?? 0,
    };
  });
}

function classifyRecordCategory(record: EnrichedRecord): string[] {
  const haystack = [
    record.material,
    record.tag,
    record.name,
    record.definitionName,
    record.type,
    record.densityLabel,
    ...record.path,
  ]
    .map(normalizeLower)
    .join(" ");

  const categories: string[] = [];
  if (/(steel|เหล็ก|beam|column|plate|brace|truss|frame|pipe)/.test(haystack)) {
    categories.push("steel");
  }
  if (/(rigging|สลิง|sling|shackle|hook|spreader|chain|wire|rope)/.test(haystack)) {
    categories.push("rigging");
  }
  if (/(lifting|lift|lug|padeye|trunnion|anchor|hoist)/.test(haystack)) {
    categories.push("lifting");
  }
  return categories;
}

function addTitle(worksheet: ExcelJS.Worksheet, title: string, subtitle?: string): void {
  worksheet.mergeCells("A1:H1");
  worksheet.getCell("A1").value = title;
  worksheet.getCell("A1").font = { bold: true, size: 16 };
  worksheet.getCell("A1").alignment = { vertical: "middle", horizontal: "left" };
  if (subtitle) {
    worksheet.mergeCells("A2:H2");
    worksheet.getCell("A2").value = subtitle;
    worksheet.getCell("A2").font = { italic: true, size: 10 };
  }
}

function styleHeaderRow(row: ExcelJS.Row): void {
  row.font = { bold: true };
  row.alignment = { vertical: "middle", horizontal: "center", wrapText: true };
  row.fill = {
    type: "pattern",
    pattern: "solid",
    fgColor: { argb: "FFD9EAF7" },
  };
  row.border = {
    top: { style: "thin" },
    left: { style: "thin" },
    bottom: { style: "thin" },
    right: { style: "thin" },
  };
}

function styleBodyRows(worksheet: ExcelJS.Worksheet, fromRow: number): void {
  worksheet.eachRow((row, rowNumber) => {
    if (rowNumber < fromRow) {
      return;
    }
    row.alignment = { vertical: "top", wrapText: true };
    row.eachCell((cell) => {
      cell.border = {
        top: { style: "thin", color: { argb: "FFE6E6E6" } },
        left: { style: "thin", color: { argb: "FFE6E6E6" } },
        bottom: { style: "thin", color: { argb: "FFE6E6E6" } },
        right: { style: "thin", color: { argb: "FFE6E6E6" } },
      };
    });
  });
}

function setColumns(worksheet: ExcelJS.Worksheet, headers: BilingualHeader[]): void {
  worksheet.columns = headers.map((header) => ({
    key: header.key,
    width: header.width ?? 18,
  }));
}

function addBilingualTableSheet(
  workbook: ExcelJS.Workbook,
  sheetName: string,
  title: string,
  subtitle: string | undefined,
  headers: BilingualHeader[],
  rows: Array<Record<string, unknown>>,
): ExcelJS.Worksheet {
  const worksheet = workbook.addWorksheet(sheetName);
  addTitle(worksheet, title, subtitle);
  setColumns(worksheet, headers);

  const thaiRow = worksheet.addRow(Object.fromEntries(headers.map((header) => [header.key, header.th])));
  const englishRow = worksheet.addRow(Object.fromEntries(headers.map((header) => [header.key, header.en])));
  styleHeaderRow(thaiRow);
  styleHeaderRow(englishRow);

  if (rows.length === 0) {
    worksheet.addRow(Object.fromEntries(headers.map((header, index) => [header.key, index === 0 ? "ไม่มีข้อมูล / No data" : ""])));
  } else {
    rows.forEach((row) => {
      worksheet.addRow(row);
    });
  }

  worksheet.views = [{ state: "frozen", ySplit: 4 }];
  styleBodyRows(worksheet, 5);
  worksheet.autoFilter = {
    from: { row: 3, column: 1 },
    to: { row: 4, column: headers.length },
  };
  return worksheet;
}

function makeSummaryRows(
  modelSummary: ModelSummary,
  inventory: EnrichedRecord[],
  bomRows: EnrichedQuantityRow[],
  reportTitle: string,
): Array<Record<string, unknown>> {
  const totalVolumeM3 = inventory.reduce((sum, item) => sum + (item.volumeM3 ?? 0), 0);
  const totalWeightKg = inventory.reduce((sum, item) => sum + (item.estimatedWeightKg ?? 0), 0);
  const uniqueTags = new Set(inventory.map((item) => item.tag)).size;
  return [
    { itemTh: "ชื่อรายงาน", itemEn: "Report Title", value: reportTitle, note: "" },
    { itemTh: "ชื่อโมเดล", itemEn: "Model Title", value: modelSummary.title || modelSummary.name, note: modelSummary.path },
    { itemTh: "จำนวนเอนทิตี", itemEn: "Entity Count", value: modelSummary.entitiesCount, note: "" },
    { itemTh: "จำนวนวัสดุ", itemEn: "Material Count", value: modelSummary.materialsCount, note: "" },
    { itemTh: "จำนวนแท็ก/เลเยอร์", itemEn: "Tag/Layer Count", value: modelSummary.layersCount, note: `Unique in inventory: ${uniqueTags}` },
    { itemTh: "จำนวนรายการ inventory", itemEn: "Inventory Item Count", value: inventory.length, note: "" },
    { itemTh: "จำนวนรายการ BOM", itemEn: "BOM Row Count", value: bomRows.length, note: "" },
    { itemTh: "ปริมาตรรวม (ลบ.ม.)", itemEn: "Total Volume (m3)", value: round(totalVolumeM3, 4), note: "Derived from SketchUp solid volume" },
    { itemTh: "น้ำหนักประมาณรวม (กก.)", itemEn: "Estimated Weight (kg)", value: round(totalWeightKg, 2), note: "Estimated from volume x density profile" },
    { itemTh: "ขนาดโมเดล (กว้าง x สูง x ลึก)", itemEn: "Model Bounds (W x H x D)", value: `${round(modelSummary.bounds.width, 3)} x ${round(modelSummary.bounds.height, 3)} x ${round(modelSummary.bounds.depth, 3)}`, note: "SketchUp internal length units" },
  ];
}

function makeTagSummaryRows(inventory: EnrichedRecord[], tags: TagInfo[]): Array<Record<string, unknown>> {
  const byTag = new Map<string, { visible: string; count: number; volumeM3: number; weightKg: number }>();
  tags.forEach((tag) => {
    byTag.set(tag.name, {
      visible: tag.visible ? "Yes / ใช่" : "No / ไม่ใช่",
      count: 0,
      volumeM3: 0,
      weightKg: 0,
    });
  });

  inventory.forEach((item) => {
    const current = byTag.get(item.tag) ?? { visible: "", count: 0, volumeM3: 0, weightKg: 0 };
    current.count += 1;
    current.volumeM3 += item.volumeM3 ?? 0;
    current.weightKg += item.estimatedWeightKg ?? 0;
    byTag.set(item.tag, current);
  });

  return Array.from(byTag.entries())
    .map(([tag, summary]) => ({
      tag,
      visible: summary.visible,
      count: summary.count,
      volumeM3: round(summary.volumeM3, 4),
      estimatedWeightKg: round(summary.weightKg, 2),
    }))
    .sort((a, b) => String(a.tag).localeCompare(String(b.tag)));
}

function inventoryRows(records: EnrichedRecord[]): Array<Record<string, unknown>> {
  return records.map((record) => ({
    type: record.type,
    entityID: record.entityID,
    name: record.name,
    definitionName: record.definitionName,
    tag: record.tag,
    depth: record.depth,
    isSolid: record.isSolid ? "Yes / ใช่" : "No / ไม่ใช่",
    width: dimensionValue(record, "width") ?? round(record.widthM ?? null, 3),
    height: dimensionValue(record, "height") ?? round(record.heightM ?? null, 3),
    depthSize: dimensionValue(record, "depth") ?? null,
    volumeRaw: round(record.volume, 3),
    volumeM3: record.volumeM3,
    material: record.material ?? "",
    densityLabel: record.densityLabel,
    densityKgM3: record.densityKgM3 ?? "",
    estimatedWeightKg: record.estimatedWeightKg ?? "",
    path: record.path.join(" > "),
  }));
}

function selectionRows(items: SelectionMetric[], densityRules: DensityRule[]): Array<Record<string, unknown>> {
  return items.map((item) => {
    const enriched = enrichRecord(
      {
        ...item,
        depth: 0,
        path: [],
      },
      densityRules,
    );

    return {
      type: item.type,
      entityID: item.entityID,
      name: item.name,
      definitionName: item.definitionName,
      tag: item.tag,
      isSolid: item.isSolid ? "Yes / ใช่" : "No / ไม่ใช่",
      width: round(item.dimensions.width, 3),
      height: round(item.dimensions.height, 3),
      depthSize: round(item.dimensions.depth, 3),
      volumeRaw: round(item.volume, 3),
      volumeM3: enriched.volumeM3 ?? "",
      material: item.material ?? "",
      densityLabel: enriched.densityLabel,
      estimatedWeightKg: enriched.estimatedWeightKg ?? "",
    };
  });
}

function bomRows(rows: EnrichedQuantityRow[], groupBy: string[]): Array<Record<string, unknown>> {
  return rows.map((row) => {
    const base: Record<string, unknown> = {};
    groupBy.forEach((key) => {
      base[key] = row[key];
    });
    return {
      ...base,
      quantity: row.quantity,
      solidCount: row.solidCount,
      types: Array.isArray(row.types) ? row.types.join(" | ") : "",
      totalVolumeRaw: round(Number(row.totalVolume), 3),
      totalVolumeM3: row.totalVolumeM3,
      estimatedWeightKg: row.estimatedWeightKg,
    };
  });
}

function filterCategory(records: EnrichedRecord[], category: string): EnrichedRecord[] {
  return records.filter((record) => classifyRecordCategory(record).includes(category));
}

export async function exportBilingualSiteReport(params: {
  modelSummary: ModelSummary;
  tags: TagInfo[];
  inventory: ComponentRecord[];
  bom: QuantitySummaryRow[];
  selection: SelectionMetric[];
  options: SiteReportOptions;
}): Promise<{ path: string; sheetNames: string[]; inventoryCount: number; bomCount: number }> {
  const densityRules = withDensityOverrides(params.options.densityOverrides);
  const inventory = params.inventory.map((record) => enrichRecord(record, densityRules));
  const bom = enrichQuantityRows(params.bom, densityRules);
  const workbook = new ExcelJS.Workbook();
  workbook.creator = "OpenAI Codex";
  workbook.created = new Date();
  workbook.modified = new Date();

  const title = params.options.reportTitle || "SketchUp Site Report / รายงานหน้างาน";
  const subtitle =
    params.options.reportSubtitle ||
    `Generated ${new Date().toLocaleString()} | Grouped by ${params.options.groupBy.join(", ")}`;

  addBilingualTableSheet(
    workbook,
    "01_Summary",
    title,
    subtitle,
    [
      { key: "itemTh", th: "หัวข้อ (ไทย)", en: "Item (TH)", width: 24 },
      { key: "itemEn", th: "หัวข้อ (อังกฤษ)", en: "Item (EN)", width: 24 },
      { key: "value", th: "ค่า", en: "Value", width: 26 },
      { key: "note", th: "หมายเหตุ", en: "Notes", width: 32 },
    ],
    makeSummaryRows(params.modelSummary, inventory, bom, title),
  );

  addBilingualTableSheet(
    workbook,
    "02_Inventory",
    "รายการชิ้นงาน / Inventory",
    subtitle,
    [
      { key: "type", th: "ประเภท", en: "Type", width: 16 },
      { key: "entityID", th: "รหัสเอนทิตี", en: "Entity ID", width: 14 },
      { key: "name", th: "ชื่อชิ้นงาน", en: "Name", width: 20 },
      { key: "definitionName", th: "ชื่อคอมโพเนนต์", en: "Definition Name", width: 22 },
      { key: "tag", th: "แท็ก/เลเยอร์", en: "Tag/Layer", width: 18 },
      { key: "depth", th: "ชั้นลำดับ", en: "Depth", width: 10 },
      { key: "isSolid", th: "เป็น Solid", en: "Solid", width: 12 },
      { key: "width", th: "กว้าง", en: "Width", width: 12 },
      { key: "height", th: "สูง", en: "Height", width: 12 },
      { key: "depthSize", th: "ลึก", en: "Depth", width: 12 },
      { key: "volumeRaw", th: "ปริมาตรดิบ", en: "Raw Volume", width: 14 },
      { key: "volumeM3", th: "ปริมาตร (ลบ.ม.)", en: "Volume (m3)", width: 16 },
      { key: "material", th: "วัสดุ", en: "Material", width: 18 },
      { key: "densityLabel", th: "โปรไฟล์ความหนาแน่น", en: "Density Profile", width: 24 },
      { key: "densityKgM3", th: "ความหนาแน่น (กก./ลบ.ม.)", en: "Density (kg/m3)", width: 20 },
      { key: "estimatedWeightKg", th: "น้ำหนักประมาณ (กก.)", en: "Estimated Weight (kg)", width: 18 },
      { key: "path", th: "เส้นทางการซ้อน", en: "Nesting Path", width: 28 },
    ],
    inventoryRows(inventory),
  );

  const groupByHeaders: BilingualHeader[] = params.options.groupBy.map((key) => ({
    key,
    th: `กลุ่ม: ${key}`,
    en: `Group: ${key}`,
    width: 18,
  }));

  addBilingualTableSheet(
    workbook,
    "03_BOM",
    "สรุปรายการวัสดุ / BOM Summary",
    subtitle,
    [
      ...groupByHeaders,
      { key: "quantity", th: "จำนวน", en: "Quantity", width: 12 },
      { key: "solidCount", th: "จำนวน Solid", en: "Solid Count", width: 12 },
      { key: "types", th: "ประเภทที่พบ", en: "Types", width: 20 },
      { key: "totalVolumeRaw", th: "ปริมาตรดิบรวม", en: "Total Raw Volume", width: 16 },
      { key: "totalVolumeM3", th: "ปริมาตรรวม (ลบ.ม.)", en: "Total Volume (m3)", width: 16 },
      { key: "estimatedWeightKg", th: "น้ำหนักประมาณรวม (กก.)", en: "Estimated Weight (kg)", width: 18 },
    ],
    bomRows(bom, params.options.groupBy),
  );

  addBilingualTableSheet(
    workbook,
    "04_Tags",
    "สรุปตามแท็ก / Tag Summary",
    subtitle,
    [
      { key: "tag", th: "แท็ก/เลเยอร์", en: "Tag/Layer", width: 18 },
      { key: "visible", th: "มองเห็น", en: "Visible", width: 12 },
      { key: "count", th: "จำนวนรายการ", en: "Item Count", width: 14 },
      { key: "volumeM3", th: "ปริมาตรรวม (ลบ.ม.)", en: "Total Volume (m3)", width: 16 },
      { key: "estimatedWeightKg", th: "น้ำหนักประมาณรวม (กก.)", en: "Estimated Weight (kg)", width: 18 },
    ],
    makeTagSummaryRows(inventory, params.tags),
  );

  addBilingualTableSheet(
    workbook,
    "05_Selection",
    "รายการที่เลือก / Selection",
    subtitle,
    [
      { key: "type", th: "ประเภท", en: "Type", width: 16 },
      { key: "entityID", th: "รหัสเอนทิตี", en: "Entity ID", width: 14 },
      { key: "name", th: "ชื่อชิ้นงาน", en: "Name", width: 20 },
      { key: "definitionName", th: "ชื่อคอมโพเนนต์", en: "Definition Name", width: 22 },
      { key: "tag", th: "แท็ก/เลเยอร์", en: "Tag/Layer", width: 16 },
      { key: "isSolid", th: "เป็น Solid", en: "Solid", width: 12 },
      { key: "width", th: "กว้าง", en: "Width", width: 12 },
      { key: "height", th: "สูง", en: "Height", width: 12 },
      { key: "depthSize", th: "ลึก", en: "Depth", width: 12 },
      { key: "volumeRaw", th: "ปริมาตรดิบ", en: "Raw Volume", width: 14 },
      { key: "volumeM3", th: "ปริมาตร (ลบ.ม.)", en: "Volume (m3)", width: 16 },
      { key: "material", th: "วัสดุ", en: "Material", width: 16 },
      { key: "densityLabel", th: "โปรไฟล์ความหนาแน่น", en: "Density Profile", width: 20 },
      { key: "estimatedWeightKg", th: "น้ำหนักประมาณ (กก.)", en: "Estimated Weight (kg)", width: 18 },
    ],
    selectionRows(params.selection, densityRules),
  );

  const categorySheets: Array<[string, string, string]> = [
    ["steel", "06_Steel", "เหล็ก / Steel"],
    ["rigging", "07_Rigging", "อุปกรณ์ยก / Rigging"],
    ["lifting", "08_Lifting", "จุดยก / Lifting Points"],
  ];

  categorySheets.forEach(([category, sheetName, sheetTitle]) => {
    addBilingualTableSheet(
      workbook,
      sheetName,
      sheetTitle,
      subtitle,
      [
        { key: "type", th: "ประเภท", en: "Type", width: 16 },
        { key: "name", th: "ชื่อชิ้นงาน", en: "Name", width: 20 },
        { key: "definitionName", th: "ชื่อคอมโพเนนต์", en: "Definition Name", width: 22 },
        { key: "tag", th: "แท็ก/เลเยอร์", en: "Tag/Layer", width: 18 },
        { key: "material", th: "วัสดุ", en: "Material", width: 18 },
        { key: "volumeM3", th: "ปริมาตร (ลบ.ม.)", en: "Volume (m3)", width: 16 },
        { key: "estimatedWeightKg", th: "น้ำหนักประมาณ (กก.)", en: "Estimated Weight (kg)", width: 18 },
        { key: "path", th: "เส้นทางการซ้อน", en: "Nesting Path", width: 28 },
      ],
      inventoryRows(filterCategory(inventory, category)),
    );
  });

  await fs.mkdir(path.dirname(params.options.outputPath), { recursive: true });
  await workbook.xlsx.writeFile(params.options.outputPath);

  return {
    path: params.options.outputPath,
    sheetNames: workbook.worksheets.map((worksheet) => worksheet.name),
    inventoryCount: inventory.length,
    bomCount: bom.length,
  };
}

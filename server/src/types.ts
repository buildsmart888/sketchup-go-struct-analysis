export interface Dimensions {
  width: number;
  height: number;
  depth: number;
}

export interface ModelSummary {
  title: string;
  path: string;
  name: string;
  guid: string;
  entitiesCount: number;
  materialsCount: number;
  layersCount: number;
  scenesCount: number;
  selectionCount: number;
  bounds: Dimensions;
}

export interface TagInfo {
  name: string;
  visible: boolean;
  displayName: string;
}

export interface ComponentRecord {
  type: string;
  entityID: number;
  name: string;
  definitionName: string;
  category?: string;
  tag: string;
  path: string[];
  depth: number;
  volume: number | null;
  dimensions: Dimensions | string;
  lengthM?: number | null;
  widthM?: number | null;
  heightM?: number | null;
  volumeM3?: number | null;
  surfaceAreaM2?: number | null;
  estimatedWeightKg?: number | null;
  material: string | null;
  isSolid: boolean;
}

export interface SelectionMetric {
  type: string;
  entityID: number;
  name: string;
  tag: string;
  dimensions: Dimensions;
  isSolid: boolean;
  volume: number | null;
  material: string | null;
  definitionName: string;
}

export interface QuantitySummaryRow {
  quantity: number;
  totalVolume: number;
  solidCount: number;
  types: string[];
  [key: string]: string | number | string[];
}

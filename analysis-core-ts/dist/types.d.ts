export type DesignMethod = "ASD" | "LRFD";
export type ModuleKind = "continuous_beam" | "truss_2d" | "frame_2d" | "steel_frame" | "mixed_system";
export type Dof = "ux" | "uy" | "rz";
export interface ProjectInfo {
    project: string;
    company?: string;
    engineer?: string;
    location?: string;
    designMethod: DesignMethod;
}
export interface Units {
    length: "m";
    force: "kg";
    moment: "kg-m";
    displacement: "mm";
}
export interface Material {
    id: string;
    name: string;
    eKgM2: number;
}
export interface Section {
    id: string;
    name: string;
    areaM2?: number;
    iM4?: number;
}
export interface Node2D {
    id: string;
    xM: number;
    yM: number;
}
export interface Member2D {
    id: string;
    nodeI: string;
    nodeJ: string;
    materialId: string;
    sectionId: string;
    module?: ModuleKind;
}
export interface Support2D {
    nodeId: string;
    restraints: Partial<Record<Dof, boolean>>;
}
export interface NodalLoad2D {
    id: string;
    nodeId: string;
    case: string;
    fxKg?: number;
    fyKg?: number;
    mzKgM?: number;
}
export interface MemberPointLoad2D {
    xM: number;
    case?: string;
    fyKg?: number;
}
export interface MemberLoad2D {
    id: string;
    memberId: string;
    case: string;
    uniformFyKgM?: number;
    pointLoads?: MemberPointLoad2D[];
}
export interface LoadCase {
    name: string;
    label?: string;
}
export interface LoadCombination {
    name: string;
    method: DesignMethod;
    factors: Record<string, number>;
}
export interface StructuralModel {
    version: number;
    projectInfo: ProjectInfo;
    units: Units;
    materials: Material[];
    sections: Section[];
    nodes: Node2D[];
    members: Member2D[];
    supports: Support2D[];
    nodalLoads: NodalLoad2D[];
    memberLoads?: MemberLoad2D[];
    loadCases: LoadCase[];
    loadCombinations: LoadCombination[];
    activeCombination: string;
    analysisModules: ModuleKind[];
    results?: Record<string, unknown>;
}
export interface NodeDisplacement2D {
    nodeId: string;
    uxM: number;
    uyM: number;
    rzRad?: number;
}
export interface SupportReaction2D {
    nodeId: string;
    fxKg: number;
    fyKg: number;
    mzKgM?: number;
}

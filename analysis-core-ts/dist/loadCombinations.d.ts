import type { LoadCombination, StructuralModel } from "./types.js";
export declare function activeCombination(model: StructuralModel): LoadCombination;
export declare function combinedNodalLoads(model: StructuralModel): Map<string, {
    fxKg: number;
    fyKg: number;
    mzKgM: number;
}>;

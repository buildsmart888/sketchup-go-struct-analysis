import type { NodeDisplacement2D, StructuralModel, SupportReaction2D } from "./types.js";
export interface TrussMemberForce {
    memberId: string;
    axialKg: number;
    tensionPositive: boolean;
}
export interface Truss2DResult {
    ok: true;
    displacements: NodeDisplacement2D[];
    reactions: SupportReaction2D[];
    memberForces: TrussMemberForce[];
}
export declare function analyzeTruss2D(model: StructuralModel): Truss2DResult;

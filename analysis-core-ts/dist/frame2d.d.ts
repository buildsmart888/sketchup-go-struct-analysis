import type { NodeDisplacement2D, StructuralModel, SupportReaction2D } from "./types.js";
export interface FrameMemberEndForces {
    memberId: string;
    localEndForces: [number, number, number, number, number, number];
}
export interface Frame2DResult {
    ok: true;
    displacements: NodeDisplacement2D[];
    reactions: SupportReaction2D[];
    memberEndForces: FrameMemberEndForces[];
}
export declare function analyzeFrame2D(model: StructuralModel): Frame2DResult;

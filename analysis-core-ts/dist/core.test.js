import { test } from "node:test";
import * as assert from "node:assert/strict";
import { activeCombination, analyzeFrame2D, analyzeTruss2D } from "./index.js";
const baseModel = {
    version: 1,
    projectInfo: { project: "Core Test", designMethod: "ASD" },
    units: { length: "m", force: "kg", moment: "kg-m", displacement: "mm" },
    loadCases: [{ name: "DL" }, { name: "LL" }],
    loadCombinations: [
        { name: "1.0DL", method: "ASD", factors: { DL: 1 } },
        { name: "1.2DL", method: "LRFD", factors: { DL: 1.2 } }
    ],
    activeCombination: "1.0DL"
};
test("activeCombination returns selected or first combination", () => {
    assert.equal(activeCombination({ ...trussModel(), activeCombination: "1.2DL" }).name, "1.2DL");
    assert.equal(activeCombination({ ...trussModel(), activeCombination: "missing" }).name, "1.0DL");
});
test("analyzeTruss2D solves a stable triangular truss and balances reactions", () => {
    const result = analyzeTruss2D(trussModel());
    const totalFx = result.reactions.reduce((sum, reaction) => sum + reaction.fxKg, 0);
    const totalFy = result.reactions.reduce((sum, reaction) => sum + reaction.fyKg, 0);
    assert.ok(Math.abs(totalFx) < 1e-6);
    assert.ok(Math.abs(totalFy - 1000) < 1e-6);
    assert.equal(result.memberForces.length, 3);
    assert.ok(result.displacements.some((item) => Math.abs(item.uyM) > 0));
});
test("analyzeFrame2D solves a one-bay portal frame and balances lateral load", () => {
    const result = analyzeFrame2D(frameModel());
    const totalFx = result.reactions.reduce((sum, reaction) => sum + reaction.fxKg, 0);
    const totalFy = result.reactions.reduce((sum, reaction) => sum + reaction.fyKg, 0);
    assert.ok(Math.abs(totalFx + 500) < 1e-5);
    assert.ok(Math.abs(totalFy) < 1e-5);
    assert.equal(result.memberEndForces.length, 3);
});
function trussModel() {
    return {
        ...baseModel,
        materials: [{ id: "steel", name: "Steel", eKgM2: 2.05e10 }],
        sections: [{ id: "rod", name: "Rod", areaM2: 0.003 }],
        nodes: [
            { id: "A", xM: 0, yM: 0 },
            { id: "B", xM: 4, yM: 0 },
            { id: "C", xM: 2, yM: 3 }
        ],
        members: [
            { id: "AB", nodeI: "A", nodeJ: "B", materialId: "steel", sectionId: "rod", module: "truss_2d" },
            { id: "AC", nodeI: "A", nodeJ: "C", materialId: "steel", sectionId: "rod", module: "truss_2d" },
            { id: "BC", nodeI: "B", nodeJ: "C", materialId: "steel", sectionId: "rod", module: "truss_2d" }
        ],
        supports: [
            { nodeId: "A", restraints: { ux: true, uy: true } },
            { nodeId: "B", restraints: { uy: true } }
        ],
        nodalLoads: [{ id: "P1", nodeId: "C", case: "DL", fyKg: -1000 }],
        analysisModules: ["truss_2d"]
    };
}
function frameModel() {
    return {
        ...baseModel,
        materials: [{ id: "steel", name: "Steel", eKgM2: 2.05e10 }],
        sections: [{ id: "w", name: "Frame Section", areaM2: 0.006, iM4: 0.00008 }],
        nodes: [
            { id: "A", xM: 0, yM: 0 },
            { id: "B", xM: 6, yM: 0 },
            { id: "C", xM: 0, yM: 4 },
            { id: "D", xM: 6, yM: 4 }
        ],
        members: [
            { id: "AC", nodeI: "A", nodeJ: "C", materialId: "steel", sectionId: "w", module: "frame_2d" },
            { id: "BD", nodeI: "B", nodeJ: "D", materialId: "steel", sectionId: "w", module: "frame_2d" },
            { id: "CD", nodeI: "C", nodeJ: "D", materialId: "steel", sectionId: "w", module: "frame_2d" }
        ],
        supports: [
            { nodeId: "A", restraints: { ux: true, uy: true, rz: true } },
            { nodeId: "B", restraints: { ux: true, uy: true, rz: true } }
        ],
        nodalLoads: [{ id: "H1", nodeId: "C", case: "DL", fxKg: 500 }],
        analysisModules: ["frame_2d"]
    };
}

import { combinedNodalLoads } from "./loadCombinations.js";
import { solveLinearSystem, zeroMatrix } from "./matrix.js";
export function analyzeTruss2D(model) {
    const nodeIndex = new Map(model.nodes.map((node, index) => [node.id, index]));
    const materialById = new Map(model.materials.map((material) => [material.id, material]));
    const sectionById = new Map(model.sections.map((section) => [section.id, section]));
    const dofCount = model.nodes.length * 2;
    const stiffness = zeroMatrix(dofCount);
    const loads = Array.from({ length: dofCount }, () => 0);
    for (const member of model.members) {
        if (member.module && member.module !== "truss_2d")
            continue;
        const i = nodeIndex.get(member.nodeI);
        const j = nodeIndex.get(member.nodeJ);
        const nodeI = model.nodes[i ?? -1];
        const nodeJ = model.nodes[j ?? -1];
        const material = materialById.get(member.materialId);
        const section = sectionById.get(member.sectionId);
        if (i === undefined || j === undefined || !nodeI || !nodeJ || !material || !section?.areaM2) {
            throw new Error(`Invalid truss member ${member.id}`);
        }
        const dx = nodeJ.xM - nodeI.xM;
        const dy = nodeJ.yM - nodeI.yM;
        const length = Math.hypot(dx, dy);
        if (length <= 0)
            throw new Error(`Zero-length truss member ${member.id}`);
        const c = dx / length;
        const s = dy / length;
        const k = (material.eKgM2 * section.areaM2) / length;
        const local = [
            [c * c, c * s, -c * c, -c * s],
            [c * s, s * s, -c * s, -s * s],
            [-c * c, -c * s, c * c, c * s],
            [-c * s, -s * s, c * s, s * s]
        ];
        const map = [i * 2, i * 2 + 1, j * 2, j * 2 + 1];
        for (let r = 0; r < 4; r += 1) {
            for (let col = 0; col < 4; col += 1)
                stiffness[map[r]][map[col]] += k * local[r][col];
        }
    }
    for (const [nodeId, load] of combinedNodalLoads(model)) {
        const index = nodeIndex.get(nodeId);
        if (index === undefined)
            continue;
        loads[index * 2] += load.fxKg;
        loads[index * 2 + 1] += load.fyKg;
    }
    return solveReducedTruss(model, stiffness, loads, nodeIndex);
}
function solveReducedTruss(model, stiffness, loads, nodeIndex) {
    const restrained = restrainedDofs(model, nodeIndex, ["ux", "uy"]);
    const free = loads.map((_, index) => index).filter((index) => !restrained.has(index));
    const reducedK = free.map((row) => free.map((col) => stiffness[row][col]));
    const reducedF = free.map((index) => loads[index]);
    const reducedD = solveLinearSystem(reducedK, reducedF);
    const displacementVector = Array.from({ length: loads.length }, () => 0);
    free.forEach((globalDof, index) => { displacementVector[globalDof] = reducedD[index]; });
    const reactionsVector = stiffness.map((row, rowIndex) => row.reduce((sum, value, colIndex) => sum + value * displacementVector[colIndex], 0) - loads[rowIndex]);
    return {
        ok: true,
        displacements: model.nodes.map((node, index) => ({
            nodeId: node.id,
            uxM: displacementVector[index * 2],
            uyM: displacementVector[index * 2 + 1]
        })),
        reactions: model.supports.map((support) => {
            const index = nodeIndex.get(support.nodeId);
            return {
                nodeId: support.nodeId,
                fxKg: index === undefined || !support.restraints.ux ? 0 : reactionsVector[index * 2],
                fyKg: index === undefined || !support.restraints.uy ? 0 : reactionsVector[index * 2 + 1]
            };
        }),
        memberForces: trussMemberForces(model, displacementVector, nodeIndex)
    };
}
function restrainedDofs(model, nodeIndex, dofs) {
    const restrained = new Set();
    for (const support of model.supports) {
        const index = nodeIndex.get(support.nodeId);
        if (index === undefined)
            continue;
        dofs.forEach((dof, offset) => {
            if (support.restraints[dof])
                restrained.add(index * dofs.length + offset);
        });
    }
    return restrained;
}
function trussMemberForces(model, displacementVector, nodeIndex) {
    const materialById = new Map(model.materials.map((material) => [material.id, material]));
    const sectionById = new Map(model.sections.map((section) => [section.id, section]));
    return model.members.filter((member) => !member.module || member.module === "truss_2d").map((member) => {
        const i = nodeIndex.get(member.nodeI);
        const j = nodeIndex.get(member.nodeJ);
        const nodeI = model.nodes[i];
        const nodeJ = model.nodes[j];
        const material = materialById.get(member.materialId);
        const section = sectionById.get(member.sectionId);
        const dx = nodeJ.xM - nodeI.xM;
        const dy = nodeJ.yM - nodeI.yM;
        const length = Math.hypot(dx, dy);
        const c = dx / length;
        const s = dy / length;
        const delta = -c * displacementVector[i * 2] -
            s * displacementVector[i * 2 + 1] +
            c * displacementVector[j * 2] +
            s * displacementVector[j * 2 + 1];
        const axial = ((material.eKgM2 * (section.areaM2 ?? 0)) / length) * delta;
        return { memberId: member.id, axialKg: axial, tensionPositive: true };
    });
}

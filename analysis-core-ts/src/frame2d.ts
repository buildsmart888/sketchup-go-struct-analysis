import { combinedNodalLoads } from "./loadCombinations.js";
import { solveLinearSystem, zeroMatrix } from "./matrix.js";
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

export function analyzeFrame2D(model: StructuralModel): Frame2DResult {
  const nodeIndex = new Map(model.nodes.map((node, index) => [node.id, index]));
  const materialById = new Map(model.materials.map((material) => [material.id, material]));
  const sectionById = new Map(model.sections.map((section) => [section.id, section]));
  const dofCount = model.nodes.length * 3;
  const stiffness = zeroMatrix(dofCount);
  const loads = Array.from({ length: dofCount }, () => 0);

  for (const member of model.members) {
    if (member.module && member.module !== "frame_2d") continue;
    const i = nodeIndex.get(member.nodeI);
    const j = nodeIndex.get(member.nodeJ);
    const nodeI = model.nodes[i ?? -1];
    const nodeJ = model.nodes[j ?? -1];
    const material = materialById.get(member.materialId);
    const section = sectionById.get(member.sectionId);
    if (i === undefined || j === undefined || !nodeI || !nodeJ || !material || !section?.areaM2 || !section.iM4) {
      throw new Error(`Invalid frame member ${member.id}`);
    }
    const transform = frameTransform(nodeI.xM, nodeI.yM, nodeJ.xM, nodeJ.yM);
    const local = frameLocalStiffness(material.eKgM2, section.areaM2, section.iM4, transform.length);
    const global = multiply(transpose(transform.t), multiply(local, transform.t));
    const map = [i * 3, i * 3 + 1, i * 3 + 2, j * 3, j * 3 + 1, j * 3 + 2];
    for (let r = 0; r < 6; r += 1) {
      for (let col = 0; col < 6; col += 1) stiffness[map[r]][map[col]] += global[r][col];
    }
  }

  for (const [nodeId, load] of combinedNodalLoads(model)) {
    const index = nodeIndex.get(nodeId);
    if (index === undefined) continue;
    loads[index * 3] += load.fxKg;
    loads[index * 3 + 1] += load.fyKg;
    loads[index * 3 + 2] += load.mzKgM;
  }

  const restrained = new Set<number>();
  for (const support of model.supports) {
    const index = nodeIndex.get(support.nodeId);
    if (index === undefined) continue;
    if (support.restraints.ux) restrained.add(index * 3);
    if (support.restraints.uy) restrained.add(index * 3 + 1);
    if (support.restraints.rz) restrained.add(index * 3 + 2);
  }
  const free = loads.map((_, index) => index).filter((index) => !restrained.has(index));
  const reducedK = free.map((row) => free.map((col) => stiffness[row][col]));
  const reducedF = free.map((index) => loads[index]);
  const reducedD = solveLinearSystem(reducedK, reducedF);
  const displacementVector = Array.from({ length: loads.length }, () => 0);
  free.forEach((globalDof, index) => { displacementVector[globalDof] = reducedD[index]; });
  const reactionsVector = stiffness.map((row, rowIndex) =>
    row.reduce((sum, value, colIndex) => sum + value * displacementVector[colIndex], 0) - loads[rowIndex]
  );

  return {
    ok: true,
    displacements: model.nodes.map((node, index) => ({
      nodeId: node.id,
      uxM: displacementVector[index * 3],
      uyM: displacementVector[index * 3 + 1],
      rzRad: displacementVector[index * 3 + 2]
    })),
    reactions: model.supports.map((support) => {
      const index = nodeIndex.get(support.nodeId);
      return {
        nodeId: support.nodeId,
        fxKg: index === undefined || !support.restraints.ux ? 0 : reactionsVector[index * 3],
        fyKg: index === undefined || !support.restraints.uy ? 0 : reactionsVector[index * 3 + 1],
        mzKgM: index === undefined || !support.restraints.rz ? 0 : reactionsVector[index * 3 + 2]
      };
    }),
    memberEndForces: frameMemberEndForces(model, displacementVector, nodeIndex)
  };
}

function frameLocalStiffness(e: number, a: number, i: number, l: number): number[][] {
  const ea = (e * a) / l;
  const ei = e * i;
  return [
    [ea, 0, 0, -ea, 0, 0],
    [0, 12 * ei / l ** 3, 6 * ei / l ** 2, 0, -12 * ei / l ** 3, 6 * ei / l ** 2],
    [0, 6 * ei / l ** 2, 4 * ei / l, 0, -6 * ei / l ** 2, 2 * ei / l],
    [-ea, 0, 0, ea, 0, 0],
    [0, -12 * ei / l ** 3, -6 * ei / l ** 2, 0, 12 * ei / l ** 3, -6 * ei / l ** 2],
    [0, 6 * ei / l ** 2, 2 * ei / l, 0, -6 * ei / l ** 2, 4 * ei / l]
  ];
}

function frameTransform(x1: number, y1: number, x2: number, y2: number): { length: number; t: number[][] } {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const length = Math.hypot(dx, dy);
  if (length <= 0) throw new Error("Zero-length frame member");
  const c = dx / length;
  const s = dy / length;
  return {
    length,
    t: [
      [c, s, 0, 0, 0, 0],
      [-s, c, 0, 0, 0, 0],
      [0, 0, 1, 0, 0, 0],
      [0, 0, 0, c, s, 0],
      [0, 0, 0, -s, c, 0],
      [0, 0, 0, 0, 0, 1]
    ]
  };
}

function frameMemberEndForces(model: StructuralModel, displacementVector: number[], nodeIndex: Map<string, number>): FrameMemberEndForces[] {
  const materialById = new Map(model.materials.map((material) => [material.id, material]));
  const sectionById = new Map(model.sections.map((section) => [section.id, section]));
  return model.members.filter((member) => !member.module || member.module === "frame_2d").map((member) => {
    const i = nodeIndex.get(member.nodeI)!;
    const j = nodeIndex.get(member.nodeJ)!;
    const nodeI = model.nodes[i];
    const nodeJ = model.nodes[j];
    const material = materialById.get(member.materialId)!;
    const section = sectionById.get(member.sectionId)!;
    const transform = frameTransform(nodeI.xM, nodeI.yM, nodeJ.xM, nodeJ.yM);
    const local = frameLocalStiffness(material.eKgM2, section.areaM2 ?? 0, section.iM4 ?? 0, transform.length);
    const map = [i * 3, i * 3 + 1, i * 3 + 2, j * 3, j * 3 + 1, j * 3 + 2];
    const globalDisplacement = map.map((dof) => displacementVector[dof]);
    const localDisplacement = multiplyVector(transform.t, globalDisplacement);
    const localEndForces = multiplyVector(local, localDisplacement) as [number, number, number, number, number, number];
    return { memberId: member.id, localEndForces };
  });
}

function transpose(matrix: number[][]): number[][] {
  return matrix[0].map((_, col) => matrix.map((row) => row[col]));
}

function multiply(a: number[][], b: number[][]): number[][] {
  return a.map((row) => b[0].map((_, col) => row.reduce((sum, value, index) => sum + value * b[index][col], 0)));
}

function multiplyVector(a: number[][], b: number[]): number[] {
  return a.map((row) => row.reduce((sum, value, index) => sum + value * b[index], 0));
}

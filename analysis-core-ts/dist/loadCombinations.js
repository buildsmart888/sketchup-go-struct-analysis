export function activeCombination(model) {
    const found = model.loadCombinations.find((item) => item.name === model.activeCombination);
    if (found)
        return found;
    if (model.loadCombinations[0])
        return model.loadCombinations[0];
    return { name: "1.0DL", method: "ASD", factors: { DL: 1 } };
}
export function combinedNodalLoads(model) {
    const combination = activeCombination(model);
    const loads = new Map();
    for (const load of model.nodalLoads) {
        const factor = combination.factors[load.case] ?? 0;
        if (factor === 0)
            continue;
        const current = loads.get(load.nodeId) ?? { fxKg: 0, fyKg: 0, mzKgM: 0 };
        current.fxKg += (load.fxKg ?? 0) * factor;
        current.fyKg += (load.fyKg ?? 0) * factor;
        current.mzKgM += (load.mzKgM ?? 0) * factor;
        loads.set(load.nodeId, current);
    }
    return loads;
}

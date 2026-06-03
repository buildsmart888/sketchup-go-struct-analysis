export function solveLinearSystem(matrix, vector) {
    const size = vector.length;
    const a = matrix.map((row) => row.slice());
    const b = vector.slice();
    for (let pivot = 0; pivot < size; pivot += 1) {
        let maxRow = pivot;
        for (let row = pivot + 1; row < size; row += 1) {
            if (Math.abs(a[row][pivot]) > Math.abs(a[maxRow][pivot]))
                maxRow = row;
        }
        if (Math.abs(a[maxRow][pivot]) < 1e-12) {
            throw new Error("Singular stiffness matrix");
        }
        if (maxRow !== pivot) {
            [a[pivot], a[maxRow]] = [a[maxRow], a[pivot]];
            [b[pivot], b[maxRow]] = [b[maxRow], b[pivot]];
        }
        const pivotValue = a[pivot][pivot];
        for (let col = pivot; col < size; col += 1)
            a[pivot][col] /= pivotValue;
        b[pivot] /= pivotValue;
        for (let row = 0; row < size; row += 1) {
            if (row === pivot)
                continue;
            const factor = a[row][pivot];
            if (Math.abs(factor) < 1e-15)
                continue;
            for (let col = pivot; col < size; col += 1)
                a[row][col] -= factor * a[pivot][col];
            b[row] -= factor * b[pivot];
        }
    }
    return b;
}
export function zeroMatrix(size) {
    return Array.from({ length: size }, () => Array.from({ length: size }, () => 0));
}

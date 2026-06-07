require 'fileutils'

html_path = 'c:/Users/g_np2/OneDrive/Programe/go_struct_analysis/go_struct_analysis/templates/gotruss_dialog.html'
html = File.read(html_path)

js_geometry_code = <<~'JAVASCRIPT'
        function generateTrussGeometry(params) {
            let n = parseInt(params.N) || 10;
            let ne_left = parseInt(params.Ne_left) || 1;
            let ne_right = parseInt(params.Ne_right) || 1;
            let l = parseFloat(params.L) || 0.5;
            let he = parseFloat(params.He) || 0.5;
            let hm = parseFloat(params.Hm) || 1.0;
            let truss_type = params.truss_type || 'flat_pratt';

            let nodes = [];
            let elements = [];
            let supports = [];
            let loads = [];

            // Bottom nodes
            for (let i = 0; i <= n; i++) {
                nodes.push({ id: i, x: i * l, y: 0.0, type: 'bottom' });
            }

            // Top nodes
            let mid_idx = n / 2.0;
            for (let i = 0; i <= n; i++) {
                let h = he + (hm - he) * (1.0 - Math.abs(i - mid_idx) / mid_idx);
                nodes.push({ id: n + 1 + i, x: i * l, y: h, type: 'top' });
            }

            // Elements
            for (let i = 0; i < n; i++) {
                elements.push({ n1: i, n2: i + 1, type: 'Bottom Chord' });
            }
            for (let i = 0; i < n; i++) {
                elements.push({ n1: n + 1 + i, n2: n + 1 + i + 1, type: 'Top Chord' });
            }

            // Webs
            for (let i = 0; i <= n; i++) {
                elements.push({ n1: i, n2: n + 1 + i, type: 'web' });
            }
            
            for (let p = 0; p < n; p++) {
                if (truss_type === 'flat_pratt') {
                    if (p < n / 2.0) elements.push({ n1: n + 1 + p, n2: p + 1, type: 'web' });
                    else if (p >= n / 2.0) elements.push({ n1: p, n2: n + 1 + p + 1, type: 'web' });
                } else if (truss_type === 'pratt_asym') {
                    elements.push({ n1: n + 1 + p, n2: p + 1, type: 'web' });
                } else if (truss_type === 'howe_sym') {
                    if (p < n / 2.0) elements.push({ n1: p, n2: n + 1 + p + 1, type: 'web' });
                    else if (p >= n / 2.0) elements.push({ n1: n + 1 + p, n2: p + 1, type: 'web' });
                }
            }

            // Supports
            supports.push({ node: ne_left, dx: true, dy: true });
            supports.push({ node: n - ne_right, dx: false, dy: true });

            // Loads
            let nodal_loads = {}; // id => { DL: 0, LL: 0 }
            let initLoad = (id) => { if(!nodal_loads[id]) nodal_loads[id] = {DL: 0, LL: 0}; };

            let dl_factor = parseFloat(params.dl_factor) || 1.0;
            let ll_factor = parseFloat(params.ll_factor) || 1.0;

            (params.uniform_loads || []).forEach(ul => {
                let w = parseFloat(ul.w);
                let x1 = parseFloat(ul.x1);
                let x2 = parseFloat(ul.x2);
                let factor = ul.type === 'LL' ? ll_factor : dl_factor;
                let w_fact = w * factor;
                
                let chord_nodes = nodes.filter(nd => nd.type.toLowerCase() === (ul.chord || 'Top').toLowerCase());
                chord_nodes.forEach((nd, idx) => {
                    let trib_start = idx === 0 ? nd.x : (nd.x + chord_nodes[idx-1].x) / 2.0;
                    let trib_end = idx === chord_nodes.size - 1 ? nd.x : (nd.x + chord_nodes[idx+1].x) / 2.0;
                    if(idx === chord_nodes.length - 1) trib_end = nd.x; // fix
                    let overlap_start = Math.max(trib_start, x1);
                    let overlap_end = Math.min(trib_end, x2);
                    if (overlap_start < overlap_end) {
                        initLoad(nd.id);
                        nodal_loads[nd.id][ul.type] -= w_fact * (overlap_end - overlap_start);
                    }
                });
            });

            (params.point_loads || []).forEach(pl => {
                let p_val = parseFloat(pl.p);
                let x = parseFloat(pl.x);
                let factor = pl.type === 'LL' ? ll_factor : dl_factor;
                let p_fact = p_val * factor;
                
                let chord_nodes = nodes.filter(nd => nd.type.toLowerCase() === (pl.chord || 'Top').toLowerCase());
                let closest = null; let minD = 99999;
                chord_nodes.forEach(nd => {
                    let d = Math.abs(nd.x - x);
                    if (d < minD) { minD = d; closest = nd; }
                });
                if (closest && minD < 0.01) {
                    initLoad(closest.id);
                    nodal_loads[closest.id][pl.type] -= p_fact;
                }
            });

            for (let [id, ld] of Object.entries(nodal_loads)) {
                if (ld.DL !== 0 || ld.LL !== 0) {
                    loads.push({ node: parseInt(id), fx: 0, fy: ld.DL + ld.LL, case: (ld.DL !== 0 && ld.LL !== 0) ? 'DL+LL' : (ld.DL !== 0 ? 'DL' : 'LL'), val_dl: ld.DL, val_ll: ld.LL });
                }
            }

            return { nodes: nodes, elements: elements, supports: supports, loads: loads };
        }

        function updateGeometryPreview() {
            let model = gatherInputs();
            model.geometry = generateTrussGeometry(model.parameters);
            currentModel = model;
            // Draw real-time
            let c1 = document.getElementById('canvas-geometry');
            let c2 = document.getElementById('canvas-loads');
            if(c1 && c1.offsetParent) renderTrussGeometry(c1, model.geometry);
            if(c2 && c2.offsetParent) renderAppliedLoads(c2, model.geometry, model.parameters);
        }
JAVASCRIPT

# Insert the javascript code right before gatherInputs
unless html.include?("function generateTrussGeometry")
  html.sub!("function gatherInputs()", "#{js_geometry_code}\n        function gatherInputs()")
end

# Update inputs to trigger preview
html.gsub!(/id="inp-he" value="0.5" step="0.1"/, 'id="inp-he" value="0.5" step="0.1" oninput="updateGeometryPreview()"')
html.gsub!(/id="inp-hm" value="1.0" step="0.1"/, 'id="inp-hm" value="1.0" step="0.1" oninput="updateGeometryPreview()"')
html.gsub!(/id="inp-truss-type"/, 'id="inp-truss-type" onchange="updateGeometryPreview()"')
html.gsub!(/onchange="updateDefaultUniformLoad\(\)"/, 'onchange="updateDefaultUniformLoad(); updateGeometryPreview()"')

# Modify gatherInputs to attach geometry
html.sub!(/currentModel\.trussName = document\.getElementById\('inp-trussname'\)\.value;\s+return currentModel;/, 
          "currentModel.trussName = document.getElementById('inp-trussname').value;\n    currentModel.geometry = generateTrussGeometry(currentModel.parameters);\n    return currentModel;")

# Update renderAppliedLoads to use geometry nodes
new_render_applied = <<~'JAVASCRIPT'
        function renderAppliedLoads(canvas, geo, params) {
    if(!canvas.offsetParent) return;
    let ctx = setupCanvas(canvas);
    let bounds = getBounds(geo.nodes);
    let tf = getTransform(canvas, bounds, 80);

    ctx.lineWidth = 1;
    ctx.strokeStyle = '#cccccc';
    geo.elements.forEach(el => {
        let n1 = geo.nodes[el.n1];
        let n2 = geo.nodes[el.n2];
        ctx.beginPath(); ctx.moveTo(tf.x(n1.x), tf.y(n1.y)); ctx.lineTo(tf.x(n2.x), tf.y(n2.y)); ctx.stroke();
    });

    if (params.uniform_loads) {
        let uOffsetTop = 0; let uOffsetBot = 0;
        params.uniform_loads.forEach((ul, idx) => {
            let w = ul.w; if(!w) return;
            let x1 = ul.x1; let x2 = ul.x2;
            let isTop = (ul.chord || 'Top').toLowerCase() === 'top';
            let isDL = (ul.type || 'DL') === 'DL';
            
            let yOffsetPx = isTop ? -20 - (uOffsetTop * 18) : 20 + (uOffsetBot * 18);
            if(isTop) uOffsetTop++; else uOffsetBot++;
            
            ctx.strokeStyle = isDL ? 'rgba(255, 0, 0, 0.4)' : 'rgba(0, 0, 255, 0.4)';
            ctx.fillStyle = isDL ? 'rgba(255, 0, 0, 0.1)' : 'rgba(0, 0, 255, 0.1)';
            
            let chordNodes = geo.nodes.filter(n => n.type.toLowerCase() === (isTop ? 'top' : 'bottom')).sort((a,b)=>a.x-b.x);
            let pts = [];
            chordNodes.forEach(nd => {
                if(nd.x >= x1 && nd.x <= x2) pts.push({x: nd.x, y: nd.y});
            });
            if(pts.length < 2 && chordNodes.length > 0) { // Fallback if points don't align exactly
                pts = chordNodes.filter(n => n.x >= Math.floor(x1) && n.x <= Math.ceil(x2));
            }
            if(pts.length === 0) return;

            ctx.beginPath();
            pts.forEach((p, i) => {
                let px = tf.x(p.x); let py = tf.y(p.y) + yOffsetPx;
                if(i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
            });
            for(let i = pts.length - 1; i >= 0; i--) {
                let px = tf.x(pts[i].x); let py = tf.y(pts[i].y) + yOffsetPx + (isTop ? -10 : 10);
                ctx.lineTo(px, py);
            }
            ctx.closePath(); ctx.fill(); ctx.stroke();
            
            ctx.strokeStyle = isDL ? 'rgba(255, 0, 0, 0.6)' : 'rgba(0, 0, 255, 0.6)';
            pts.forEach(p => {
                let px = tf.x(p.x); let py = tf.y(p.y) + yOffsetPx;
                let arrowLen = isTop ? -10 : 10;
                ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px, py + arrowLen); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px - 3, py + (isTop ? -3 : 3)); ctx.lineTo(px + 3, py + (isTop ? -3 : 3)); ctx.stroke();
            });
            
            let mx = tf.x((x1+x2)/2); let my = tf.y(pts[Math.floor(pts.length/2)].y) + yOffsetPx + (isTop ? -15 : 22);
            ctx.fillStyle = isDL ? 'rgba(255, 0, 0, 1)' : 'rgba(0, 0, 255, 1)';
            ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
            ctx.fillText(`${w} kg/m [${ul.type}]`, mx, my);
        });
    }

    if (params.point_loads) {
        let pCounts = {};
        params.point_loads.forEach(pl => {
            let p_val = pl.p; if(!p_val) return;
            let x = pl.x; let isTop = (pl.chord || 'Top').toLowerCase() === 'top';
            let isDL = (pl.type || 'DL') === 'DL';
            
            let chordNodes = geo.nodes.filter(n => n.type.toLowerCase() === (isTop ? 'top' : 'bottom'));
            let closest = chordNodes.reduce((prev, curr) => Math.abs(curr.x - x) < Math.abs(prev.x - x) ? curr : prev);
            if(Math.abs(closest.x - x) > 0.01) return;

            let key = `${closest.id}_${isTop}`;
            pCounts[key] = (pCounts[key] || 0) + 1;
            let offsetIdx = pCounts[key] - 1;
            let px = tf.x(closest.x) + (offsetIdx * 12);
            let py = tf.y(closest.y) + (isTop ? -5 : 5);
            let arrowLen = isTop ? -25 : 25;
            
            ctx.strokeStyle = isDL ? 'rgba(255, 0, 0, 0.8)' : 'rgba(0, 0, 255, 0.8)';
            ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px, py + arrowLen); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px - 4, py + (isTop ? -4 : 4)); ctx.lineTo(px + 4, py + (isTop ? -4 : 4)); ctx.stroke();
            
            ctx.fillStyle = isDL ? 'rgba(255, 0, 0, 1)' : 'rgba(0, 0, 255, 1)';
            ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
            ctx.fillText(`${p_val} kg [${pl.type}]`, px, py + (isTop ? -30 : 35));
        });
    }
    drawDimensions(ctx, geo, tf);
}
JAVASCRIPT

# Replace renderAppliedLoads
html.sub!(/function renderAppliedLoads\(canvas, geo, params\) \{.*?drawDimensions\(ctx, geo, tf\);\n\s*\}/m, new_render_applied)

# Add updateGeometryPreview to DOMContentLoaded
html.sub!(/window\.addEventListener\('resize', renderAll\);/, "window.addEventListener('resize', renderAll);\n            updateGeometryPreview();")
html.sub!(/addUniformLoad\(100, 0, p\.N \* p\.L, 'Top', 'DL'\);/, "addUniformLoad(100, 0, p.N * p.L, 'Top', 'DL');\n        updateGeometryPreview();")
html.sub!(/function addUniformLoad.*?tbody\.appendChild\(tr\);/m, '\0' + "\n    updateGeometryPreview();")
html.sub!(/function addPointLoad.*?tbody\.appendChild\(tr\);/m, '\0' + "\n    updateGeometryPreview();")

File.write(html_path, html)

puts "Updated JS."

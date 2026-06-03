path = 'c:/Users/g_np2/OneDrive/Programe/sketchup-mcp-prototype/sketchup-extension/go_struct_analysis/templates/gobeam_dialog.html'
content = File.read(path)

# 1. Update CSS for tables
css_old = %Q{      .point-table { margin-top: 8px; table-layout: fixed; }
      .point-table th, .point-table td { padding: 5px 6px; }
      .point-table th:nth-child(1), .point-table td:nth-child(1) { width: 84px; }
      .point-table th:nth-child(2), .point-table td:nth-child(2) { width: 68px; }
      .point-table th:nth-child(3), .point-table td:nth-child(3) { width: 150px; }
      .point-table th:nth-child(4), .point-table td:nth-child(4) { width: 64px; }
      .point-table input, .point-table select { height: 30px; padding: 3px 7px; }
      .point-table button.danger { min-width: 52px; padding: 4px 7px; }}
css_new = %Q{      .load-table { margin-top: 8px; table-layout: fixed; width: 100%; }
      .load-table th, .load-table td { padding: 5px 6px; }
      .load-table input, .load-table select { height: 30px; padding: 3px 7px; width: 100%; box-sizing: border-box; }
      .load-table button.danger { min-width: 52px; padding: 4px 7px; }
      
      .point-table th:nth-child(1), .point-table td:nth-child(1) { width: 84px; }
      .point-table th:nth-child(2), .point-table td:nth-child(2) { width: 68px; }
      .point-table th:nth-child(3), .point-table td:nth-child(3) { width: 110px; }
      .point-table th:nth-child(4), .point-table td:nth-child(4) { width: 64px; }

      .uniform-table th:nth-child(1), .uniform-table td:nth-child(1) { width: 74px; }
      .uniform-table th:nth-child(2), .uniform-table td:nth-child(2) { width: 58px; }
      .uniform-table th:nth-child(3), .uniform-table td:nth-child(3) { width: 58px; }
      .uniform-table th:nth-child(4), .uniform-table td:nth-child(4) { width: 80px; }
      .uniform-table th:nth-child(5), .uniform-table td:nth-child(5) { width: 64px; }}
content.sub!(css_old, css_new)

# 2. Remove Method dropdown
method_old = %Q{            <div class="row">
              <label>Method</label>
              <select id="designMethod" onchange="syncProject()">
                <option value="ASD">ASD</option>
                <option value="LRFD">LRFD</option>
              </select>
              <span></span>
            </div>
}
content.sub!(method_old, "")

# 3. Replace Uniform Load inputs with table
ul_inputs_old = %Q{            <div class="row">
              <label>Uniform Load</label>
              <input id="uniformLoad" type="number" step="0.01" min="0" oninput="updateSelectedSpan()">
              <span>kg/m</span>
            </div>
            <div class="row">
              <label>Uniform Case</label>
              <select id="uniformLoadCase" onchange="updateSelectedSpan()"></select>
              <span></span>
            </div>}
ul_inputs_new = %Q{            <div class="actions">
              <button class="soft" onclick="addUniformLoad()">Add Uniform Load</button>
            </div>
            <table class="load-table uniform-table">
              <thead><tr><th>w kg/m</th><th>x1 m</th><th>x2 m</th><th>Case</th><th></th></tr></thead>
              <tbody id="uniformLoadRows"></tbody>
            </table>}
content.sub!(ul_inputs_old, ul_inputs_new)

# Update point table class
content.sub!(/<table class="point-table">/, '<table class="load-table point-table">')

# 4. JS: defaultCombinations
combo_js_old = %Q{      function defaultCombinations() {
        return [
          { name: "1.0DL", method: "ASD", factors: { DL: 1, LL: 0 } },
          { name: "DL + LL", method: "ASD", factors: { DL: 1, LL: 1 } },
          { name: "1.2DL + 1.6LL", method: "LRFD", factors: { DL: 1.2, LL: 1.6 } },
          { name: "Custom", method: "ASD", factors: { DL: 1, LL: 0 } }
        ];
      }}
combo_js_new = %Q{      function defaultCombinations() {
        return [
          { name: "1.0DL [Service]", method: "ASD", factors: { DL: 1, LL: 0 } },
          { name: "1.0DL + 1.0LL [Service]", method: "ASD", factors: { DL: 1, LL: 1 } },
          { name: "1.4DL + 1.7LL [EIT / กฎกระทรวง]", method: "LRFD", factors: { DL: 1.4, LL: 1.7 } },
          { name: "1.2DL + 1.6LL [ACI / วสท. ใหม่]", method: "LRFD", factors: { DL: 1.2, LL: 1.6 } },
          { name: "Custom", method: "ASD", factors: { DL: 1, LL: 0 } }
        ];
      }}
content.sub!(combo_js_old, combo_js_new)

# 5. JS: remove designMethod dependencies
content.sub!(/model.projectInfo.designMethod = document.getElementById\("designMethod"\).value \|\| "ASD";/, "")
content.sub!(/document.getElementById\("designMethod"\).value = model.projectInfo.designMethod \|\| \(combo && combo.method\) \|\| "ASD";/, "")
content.sub!(/combo.method = document.getElementById\("designMethod"\).value \|\| combo.method \|\| "ASD";/, "")
content.sub!(/<option value=".*? \+ \(item.method \|\| "ASD"\) \+ "\]<\/option>";/, '<option value="\' + escapeAttr(item.name) + \'"\' + (item.name === model.activeCombination ? " selected" : "") + ">" + item.name + "</option>";')

# 6. JS: addSpan updates
add_span_old = %Q{          uniformLoadKgM: Number(last.uniformLoadKgM) || 0,
          uniformLoadCase: last.uniformLoadCase || "DL",}
add_span_new = %Q{          uniformLoads: last.uniformLoads ? JSON.parse(JSON.stringify(last.uniformLoads)) : [{ wKgM: 0, x1M: 0, x2M: 4, case: "DL" }],}
content.sub!(add_span_old, add_span_new)

# 7. JS: updateSelectedSpan updates
update_span_old = %Q{        span.uniformLoadKgM = Math.max(numberValue("uniformLoad", span.uniformLoadKgM), 0);
        span.uniformLoadCase = document.getElementById("uniformLoadCase").value || "DL";}
update_span_new = %Q{        span.uniformLoads = (span.uniformLoads || []).map(function(load) {
          var x1 = clamp(Number(load.x1M) || 0, 0, span.lengthM);
          var x2 = clamp(Number(load.x2M) || span.lengthM, 0, span.lengthM);
          if (x1 > x2) { var t = x1; x1 = x2; x2 = t; }
          return { wKgM: Math.max(Number(load.wKgM) || 0, 0), x1M: x1, x2M: x2, case: load.case || "DL" };
        });}
content.sub!(update_span_old, update_span_new)
content.sub!(/renderPointLoads\(\);/, "renderUniformLoads();\n        renderPointLoads();")

# 8. JS: new uniform load functions
render_ui_old = %Q{        document.getElementById("spanLength").value = span.lengthM;
        document.getElementById("uniformLoad").value = span.uniformLoadKgM;
        document.getElementById("uniformLoadCase").innerHTML = caseOptions(span.uniformLoadCase || "DL");}
render_ui_new = %Q{        document.getElementById("spanLength").value = span.lengthM;}
content.sub!(render_ui_old, render_ui_new)
content.sub!(/renderPointLoads\(\);/, "renderUniformLoads();\n        renderPointLoads();")

new_funcs = %Q{
      function renderUniformLoads() {
        var span = model.spans[selectedSpan];
        var rows = (span.uniformLoads || []).map(function(load, index) {
          return '<tr><td><input type="number" step="0.01" min="0" value="' + escapeAttr(load.wKgM) + '" oninput="updateUniformLoad(' + index + ', \\'wKgM\\', this.value)"></td>' +
            '<td><input type="number" step="0.01" min="0" max="' + escapeAttr(span.lengthM) + '" value="' + escapeAttr(load.x1M) + '" oninput="updateUniformLoad(' + index + ', \\'x1M\\', this.value)"></td>' +
            '<td><input type="number" step="0.01" min="0" max="' + escapeAttr(span.lengthM) + '" value="' + escapeAttr(load.x2M) + '" oninput="updateUniformLoad(' + index + ', \\'x2M\\', this.value)"></td>' +
            '<td><select onchange="updateUniformLoad(' + index + ', \\'case\\', this.value)">' + caseOptions(load.case || "DL", true) + '</select></td>' +
            '<td><button class="danger" onclick="deleteUniformLoad(' + index + ')">Delete</button></td></tr>';
        }).join("");
        document.getElementById("uniformLoadRows").innerHTML = rows || '<tr><td colspan="5" class="muted">No uniform loads</td></tr>';
      }

      function addUniformLoad() {
        var span = model.spans[selectedSpan];
        span.uniformLoads = span.uniformLoads || [];
        span.uniformLoads.push({ wKgM: 1000, x1M: 0, x2M: span.lengthM, case: "DL" });
        renderUniformLoads();
        gobeamSetStatus("Uniform load added. Press Analyze to update diagrams.", true);
      }

      function updateUniformLoad(index, key, value) {
        var span = model.spans[selectedSpan];
        var load = span.uniformLoads[index];
        load[key] = key === "case" ? value : Number(value) || 0;
        if (key === "wKgM") load.wKgM = Math.max(load.wKgM, 0);
        if (key === "x1M" || key === "x2M") load[key] = clamp(load[key], 0, span.lengthM);
      }

      function deleteUniformLoad(index) {
        model.spans[selectedSpan].uniformLoads.splice(index, 1);
        renderUniformLoads();
      }
}
content.sub!(/function renderPointLoads\(\) \{/, new_funcs.strip + "\n\n      function renderPointLoads() {")

File.write(path, content)

module GOStructAnalysis
  module Gotruss
    GOTRUSS_VERSION = 1

    def show_gotruss_dialog(args = {})
      puts '[GO Struct Analysis] Opening Gotruss dialog...'
      has_model_data = args.key?(:model_data) || args.key?('model_data')
      model = has_model_data ? (args[:model_data] || args['model_data']) : default_gotruss_model
      # Geometry is now generated in Javascript, so we can't analyze the default model here
      result = has_model_data ? analyze_gotruss_model(model) : { 'ok' => false }
      dialog = ensure_gotruss_dialog
      dialog.set_html(gotruss_dialog_html(model, result))
      present_dialog(dialog, width: 1360, height: 860, left: 60, top: 60)
    rescue StandardError => e
      puts "[GO Struct Analysis] Gotruss failed: #{format_error(e)}"
      UI.messagebox("Gotruss failed:\n#{format_error(e)}")
    end

    def ensure_gotruss_dialog
      return @gotruss_dialog if defined?(@gotruss_dialog) && @gotruss_dialog

      if defined?(UI::HtmlDialog)
        @gotruss_dialog = UI::HtmlDialog.new(
          dialog_title: 'Pratt Truss Analysis',
          preferences_key: 'go_struct_analysis.gotruss',
          scrollable: true,
          resizable: true,
          width: 1360,
          height: 860,
          style: UI::HtmlDialog::STYLE_DIALOG
        )
      else
        @gotruss_dialog = UI::WebDialog.new(
          'Pratt Truss Analysis',
          true,
          'go_struct_analysis.gotruss',
          1360,
          860,
          60,
          60,
          true
        )
      end
      add_gotruss_callbacks(@gotruss_dialog)
      clear_dialog_on_close(@gotruss_dialog, :@gotruss_dialog)

      @gotruss_dialog
    end

    def add_gotruss_callbacks(dialog)
      dialog.add_action_callback('gotrussAnalyze') { |_context, payload| gotruss_analyze_callback(payload) }
      dialog.add_action_callback('gotrussSave') { |_context, payload| gotruss_save_callback(payload) }
      dialog.add_action_callback('gotrussLoad') { |_context, _payload| gotruss_load_callback }
      dialog.add_action_callback('gotrussDraw3D') { |_context, payload| gotruss_draw3d_callback(payload) }
      dialog.add_action_callback('save_custom_section') do |_context, payload|
        data = GOStructAnalysis::Support.parse_dialog_payload(payload)
        GOStructAnalysis::SectionDatabase.save_user_section(data)
        dialog.execute_script("window.SECTION_DATABASE = #{GOStructAnalysis::SectionDatabase.get_full_database_json}; if (window.renderSecDBTable) renderSecDBTable();")
      end
      dialog.add_action_callback('gotrussReport') { |_context, payload| gotruss_report_callback(payload) }
    end

    def gotruss_analyze_callback(payload)
      model = parse_dialog_payload(payload)
      result = analyze_gotruss_model(model)
      ensure_gotruss_dialog.execute_script("window.gotrussReceiveAnalysis(#{JSON.generate(result)})")
    rescue StandardError => e
      ensure_gotruss_dialog.execute_script("window.gotrussSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def gotruss_save_callback(payload)
      model = parse_dialog_payload(payload)
      default_name = "T1.gotruss.json"
      path = UI.savepanel('Save GOTruss', Dir.home, default_name)
      return if blank?(path)

      File.write(path, JSON.pretty_generate(model))
      ensure_gotruss_dialog.execute_script("window.gotrussSetStatus(#{JSON.generate("Saved: #{path}")}, true)")
    rescue StandardError => e
      ensure_gotruss_dialog.execute_script("window.gotrussSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def gotruss_load_callback
      path = UI.openpanel('Load GOTruss', Dir.home, 'GOTruss Files|*.gotruss.json;*.json||')
      return if blank?(path)

      model = JSON.parse(File.read(path))
      result = analyze_gotruss_model(model)
      ensure_gotruss_dialog.execute_script("window.gotrussReceiveModel(#{JSON.generate(model)}, #{JSON.generate(result)})")
      ensure_gotruss_dialog.execute_script("window.gotrussSetStatus(#{JSON.generate("Loaded: #{path}")}, true)")
    rescue StandardError => e
      ensure_gotruss_dialog.execute_script("window.gotrussSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def gotruss_report_callback(payload)
      model = parse_dialog_payload(payload)
      result = analyze_gotruss_model(model)
      dialog = ensure_gotruss_report_dialog
      dialog.set_html(gotruss_report_html(model, result))
      present_dialog(dialog, width: 900, height: 900, left: 100, top: 100)
    rescue StandardError => e
      ensure_gotruss_dialog.execute_script("window.gotrussSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def ensure_gotruss_report_dialog
      return @gotruss_report_dialog if defined?(@gotruss_report_dialog) && @gotruss_report_dialog

      if defined?(UI::HtmlDialog)
        @gotruss_report_dialog = UI::HtmlDialog.new(
          dialog_title: 'Pratt Truss Analysis Report',
          preferences_key: 'go_struct_analysis.gotruss_report',
          scrollable: true,
          resizable: true,
          width: 900,
          height: 900,
          style: UI::HtmlDialog::STYLE_DIALOG
        )
      else
        @gotruss_report_dialog = UI::WebDialog.new(
          'Pratt Truss Analysis Report',
          true,
          'go_struct_analysis.gotruss_report',
          900,
          900,
          100,
          100,
          true
        )
      end
      clear_dialog_on_close(@gotruss_report_dialog, :@gotruss_report_dialog)

      @gotruss_report_dialog
    end

    def gotruss_report_html(model, result)
      render_template(
        'gotruss_report.html',
        'MODEL_JSON' => json_script_value(model),
        'RESULT_JSON' => json_script_value(result),
        'REPORT_DATE' => Time.now.strftime('%d/%m/%Y %H:%M'),
        'BODY_HTML' => gotruss_report_body_html(model, result)
      )
    end

    def gotruss_report_body_html(model, full_result)
      info = model['projectInfo'] || {}
      sections = []

      params = model['parameters'] || {}
      res = full_result[:result] || full_result['result'] || {}
      geo = full_result[:geometry] || full_result['geometry'] || {}


combo_str = params['combo'] ? params['combo'].upcase : '1.0DL + 1.0LL'
      dl_factor = params['dl_factor'] || 1.0
      ll_factor = params['ll_factor'] || 1.0
      u_loads = params['uniform_loads'] || []
      p_loads = params['point_loads'] || []

      u_loads_html = u_loads.map { |l| "w=#{l['w']}kg/m (x:#{l['x1']}-#{l['x2']}m) on #{l['chord']} [#{l['type']}]" }.join("<br>")
      p_loads_html = p_loads.map { |l| "P=#{l['p']}kg (x:#{l['x']}m) on #{l['chord']} [#{l['type']}]" }.join("<br>")
      loads_summary = ""
      loads_summary += "<b>Uniform Loads:</b><br>#{u_loads_html}<br>" if u_loads.any?
      loads_summary += "<b>Point Loads:</b><br>#{p_loads_html}" if p_loads.any?
      loads_summary = "None" if loads_summary.empty?

      sections << <<-HTML
<section class="report-page">
  <header class="report-head">
    <div class="logo">GO<br>Truss</div>
    <table>
      <tr><td>Project : #{html_escape(info['project'])}</td><td>Truss : #{html_escape(model['trussName'])}</td></tr>
      <tr><td>Company : #{html_escape(info['company'])}</td><td>Engineer : #{html_escape(info['engineer'])}</td></tr>
      <tr><td>Location : #{html_escape(info['location'])}</td><td>Date : #{html_escape(Time.now.strftime('%Y-%m-%d'))}</td></tr>
      <tr><td>Method : #{html_escape(info['designMethod'])}</td><td>Combination: #{combo_str} (DL:#{dl_factor}, LL:#{ll_factor})</td></tr>
    </table>
  </header>
  <h1>Pratt Truss Analysis Report</h1>
  <div style="font-size:12px; margin-bottom: 10px; padding: 10px; background: #f9f9f9; border: 1px solid #ddd;">
    <p style="margin:0 0 5px 0;"><b>Geometry:</b> Panels(N)=#{params['N']}, Length=#{round_value(params['L'], 2)}m, H(ends)=#{round_value(params['He'], 2)}m, H(mid)=#{round_value(params['Hm'], 2)}m</p>
    <div style="margin:0;">#{loads_summary}</div>
  </div>
  <h2>(1) Applied Loads (Uniform/Point Loads)</h2>
  <div class="diagram" data-diagram="applied"></div>
  <h2>(2) Equivalent Nodal Loads</h2>
  <div class="diagram" data-diagram="truss"></div>
  <h2>(3) Member Forces</h2>
  <div class="diagram" data-diagram="forces"></div>
  <h2>(4) Member Detail</h2>
  <table class="data-table">
    <thead>
      <tr><th>Member</th><th>Area (cm2)</th><th>Tension Max (kg)</th><th>Compression Max (kg)</th></tr>
    </thead>
    <tbody>
      <tr><td>Chord (Top & Bottom)</td><td>#{round_value(params['Ac'], 2)}</td><td>#{round_value(res[:max_t_chord] || res['max_t_chord'], 2)} (M#{(res[:max_t_chord_m] || res['max_t_chord_m']).to_i + 1})</td><td>#{round_value(res[:max_c_chord] || res['max_c_chord'], 2)} (M#{(res[:max_c_chord_m] || res['max_c_chord_m']).to_i + 1})</td></tr>
      <tr><td>Web (Vert & Diag)</td><td>#{round_value(params['Aw'], 2)}</td><td>#{round_value(res[:max_t_web] || res['max_t_web'], 2)} (M#{(res[:max_t_web_m] || res['max_t_web_m']).to_i + 1})</td><td>#{round_value(res[:max_c_web] || res['max_c_web'], 2)} (M#{(res[:max_c_web_m] || res['max_c_web_m']).to_i + 1})</td></tr>
    </tbody>
  </table>
  <h2>(5) Deformation Summary</h2>
  <div class="diagram" data-diagram="deformation"></div>
  <p>Maximum Displacement: &Delta;x = #{round_value((res[:max_dx] || res['max_dx'] || 0.0) * 1000, 2)} mm, &Delta;y = #{round_value((res[:max_dy] || res['max_dy'] || 0.0) * 1000, 2)} mm</p>
</section>
      HTML

      # Build Member Forces Table
      forces_table_rows = []
      total_top_chord_len = 0.0
      total_bot_chord_len = 0.0
      total_chord_len = 0.0
      total_web_len = 0.0

      elements = geo['elements'] || []
      nodes = geo['nodes'] || []
      member_forces = res['member_forces'] || res[:member_forces] || []

      elements.each_with_index do |el, i|
        n1 = nodes[el['n1']]
        n2 = nodes[el['n2']]
        dx = n2['x'].to_f - n1['x'].to_f
        dy = n2['y'].to_f - n1['y'].to_f
        len = Math.sqrt(dx*dx + dy*dy)

        type = el['type'] || ''
        if type == 'Top Chord'
          total_top_chord_len += len
          total_chord_len += len
        elsif type == 'Bottom Chord'
          total_bot_chord_len += len
          total_chord_len += len
        elsif type.include?('Chord')
          total_chord_len += len
        else
          total_web_len += len
        end

        f = member_forces[i] || 0.0
        state = f > 0.01 ? '(T)' : (f < -0.01 ? '(C)' : '(0)')

        forces_table_rows << "<tr><td>M#{i+1}</td><td>N#{el[:n1]}-N#{el[:n2]}</td><td>#{type}</td><td>#{round_value(f, 2)} #{state}</td><td>#{round_value(len, 3)}</td></tr>"
      end

      sections << <<-HTML
<section class="report-page">
  <h2>(6) Member Forces & Length</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>Member</th>
        <th>Nodes</th>
        <th>Type</th>
        <th>Force (kg)</th>
        <th>Length (m)</th>
      </tr>
    </thead>
    <tbody>
      #{forces_table_rows.join("\n      ")}
      <tr style="background-color: #f8f9fa; font-weight: bold;">
        <td colspan="4" style="text-align: right;">Total Chord Length:</td>
        <td>#{round_value(total_chord_len, 3)} m (Top: #{round_value(total_top_chord_len, 3)} m, Bottom: #{round_value(total_bot_chord_len, 3)} m)</td>
      </tr>
      <tr style="background-color: #f8f9fa; font-weight: bold;">
        <td colspan="4" style="text-align: right;">Total Web Length:</td>
        <td>#{round_value(total_web_len, 3)} m</td>
      </tr>
      <tr style="background-color: #eef4f3; font-weight: bold;">
        <td colspan="4" style="text-align: right;">Total Truss Length:</td>
        <td>#{round_value(total_chord_len + total_web_len, 3)} m</td>
      </tr>
    </tbody>
  </table>
</section>
      HTML

      reactions = res['reactions'] || res[:reactions] || {}
      reactions_rows = []
      reactions.each do |node_id, r|
        rx = r['rx'] || r[:rx] || 0.0
        ry = r['ry'] || r[:ry] || 0.0
        reactions_rows << "<tr><td>Node #{node_id}</td><td>#{round_value(rx, 2)}</td><td>#{round_value(ry, 2)}</td></tr>"
      end

      sections << <<-HTML
<section class="report-page">
  <h2>(7) Support Reactions</h2>
  <table class="data-table">
    <thead>
      <tr>
        <th>Node</th>
        <th>Rx (kg)</th>
        <th>Ry (kg)</th>
      </tr>
    </thead>
    <tbody>
      #{reactions_rows.join("\n      ")}
    </tbody>
  </table>
</section>
<section class="report-page">
  <h2>(8) Analysis Summary</h2>
  <pre style="font-size:11px; background:#f9f9f9; padding:10px; white-space:pre-wrap; border:1px solid #ddd; line-height: 1.4;">#{html_escape(res[:summary] || res['summary'] || '')}</pre>
</section>
      HTML

      sections.join("\n")
    end

    def gotruss_dialog_html(model, result)
      render_template(
        'gotruss_dialog.html',
        'MODEL_JSON' => json_script_value(model),
        'RESULT_JSON' => json_script_value(result),
        'SECTION_DATABASE_JSON' => GOStructAnalysis::SectionDatabase.get_full_database_json
      )
    end

    def default_gotruss_model
      {
        'version' => GOTRUSS_VERSION,
        'trussName' => 'T1',
        'projectInfo' => {
          'project' => 'Structure',
          'company' => 'GO Structure',
          'engineer' => 'Structural Engineer',
          'location' => 'Bangkok THAILAND',
          'designMethod' => 'ASD'
        },
        'parameters' => {
          'N' => 10,
          'Ne_left' => 1,
          'Ne_right' => 1,
          'L' => 0.5,
          'He' => 0.5,
          'Hm' => 1.0,
          'Pe' => 500.0,
          'Pi' => 1000.0,
          'Ac' => 20.0,
          'Aw' => 10.0,
          'E' => 20_000_000_000.0 # Steel in kg/m2 (approx 2.0E6 kg/cm2)
        }
      }
    end

    def analyze_gotruss_model(model)
      # 1. Use Geometry directly from Javascript payload
      gen = model['geometry']
      nodes = gen['nodes']

      # Convert keys to symbols as expected by solver
      sym_nodes = nodes.map { |n| { id: n['id'].to_i, x: n['x'].to_f, y: n['y'].to_f, type: n['type'] } }
      sym_elements = gen['elements'].map { |e| { n1: e['n1'].to_i, n2: e['n2'].to_i, type: e['type'] } }
      sym_supports = gen['supports'].map { |s| { node: s['node'].to_i, dx: s['dx'], dy: s['dy'] } }
      sym_loads = gen['loads'].map { |l| { node: l['node'].to_i, fx: l['fx'].to_f, fy: l['fy'].to_f, case: l['case'] } }

      # 2. Build and Solve DSM (Direct Stiffness Method)
      result = solve_truss(sym_nodes, sym_elements, sym_supports, sym_loads, model['parameters'])

      {
        'ok' => true,
        'model' => model,
        'geometry' => gen,
        'result' => result
      }
    end


    def solve_truss(nodes, elements, supports, loads, params)
      e = params['E'].to_f
      ac = params['Ac'].to_f / 10000.0 # cm2 to m2
      aw = params['Aw'].to_f / 10000.0
      e = params['E'].to_f
      e = 20_000_000_000.0 if e <= 0.0

      num_nodes = nodes.length
      num_dof = num_nodes * 2

      # K matrix (1D array mapping for simplicity or Array of Arrays)
      k_global = Array.new(num_dof) { Array.new(num_dof, 0.0) }

      elements.each_with_index do |el, idx|
        n1 = nodes[el[:n1]]
        n2 = nodes[el[:n2]]

        dx = n2[:x] - n1[:x]
        dy = n2[:y] - n1[:y]
        len = Math.sqrt(dx**2 + dy**2)
        cx = dx / len
        cy = dy / len

        area = el[:type].to_s.include?('Chord') ? ac : aw
        k = e * area / len

        k_local = [
          [cx*cx, cx*cy, -cx*cx, -cx*cy],
          [cx*cy, cy*cy, -cx*cy, -cy*cy],
          [-cx*cx, -cx*cy, cx*cx, cx*cy],
          [-cx*cy, -cy*cy, cx*cy, cy*cy]
        ]

        dofs = [el[:n1]*2, el[:n1]*2+1, el[:n2]*2, el[:n2]*2+1]

        4.times do |i|
          4.times do |j|
            k_global[dofs[i]][dofs[j]] += k * k_local[i][j]
          end
        end
      end

      # Force vector
      f = Array.new(num_dof, 0.0)
      loads.each do |load|
        n = load[:node]
        f[n*2] += load[:fx] || 0.0
        f[n*2+1] += load[:fy] || 0.0
      end

      # Apply Boundary Conditions (Penalty Method)
      penalty = 1.0e12
      supports.each do |sup|
        n = sup[:node]
        if sup[:dx]
          k_global[n*2][n*2] += penalty
        end
        if sup[:dy]
          k_global[n*2+1][n*2+1] += penalty
        end
      end

      # Stabilize matrix for mechanisms (unsupported nodes in Vierendeel/Warren)
      (0...num_dof).each do |i|
        k_global[i][i] += 1e-3
      end

      # Solve KU = F using simple Gaussian Elimination
      begin
        u = solve_linear_system(k_global, f)
      rescue ArgumentError => e
        if e.message.include?('Singular')
          raise ArgumentError, "Structure is unstable (Mechanism). Please add vertical/diagonal webs or check supports."
        else
          raise e
        end
      end

      # Calculate Member Forces
      member_forces = []
      max_t_chord = 0; max_c_chord = 0
      max_t_web = 0; max_c_web = 0
      max_t_chord_m = -1; max_c_chord_m = -1
      max_t_web_m = -1; max_c_web_m = -1

      elements.each_with_index do |el, idx|
        n1 = nodes[el[:n1]]
        n2 = nodes[el[:n2]]

        dx = n2[:x] - n1[:x]
        dy = n2[:y] - n1[:y]
        len = Math.sqrt(dx**2 + dy**2)
        cx = dx / len
        cy = dy / len

        is_chord = el[:type].downcase.include?('chord')
        area = is_chord ? ac : aw

        u1x = u[el[:n1]*2]; u1y = u[el[:n1]*2+1]
        u2x = u[el[:n2]*2]; u2y = u[el[:n2]*2+1]

        # force = (EA/L) * [-cx -cy cx cy] * U
        force = (e * area / len) * (-cx*u1x - cy*u1y + cx*u2x + cy*u2y)

        member_forces << force

        if is_chord
          if force > max_t_chord
            max_t_chord = force
            max_t_chord_m = idx
          end
          if force < max_c_chord
            max_c_chord = force
            max_c_chord_m = idx
          end
        else
          if force > max_t_web
            max_t_web = force
            max_t_web_m = idx
          end
          if force < max_c_web
            max_c_web = force
            max_c_web_m = idx
          end
        end
      end

      # Formatting displacements
      displacements = []
      max_dx = 0; max_dy = 0
      max_dx_n = -1; max_dy_n = -1
      nodes.each_with_index do |node, i|
        dx = u[i*2]
        dy = u[i*2+1]
        displacements << { dx: dx, dy: dy }

        if dx.abs > max_dx.abs
          max_dx = dx.abs
          max_dx_n = i
        end
        if dy.abs > max_dy.abs
          max_dy = dy.abs
          max_dy_n = i
        end
      end
      # Calculate Reactions
      reactions = {}
      supports.each do |sup|
        n = sup[:node]
        rx = sup[:dx] ? -penalty * u[n*2] : 0.0
        ry = sup[:dy] ? -penalty * u[n*2+1] : 0.0
        reactions[n] = { rx: rx, ry: ry }
      end

      # Generate Step-by-Step Summary
      summary = "TRUSS ANALYSIS SUMMARY\n"
      summary += "======================\n\n"

      summary += "1. Node Generation\n"
      nodes.each do |n|
        summary += "  Node #{n[:id]}: x = #{round_value(n[:x],3)} m, y = #{round_value(n[:y],3)} m [#{n[:type]}]\n"
      end

      summary += "\n2. Element Generation\n"
      elements.each_with_index do |el, i|
        summary += "  Element #{i+1}: Node #{el[:n1]} -> Node #{el[:n2]} [#{el[:type]}]\n"
      end

      summary += "\n3. Degrees of Freedom (DOF)\n"
      summary += "  Total Nodes: #{num_nodes}, Total DOF: #{num_dof}\n"

      summary += "\n4. Applied Nodal Forces (F vector)\n"
      loads.each do |l|
        summary += "  Node #{l[:node]}: Fx = #{round_value(l[:fx]||0,2)} kg, Fy = #{round_value(l[:fy]||0,2)} kg (#{l[:case]})\n"
      end

      summary += "\n5. Displacement Solution (U vector)\n"
      displacements.each_with_index do |d, i|
        summary += "  Node #{i}: dx = #{round_value(d[:dx]*1000, 4)} mm, dy = #{round_value(d[:dy]*1000, 4)} mm\n"
      end

      summary += "\n6. Member Forces\n"
      member_forces.each_with_index do |f, i|
        state = f > 0.01 ? '(Tension)' : (f < -0.01 ? '(Compression)' : '(Zero)')
        summary += "  Element #{i+1}: #{round_value(f, 2)} kg #{state}\n"
      end
      summary += "\n7. Support Reactions\n"
      reactions.each do |n, r|
        summary += "  Node #{n}: Rx = #{round_value(r[:rx], 2)} kg, Ry = #{round_value(r[:ry], 2)} kg\n"
      end

      {
        reactions: reactions,
        displacements: displacements,
        member_forces: member_forces,
        max_t_chord: max_t_chord,
        max_c_chord: max_c_chord,
        max_t_web: max_t_web,
        max_c_web: max_c_web,
        max_t_chord_m: max_t_chord_m,
        max_c_chord_m: max_c_chord_m,
        max_t_web_m: max_t_web_m,
        max_c_web_m: max_c_web_m,
        max_dx: max_dx,
        max_dy: max_dy,
        max_dx_n: max_dx_n,
        max_dy_n: max_dy_n,
        summary: summary
      }
    end
  end
end

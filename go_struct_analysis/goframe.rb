module GOStructAnalysis
  module Goframe

    def show_goframe_dialog(args = {})
      puts '[GO Struct Analysis] Opening Goframe dialog...'
      has_model_data = args.key?(:model_data) || args.key?('model_data')
      model = has_model_data ? (args[:model_data] || args['model_data']) : default_goframe_model
      result = has_model_data ? analyze(model) : { 'ok' => false }
      dialog = ensure_goframe_dialog
      dialog.set_html(goframe_dialog_html(model, result))
      present_dialog(dialog, width: 1200, height: 800, left: 100, top: 100)
    rescue StandardError => e
      puts "[GO Struct Analysis] Goframe failed: #{format_error(e)}"
      UI.messagebox("Goframe failed:\n#{format_error(e)}")
    end

    def ensure_goframe_dialog
      return @goframe_dialog if defined?(@goframe_dialog) && @goframe_dialog

      if defined?(UI::HtmlDialog)
        @goframe_dialog = UI::HtmlDialog.new(
          dialog_title: 'GO Frame Analysis (2D Rigid Frame)',
          preferences_key: 'com.gostruct.goframe',
          scrollable: true,
          resizable: true,
          width: 1200,
          height: 800,
          min_width: 800,
          min_height: 600,
          style: UI::HtmlDialog::STYLE_DIALOG
        )
      else
        @goframe_dialog = UI::WebDialog.new(
          'GO Frame Analysis (2D Rigid Frame)',
          true,
          'com.gostruct.goframe',
          1200,
          800,
          100,
          100,
          true
        )
      end
      add_goframe_callbacks(@goframe_dialog)
      clear_dialog_on_close(@goframe_dialog, :@goframe_dialog)

      @goframe_dialog
    end

    def add_goframe_callbacks(dialog)
      dialog.add_action_callback('analyze_frame') { |_context, payload| goframe_analyze_callback(payload) }
      dialog.add_action_callback('goframeSave') { |_context, payload| goframe_save_callback(payload) }
      dialog.add_action_callback('goframeLoad') { |_context, _payload| goframe_load_callback }
      dialog.add_action_callback('save_custom_section') do |_context, payload|
        data = GOStructAnalysis::Support.parse_dialog_payload(payload)
        GOStructAnalysis::SectionDatabase.save_user_section(data)
        dialog.execute_script("SECTION_DATABASE = #{GOStructAnalysis::SectionDatabase.get_full_database_json}; if (window.renderSecDBTable) renderSecDBTable();")
      end
      dialog.add_action_callback('export_3d') do |_context, data|
        begin
          GOStructAnalysis::DrawGoframe.draw(data)
        rescue StandardError => e
          UI.messagebox("Export Error:\n#{e.message}\n\n#{e.backtrace.join("\n")}")
        end
      end
      dialog.add_action_callback('export_report') do |_context, data|
        begin
          generate_report(data)
        rescue StandardError => e
          UI.messagebox("Report Error:\n#{e.message}\n\n#{e.backtrace.join("\n")}")
        end
      end
    end

    def goframe_analyze_callback(payload)
      model = parse_dialog_payload(payload)
      result = analyze(model)
      ensure_goframe_dialog.execute_script("window.goframeReceiveModel(null, #{JSON.generate(result)})")
    rescue StandardError => e
      ensure_goframe_dialog.execute_script("window.goframeSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def goframe_save_callback(payload)
      model = parse_dialog_payload(payload)
      default_name = "Frame1.goframe.json"
      path = UI.savepanel('Save GOFrame', Dir.home, default_name)
      return if blank?(path)

      File.write(path, JSON.pretty_generate(model))
      ensure_goframe_dialog.execute_script("window.goframeSetStatus(#{JSON.generate("Saved: #{path}")}, true)")
    rescue StandardError => e
      ensure_goframe_dialog.execute_script("window.goframeSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def goframe_load_callback
      path = UI.openpanel('Load GOFrame', Dir.home, 'GOFrame Files|*.goframe.json;*.json||')
      return if blank?(path)

      model = JSON.parse(File.read(path))
      result = analyze(model)
      ensure_goframe_dialog.execute_script("window.goframeReceiveModel(#{JSON.generate(model)}, #{JSON.generate(result)})")
      ensure_goframe_dialog.execute_script("window.goframeSetStatus(#{JSON.generate("Loaded: #{path}")}, true)")
    rescue StandardError => e
      ensure_goframe_dialog.execute_script("window.goframeSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def goframe_dialog_html(model, result)
      render_template(
        'goframe_dialog.html',
        'MODEL_JSON' => json_script_value(model),
        'RESULT_JSON' => json_script_value(result),
        'SECTION_DATABASE_JSON' => GOStructAnalysis::SectionDatabase.get_full_database_json
      )
    end

    def default_goframe_model
      {}
    end

    def build_t(angle)
      c = Math.cos(angle)
      s = Math.sin(angle)
      [
        [c, s, 0, 0, 0, 0],
        [-s, c, 0, 0, 0, 0],
        [0, 0, 1, 0, 0, 0],
        [0, 0, 0, c, s, 0],
        [0, 0, 0, -s, c, 0],
        [0, 0, 0, 0, 0, 1]
      ]
    end

    def build_tt(angle)
      c = Math.cos(angle)
      s = Math.sin(angle)
      [
        [c, -s, 0, 0, 0, 0],
        [s, c, 0, 0, 0, 0],
        [0, 0, 1, 0, 0, 0],
        [0, 0, 0, c, -s, 0],
        [0, 0, 0, s, c, 0],
        [0, 0, 0, 0, 0, 1]
      ]
    end

    def build_local_k(e, a, i, l, release = 'Rigid-Rigid')
      k = Array.new(6) { Array.new(6, 0.0) }
      eal = e * a / l
      ei_l = e * i / l
      ei_l2 = 6.0 * e * i / (l**2)
      ei_l3 = 12.0 * e * i / (l**3)

      k[0][0] = eal;  k[0][3] = -eal
      k[3][0] = -eal; k[3][3] = eal

      if release == 'Rigid-Rigid' || release == nil || release == ''
        k[1][1] = ei_l3;   k[1][2] = ei_l2;  k[1][4] = -ei_l3;  k[1][5] = ei_l2
        k[2][1] = ei_l2;   k[2][2] = 4*ei_l; k[2][4] = -ei_l2;  k[2][5] = 2*ei_l
        k[4][1] = -ei_l3;  k[4][2] = -ei_l2; k[4][4] = ei_l3;   k[4][5] = -ei_l2
        k[5][1] = ei_l2;   k[5][2] = 2*ei_l; k[5][4] = -ei_l2;  k[5][5] = 4*ei_l
      elsif release == 'Pin-Rigid'
        ei3_l3 = 3.0 * e * i / (l**3)
        ei3_l2 = 3.0 * e * i / (l**2)
        ei3_l  = 3.0 * e * i / l
        k[1][1] = ei3_l3;  k[1][4] = -ei3_l3; k[1][5] = ei3_l2
        k[4][1] = -ei3_l3; k[4][4] = ei3_l3;  k[4][5] = -ei3_l2
        k[5][1] = ei3_l2;  k[5][4] = -ei3_l2; k[5][5] = ei3_l
      elsif release == 'Rigid-Pin'
        ei3_l3 = 3.0 * e * i / (l**3)
        ei3_l2 = 3.0 * e * i / (l**2)
        ei3_l  = 3.0 * e * i / l
        k[1][1] = ei3_l3;  k[1][2] = ei3_l2;  k[1][4] = -ei3_l3
        k[2][1] = ei3_l2;  k[2][2] = ei3_l;   k[2][4] = -ei3_l2
        k[4][1] = -ei3_l3; k[4][2] = -ei3_l2; k[4][4] = ei3_l3
      elsif release == 'Pin-Pin'
        # No bending stiffness
      end

      k
    end

    def compute_fixed_end_forces(wx1, wx2, wy1, wy2, l, release = 'Rigid-Rigid')
      fef = Array.new(6, 0.0)

      dwx = wx2 - wx1
      fef[0] = -(wx1 * l / 2.0) - (dwx * l / 6.0)
      fef[3] = -(wx1 * l / 2.0) - (dwx * l / 3.0)

      release = 'Rigid-Rigid' if release == nil || release == ''

      dwy = wy2 - wy1

      if release == 'Rigid-Rigid'
        fef[1] = -(wy1 * l / 2.0) - (3.0 * dwy * l / 20.0)
        fef[2] = -(wy1 * (l**2) / 12.0) - (dwy * (l**2) / 30.0)
        fef[4] = -(wy1 * l / 2.0) - (7.0 * dwy * l / 20.0)
        fef[5] =  (wy1 * (l**2) / 12.0) + (dwy * (l**2) / 20.0)
      elsif release == 'Pin-Rigid'
        fef[1] = -(3.0 * wy1 * l / 8.0) - (dwy * l / 10.0)
        fef[2] = 0.0
        fef[4] = -(5.0 * wy1 * l / 8.0) - (2.0 * dwy * l / 5.0)
        fef[5] =  (wy1 * (l**2) / 8.0) + (dwy * (l**2) / 15.0)
      elsif release == 'Rigid-Pin'
        fef[1] = -(5.0 * wy1 * l / 8.0) - (13.0 * dwy * l / 120.0)
        fef[2] = -(wy1 * (l**2) / 8.0) - (7.0 * dwy * (l**2) / 120.0)
        fef[4] = -(3.0 * wy1 * l / 8.0) - (47.0 * dwy * l / 120.0)
        fef[5] = 0.0
      elsif release == 'Pin-Pin'
        fef[1] = -(wy1 * l / 2.0) - (dwy * l / 6.0)
        fef[2] = 0.0
        fef[4] = -(wy1 * l / 2.0) - (dwy * l / 3.0)
        fef[5] = 0.0
      end
      fef
    end

    def analyze(data)
      nodes = data['nodes'] || []
      elements = data['elements'] || []
      sections = data['sections'] || []
      loadcases = data['loadcases'] || ['DL']
      loadcombos = data['loadcombos'] || [{'name' => 'Comb 1', 'eq' => '1.0DL'}]
      nloads = data['nloads'] || []
      eloads = data['eloads'] || []
      settings = data['settings'] || {}
      include_sw = settings['include_self_weight'] == true

      steps = []
      steps << "1. Assembling Global Stiffness Matrix & Analyzing Topography"
      steps << "  Nodes: #{nodes.length}, Elements: #{elements.length}"

      num_nodes = nodes.length
      total_dofs = num_nodes * 3

      node_map = {}
      nodes.each_with_index { |n, i| node_map[n['id']] = i }

      sec_map = {}
      sections.each do |s|
        a_m2 = s['a'].to_f * 1e-4
        i_m4 = s['i'].to_f * 1e-8
        sec_map[s['id']] = { e: s['e'].to_f, a: a_m2, i: i_m4, density: s['density'].to_f }
      end

      k_global = Array.new(total_dofs) { Array.new(total_dofs, 0.0) }
      elem_results = {}

      elements.each do |el|
        id = el['id']
        n1_idx = node_map[el['n1']]
        n2_idx = node_map[el['n2']]
        sec = sec_map[el['sec']]
        release = el['release'] || 'Rigid-Rigid'
        next unless n1_idx && n2_idx && sec

        x1 = nodes[n1_idx]['x'].to_f
        y1 = nodes[n1_idx]['y'].to_f
        x2 = nodes[n2_idx]['x'].to_f
        y2 = nodes[n2_idx]['y'].to_f

        dx = x2 - x1
        dy = y2 - y1
        l = Math.sqrt(dx**2 + dy**2)
        angle = Math.atan2(dy, dx)

        k_local = build_local_k(sec[:e], sec[:a], sec[:i], l, release)
        t = build_t(angle)
        tt = build_tt(angle)

        k_temp = GOStructAnalysis::Suite::MatrixOperations.multiply(tt, k_local)
        k_g = GOStructAnalysis::Suite::MatrixOperations.multiply(k_temp, t)

        dof_map = [n1_idx*3, n1_idx*3+1, n1_idx*3+2, n2_idx*3, n2_idx*3+1, n2_idx*3+2]

        6.times do |i|
          6.times do |j|
            k_global[dof_map[i]][dof_map[j]] += k_g[i][j]
          end
        end

        elem_results[id] = {
          l: l, angle: angle, k_local: k_local, t: t, tt: tt, dof_map: dof_map,
          sec: sec, release: release, n1_idx: n1_idx, n2_idx: n2_idx
        }
      end

      # Apply Boundary Conditions to K
      fixed_dofs = []
      nodes.each do |n|
        idx = node_map[n['id']]
        sup = n['support']
        if sup == 'Fixed'
          fixed_dofs.push(idx*3, idx*3+1, idx*3+2)
        elsif sup == 'Pinned'
          fixed_dofs.push(idx*3, idx*3+1)
        elsif sup == 'RollerX'
          fixed_dofs.push(idx*3+1)
        elsif sup == 'RollerY'
          fixed_dofs.push(idx*3)
        end
      end

      # Fix unconnected rotational DOFs
      total_dofs.times do |i|
        if k_global[i][i].abs < 1e-9 && !fixed_dofs.include?(i)
          k_global[i][i] = 1.0
        end
      end

      fixed_dofs.each do |dof|
        total_dofs.times do |i|
          k_global[dof][i] = 0.0
          k_global[i][dof] = 0.0
        end
        k_global[dof][dof] = 1.0
      end

      steps << "2. Decomposing Global Stiffness Matrix"
      # Using LUP solve
      begin
        decomp = GOStructAnalysis::Suite::MatrixOperations.lup_decompose(k_global)
      rescue => e
        return { ok: false, error: "Matrix Singular. Structure may be unstable.\n#{e.message}" }
      end

      steps << "3. Processing Load Cases"

      results_by_case = {}

      loadcases.each do |lc|
        f_global = Array.new(total_dofs, 0.0)

        # Nodal loads for this case
        nloads.select{|l| l['lcase'] == lc}.each do |nl|
          idx = node_map[nl['node']]
          next unless idx
          f_global[idx*3] += nl['fx'].to_f
          f_global[idx*3+1] += nl['fy'].to_f
          f_global[idx*3+2] += nl['mz'].to_f
        end

        # Element loads for this case
        elem_fefs = {}
        elements.each do |el|
          id = el['id']
          res = elem_results[id]
          next unless res

          local_f_fixed = Array.new(6, 0.0)

          # Self-weight is typically assigned to DL
          if lc == 'DL' && include_sw && res[:sec][:density] > 0
            w_self = res[:sec][:a] * res[:sec][:density]
            sw_wx = (-w_self) * Math.sin(res[:angle])
            sw_wy = (-w_self) * Math.cos(res[:angle])
            fef = compute_fixed_end_forces(sw_wx, sw_wx, sw_wy, sw_wy, res[:l], res[:release])
            6.times { |i| local_f_fixed[i] += fef[i] }
          end

          eloads.select{|l| l['elem'] == id && l['lcase'] == lc}.each do |load|
            w1 = load['w1'] ? load['w1'].to_f : (load['w'] ? load['w'].to_f : 0.0)
            w2 = load['w2'] ? load['w2'].to_f : w1
            dir = load['dir']
            wx1, wy1, wx2, wy2 = 0.0, 0.0, 0.0, 0.0
            if dir == 'Local Y'
              wy1 = w1
              wy2 = w2
            elsif dir == 'Global Y'
              wx1 = w1 * Math.sin(res[:angle])
              wy1 = w1 * Math.cos(res[:angle])
              wx2 = w2 * Math.sin(res[:angle])
              wy2 = w2 * Math.cos(res[:angle])
            end
            fef = compute_fixed_end_forces(wx1, wx2, wy1, wy2, res[:l], res[:release])
            6.times { |i| local_f_fixed[i] += fef[i] }
          end

          elem_fefs[id] = local_f_fixed

          has_loads = local_f_fixed.any? { |v| v.abs > 1e-9 }
          if has_loads
            global_f_fixed = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(res[:tt], local_f_fixed)
            6.times do |i|
              f_global[res[:dof_map][i]] -= global_f_fixed[i]
            end
          end
        end

        # Zero out f_global at fixed dofs
        fixed_dofs.each { |dof| f_global[dof] = 0.0 }

        # Solve
        u_global = GOStructAnalysis::Suite::MatrixOperations.lup_solve(decomp, f_global)

        # Store results for this case
        case_nodes_results = nodes.map { |n| { id: n['id'], x: n['x'], y: n['y'], dx: 0.0, dy: 0.0, rz: 0.0, fx: 0.0, fy: 0.0, mz: 0.0 } }
        nodes.each_with_index do |n, i|
          case_nodes_results[i][:dx] = u_global[i*3]
          case_nodes_results[i][:dy] = u_global[i*3+1]
          case_nodes_results[i][:rz] = u_global[i*3+2]
        end

        case_member_forces = []

        elements.each do |el|
          id = el['id']
          res = elem_results[id]
          next unless res

          u_g = res[:dof_map].map { |dof| u_global[dof] }
          u_l = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(res[:t], u_g)

          f_l_k = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(res[:k_local], u_l)
          f_l = Array.new(6, 0.0)
          6.times { |i| f_l[i] = f_l_k[i] + elem_fefs[id][i] }

          case_member_forces << {
            id: id,
            n1: el['n1'],
            n2: el['n2'],
            n1_forces: { axial: f_l[0], shear: f_l[1], moment: f_l[2] },
            n2_forces: { axial: f_l[3], shear: f_l[4], moment: f_l[5] }
          }

          f_g = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(res[:tt], f_l)
          n1_idx = res[:n1_idx]
          n2_idx = res[:n2_idx]

          if fixed_dofs.include?(n1_idx*3) || fixed_dofs.include?(n1_idx*3+1) || fixed_dofs.include?(n1_idx*3+2)
            case_nodes_results[n1_idx][:fx] += f_g[0]
            case_nodes_results[n1_idx][:fy] += f_g[1]
            case_nodes_results[n1_idx][:mz] += f_g[2]
          end
          if fixed_dofs.include?(n2_idx*3) || fixed_dofs.include?(n2_idx*3+1) || fixed_dofs.include?(n2_idx*3+2)
            case_nodes_results[n2_idx][:fx] += f_g[3]
            case_nodes_results[n2_idx][:fy] += f_g[4]
            case_nodes_results[n2_idx][:mz] += f_g[5]
          end
        end

        nloads.select{|l| l['lcase'] == lc}.each do |nl|
          idx = node_map[nl['node']]
          if fixed_dofs.include?(idx*3)
            case_nodes_results[idx][:fx] -= nl['fx'].to_f
          end
          if fixed_dofs.include?(idx*3+1)
            case_nodes_results[idx][:fy] -= nl['fy'].to_f
          end
          if fixed_dofs.include?(idx*3+2)
            case_nodes_results[idx][:mz] -= nl['mz'].to_f
          end
        end

        results_by_case[lc] = { nodes: case_nodes_results, elements: case_member_forces }
      end

      steps << "4. Processing Load Combinations & Envelopes"

      combos_results = {}

      loadcombos.each do |cinfo|
        cname = cinfo['name']
        factors = cinfo['factors'] || {}

        if cinfo['eq'] && cinfo['eq'].is_a?(String) && factors.empty?
          eq = cinfo['eq']
          terms = eq.scan(/[+-]?[^-+]+/)
          terms.each do |term|
            term = term.strip
            next if term.empty?
            if term =~ /([+-]?\s*\d*\.?\d*)\s*(.+)/
              f_str = $1.to_s
              l_str = $2.to_s
              fact = f_str.gsub(/\s+/, '')
              fact = "1.0" if fact.empty? || fact == "+"
              fact = "-1.0" if fact == "-"
              fact = fact.to_f
              lcase = l_str.strip
              factors[lcase] = fact
            end
          end
        end

        combo_nodes = nodes.map { |n| { id: n['id'], x: n['x'], y: n['y'], dx: 0.0, dy: 0.0, rz: 0.0, fx: 0.0, fy: 0.0, mz: 0.0 } }
        combo_elems = elements.map do |el|
          {
            id: el['id'], n1: el['n1'], n2: el['n2'],
            n1_forces: { axial: 0.0, shear: 0.0, moment: 0.0 },
            n2_forces: { axial: 0.0, shear: 0.0, moment: 0.0 }
          }
        end

        factors.each do |lc, factor|
          next unless results_by_case[lc]

          # Accumulate nodes
          results_by_case[lc][:nodes].each_with_index do |rn, i|
            combo_nodes[i][:dx] += rn[:dx] * factor
            combo_nodes[i][:dy] += rn[:dy] * factor
            combo_nodes[i][:rz] += rn[:rz] * factor
            combo_nodes[i][:fx] += rn[:fx] * factor
            combo_nodes[i][:fy] += rn[:fy] * factor
            combo_nodes[i][:mz] += rn[:mz] * factor
          end

          # Accumulate elements
          results_by_case[lc][:elements].each_with_index do |re, i|
            combo_elems[i][:n1_forces][:axial] += re[:n1_forces][:axial] * factor
            combo_elems[i][:n1_forces][:shear] += re[:n1_forces][:shear] * factor
            combo_elems[i][:n1_forces][:moment] += re[:n1_forces][:moment] * factor
            combo_elems[i][:n2_forces][:axial] += re[:n2_forces][:axial] * factor
            combo_elems[i][:n2_forces][:shear] += re[:n2_forces][:shear] * factor
            combo_elems[i][:n2_forces][:moment] += re[:n2_forces][:moment] * factor
          end
        end

        combos_results[cname] = { nodes: combo_nodes, elements: combo_elems }
      end

      # Envelopes
      env_nodes = nodes.map { |n| { id: n['id'], x: n['x'], y: n['y'], dx: 0.0, dy: 0.0, rz: 0.0, fx: 0.0, fy: 0.0, mz: 0.0 } }
      env_elems = elements.map do |el|
        {
          id: el['id'], n1: el['n1'], n2: el['n2'],
          n1_forces: { axial: 0.0, shear: 0.0, moment: 0.0 },
          n2_forces: { axial: 0.0, shear: 0.0, moment: 0.0 }
        }
      end

      if combos_results.any?
        combos_results.values.each_with_index do |cres, idx|
          if idx == 0
            # Initialize envelope with first combo
            cres[:nodes].each_with_index do |rn, i|
              env_nodes[i][:dx] = rn[:dx]
              env_nodes[i][:dy] = rn[:dy]
              env_nodes[i][:rz] = rn[:rz]
              env_nodes[i][:fx] = rn[:fx]
              env_nodes[i][:fy] = rn[:fy]
              env_nodes[i][:mz] = rn[:mz]
            end
            cres[:elements].each_with_index do |re, i|
              env_elems[i][:n1_forces][:axial] = re[:n1_forces][:axial]
              env_elems[i][:n1_forces][:shear] = re[:n1_forces][:shear]
              env_elems[i][:n1_forces][:moment] = re[:n1_forces][:moment]
              env_elems[i][:n2_forces][:axial] = re[:n2_forces][:axial]
              env_elems[i][:n2_forces][:shear] = re[:n2_forces][:shear]
              env_elems[i][:n2_forces][:moment] = re[:n2_forces][:moment]
            end
          else
            # Max absolute value logic (or you can do true max/min)
            # For simplicity, Envelope stores the value that has max absolute magnitude
            # preserving its sign.
            cres[:nodes].each_with_index do |rn, i|
              env_nodes[i][:dx] = rn[:dx] if rn[:dx].abs > env_nodes[i][:dx].abs
              env_nodes[i][:dy] = rn[:dy] if rn[:dy].abs > env_nodes[i][:dy].abs
              env_nodes[i][:rz] = rn[:rz] if rn[:rz].abs > env_nodes[i][:rz].abs
              env_nodes[i][:fx] = rn[:fx] if rn[:fx].abs > env_nodes[i][:fx].abs
              env_nodes[i][:fy] = rn[:fy] if rn[:fy].abs > env_nodes[i][:fy].abs
              env_nodes[i][:mz] = rn[:mz] if rn[:mz].abs > env_nodes[i][:mz].abs
            end
            cres[:elements].each_with_index do |re, i|
              [:axial, :shear, :moment].each do |k|
                env_elems[i][:n1_forces][k] = re[:n1_forces][k] if re[:n1_forces][k].abs > env_elems[i][:n1_forces][k].abs
                env_elems[i][:n2_forces][k] = re[:n2_forces][k] if re[:n2_forces][k].abs > env_elems[i][:n2_forces][k].abs
              end
            end
          end
        end
      end

      steps << "  Total Load Cases Evaluated: #{loadcases.length}"
      steps << "  Total Combinations Evaluated: #{loadcombos.length}"
      steps << "  Analysis Complete."

      {
        ok: true,
        nodes: env_nodes,
        elements: env_elems,
        steps: steps,
        cases: results_by_case,
        combos: combos_results
      }
    end

    def generate_report(data)
      model_data = data['model'] || {}
      result_data = data['result'] || {}

      template_path = File.join(GOStructAnalysis::TEMPLATE_ROOT, 'goframe_report.html')
      html = File.read(template_path, encoding: 'UTF-8')

      # Build body HTML
      body_html = goframe_report_body_html(model_data, result_data, data['report_combos'] || ['Envelope'])

      # Replace placeholders
      html.gsub!('{{MODEL_JSON}}', json_script_value(model_data))
      html.gsub!('{{RESULT_JSON}}', json_script_value(result_data))
      html.gsub!('{{REPORT_DATE}}', Time.now.strftime('%d/%m/%Y %H:%M'))
      html.gsub!('{{TABLE_OPTIONS_JSON}}', json_script_value(data['report_tables'] || ['t0','t1','t2','t3','t4','t5','t6','t7']))
      html.gsub!('{{BODY_HTML}}', body_html)

      # Show dialog
      report_dialog = UI::HtmlDialog.new(
        {
          dialog_title: 'GO Frame Analysis Report',
          preferences_key: 'com.gostruct.goframe.report',
          scrollable: true,
          resizable: true,
          width: 1000,
          height: 800,
          left: 150,
          top: 150,
          style: UI::HtmlDialog::STYLE_DIALOG
        }
      )
      report_dialog.set_html(html)
      report_dialog.show
    end

    def goframe_report_body_html(model, full_result, report_combos)
      info = model['projectInfo'] || {}
      sections = []

      res = full_result || {}
      nodes = res['nodes'] || res[:nodes] || []
      elements = res['elements'] || res[:elements] || []
      steps = res['steps'] || res[:steps] || []

      sections_data = model['sections'] || []
      nloads = model['nloads'] || []
      eloads = model['eloads'] || []

      sections_html = sections_data.map { |s| "Sec #{s['id']}: <b>#{s['name'] || '-'}</b> (E=#{s['e']}, A=#{s['a']}, I=#{s['i']}, &rho;=#{s['density']})" }.join("<br>")
      nloads_html = nloads.map { |l| "N#{l['node']}: #{l['lcase']}=(Fx=#{l['fx']} kg, Fy=#{l['fy']} kg, Mz=#{l['mz']} kg&middot;m)" }.join("<br>")
      eloads_html = eloads.map { |l|
        w1 = l['w1'] || l['w'] || 0
        w2 = l['w2'] || w1
        if (w1 - w2).abs < 1e-3
          "E#{l['elem']}: #{l['lcase']}=#{w1} kg/m (#{l['dir']})"
        else
          "E#{l['elem']}: #{l['lcase']}=(w1=#{w1}, w2=#{w2} kg/m) (#{l['dir']})"
        end
      }.join("<br>")

      loads_summary = ""
      loads_summary += "<div style='margin-bottom:5px'><b>Sections:</b><br>#{sections_html}</div>" if sections_data.any?
      loads_summary += "<div style='margin-bottom:5px'><b>Nodal Loads:</b><br>#{nloads_html}</div>" if nloads.any?
      loads_summary += "<div style='margin-bottom:5px'><b>Element Loads:</b><br>#{eloads_html}</div>" if eloads.any?
      loads_summary = "None" if loads_summary.empty?

      max_dx = nodes.map { |n| (n['dx'] || n[:dx] || 0.0).to_f.abs }.max || 0.0
      max_dy = nodes.map { |n| (n['dy'] || n[:dy] || 0.0).to_f.abs }.max || 0.0

      num_supports = model['nodes'].count { |n| n['support'] != 'Free' }
      sections << <<-HTML
<section class="report-page">
  <header class="report-head">
    <div class="logo">GO<br>Struct</div>
    <table>
      <tr><td>Project : #{html_escape(info['project'] || '-')}</td><td>Engineer : #{html_escape(info['engineer'] || '-')}</td></tr>
      <tr><td>Structure : #{html_escape(info['name'] || 'GOFrame Project')}</td><td>Company : #{html_escape(info['company'] || '-')}</td></tr>
      <tr><td>Location : #{html_escape(info['location'] || '-')}</td><td>Date : #{Time.now.strftime('%Y-%m-%d %H:%M')}</td></tr>
      <tr><td>Method : #{html_escape(info['designMethod'] || 'Service/ASD')}</td><td></td></tr>
    </table>
  </header>
  <h1>2D Rigid Frame Analysis Report</h1>
  <div style="font-size:12px; margin-bottom: 10px; padding: 10px; background: #f9f9f9; border: 1px solid #ddd;">
    <p style="margin:0 0 5px 0;"><b>Geometry:</b> Nodes = #{model['nodes'].length}, Elements = #{model['elements'].length}, Supports = #{num_supports}</p>
    <div style="margin:0;">#{loads_summary}</div>
  </div>
  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Applied Loads</h2>
    <div class="diagram" data-diagram="loads"></div>
  </div>
  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Structural Geometry</h2>
    <div class="diagram" data-diagram="frame"></div>
  </div>
</section>
      HTML

      report_combos.each do |c_obj|
        cname = c_obj.is_a?(Hash) ? c_obj['name'] : c_obj
        clabel = c_obj.is_a?(Hash) ? c_obj['label'] : c_obj
        safe_cname = html_escape(cname)
        safe_clabel = html_escape(clabel)
        sections << <<-HTML
<section class="report-page">
  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Axial Force Diagram (AFD) - #{safe_clabel}</h2>
    <div class="diagram" data-diagram="afd" data-combo="#{safe_cname}"></div>
  </div>
  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Shear Force Diagram (SFD) - #{safe_clabel}</h2>
    <div class="diagram" data-diagram="sfd" data-combo="#{safe_cname}"></div>
  </div>
</section>

<section class="report-page">
  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Bending Moment Diagram (BMD) - #{safe_clabel}</h2>
    <div class="diagram" data-diagram="bmd" data-combo="#{safe_cname}"></div>
  </div>
  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Deformation Shape - #{safe_clabel}</h2>
    <div class="diagram" data-diagram="deformation" data-combo="#{safe_cname}"></div>
  </div>
</section>
        HTML
      end

      def self.build_result_tables_html(title, nodes, elements)
        forces_table_rows = []
        elements.each do |el|
          n1 = el['n1_forces'] || el[:n1_forces] || {}
          n2 = el['n2_forces'] || el[:n2_forces] || {}
          id = el['id'] || el[:id]
          forces_table_rows << "<tr><td>#{id}</td><td>#{round_value(n1[:axial]||n1['axial'], 2)}</td><td>#{round_value(n1[:shear]||n1['shear'], 2)}</td><td>#{round_value(n1[:moment]||n1['moment'], 2)}</td><td>#{round_value(n2[:axial]||n2['axial'], 2)}</td><td>#{round_value(n2[:shear]||n2['shear'], 2)}</td><td>#{round_value(n2[:moment]||n2['moment'], 2)}</td></tr>"
        end

        nodes_table_rows = []
        nodes.each do |n|
          id = n['id'] || n[:id]
          dx = n['dx'] || n[:dx] || 0.0
          dy = n['dy'] || n[:dy] || 0.0
          rot = n['rot'] || n[:rot] || 0.0
          nodes_table_rows << "<tr><td>#{id}</td><td>#{round_value(dx * 1000, 4)}</td><td>#{round_value(dy * 1000, 4)}</td><td>#{round_value(rot, 6)}</td></tr>"
        end

        reactions_rows = []
        nodes.each do |n|
          id = n['id'] || n[:id]
          fx = n['fx'] || n[:fx] || 0.0
          fy = n['fy'] || n[:fy] || 0.0
          mz = n['mz'] || n[:mz] || 0.0
          next if fx.abs < 1e-6 && fy.abs < 1e-6 && mz.abs < 1e-6
          reactions_rows << "<tr><td>#{id}</td><td>#{round_value(fx, 2)}</td><td>#{round_value(fy, 2)}</td><td>#{round_value(mz, 2)}</td></tr>"
        end
        reactions_rows << "<tr><td colspan='4'>No reactions found</td></tr>" if reactions_rows.empty?

        <<-HTML
<section class="report-page">
  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Member Forces Summary (#{html_escape(title)})</h2>
    <table class="data-table">
      <thead>
        <tr>
          <th rowspan="2">Element</th>
          <th colspan="3">Start Node (N1)</th>
          <th colspan="3">End Node (N2)</th>
        </tr>
        <tr>
          <th>Axial (kg)</th><th>Shear (kg)</th><th>Moment (kg-m)</th>
          <th>Axial (kg)</th><th>Shear (kg)</th><th>Moment (kg-m)</th>
        </tr>
      </thead>
      <tbody>
        #{forces_table_rows.join("\n        ")}
      </tbody>
    </table>
  </div>

  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Nodal Displacements (#{html_escape(title)})</h2>
    <table class="data-table">
      <thead>
        <tr><th>Node</th><th>&Delta;x (mm)</th><th>&Delta;y (mm)</th><th>Rotation (rad)</th></tr>
      </thead>
      <tbody>
        #{nodes_table_rows.join("\n        ")}
      </tbody>
    </table>
  </div>

  <div style="page-break-inside: avoid; margin-bottom: 20px;">
    <h2>Support Reactions (#{html_escape(title)})</h2>
    <table class="data-table">
      <thead>
        <tr><th>Node</th><th>Rx (kg)</th><th>Ry (kg)</th><th>Mz (kg-m)</th></tr>
      </thead>
      <tbody>
        #{reactions_rows.join("\n        ")}
      </tbody>
    </table>
  </div>
</section>
        HTML
      end

      sections << <<-HTML
<section class="report-page" style="padding-top: 20px;">
  <div id="report-tables-container"></div>
</section>
      HTML

      # Steps
      steps_html = steps.map { |s| html_escape(s) }.join("<br>")
      sections << <<-HTML
<section class="report-page">
  <h2>(10) Calculation Steps Overview</h2>
  <div class="calc-steps" style="font-family:monospace; font-size:12px; background:#f5f5f5; padding:10px; border:1px solid #ddd; white-space:pre-wrap;">
    #{steps_html}
  </div>
</section>
      HTML

      sections.join("\n")
    end
  end
end

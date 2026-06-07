module GOStructAnalysis
  module Goframe
    extend self

    def show_dialog
      @dialog ||= UI::HtmlDialog.new(
        {
          dialog_title: 'GO Frame Analysis (2D Rigid Frame)',
          preferences_key: 'com.gostruct.goframe',
          scrollable: true,
          resizable: true,
          width: 1200,
          height: 800,
          left: 100,
          top: 100,
          min_width: 800,
          min_height: 600,
          max_width: 10000,
          max_height: 10000,
          style: UI::HtmlDialog::STYLE_DIALOG
        }
      )

      html_path = File.join(GOStructAnalysis::TEMPLATE_ROOT, 'goframe_dialog.html')
      @dialog.set_file(html_path)

      @dialog.add_action_callback('analyze_frame') do |action_context, params|
        begin
          results = analyze(params)
          @dialog.execute_script("displayResults(#{results.to_json})")
        rescue StandardError => e
          UI.messagebox("Analysis Error:\n#{e.message}\n\n#{e.backtrace.join("\n")}")
        end
      end

      @dialog.add_action_callback('export_3d') do |action_context, data|
        begin
          GOStructAnalysis::DrawGoframe.draw(data)
        rescue StandardError => e
          UI.messagebox("Export Error:\n#{e.message}\n\n#{e.backtrace.join("\n")}")
        end
      end

      @dialog.add_action_callback('export_report') do |action_context, data|
        begin
          generate_report(data)
        rescue StandardError => e
          UI.messagebox("Report Error:\n#{e.message}\n\n#{e.backtrace.join("\n")}")
        end
      end

      @dialog.show
    end

    def build_local_k(e, a, i, l)
      k = Array.new(6) { Array.new(6, 0.0) }
      eal = e * a / l
      ei_l = e * i / l
      ei_l2 = 6.0 * e * i / (l**2)
      ei_l3 = 12.0 * e * i / (l**3)

      k[0][0] = eal;  k[0][3] = -eal
      k[3][0] = -eal; k[3][3] = eal

      k[1][1] = ei_l3;   k[1][2] = ei_l2;  k[1][4] = -ei_l3;  k[1][5] = ei_l2
      k[2][1] = ei_l2;   k[2][2] = 4*ei_l; k[2][4] = -ei_l2;  k[2][5] = 2*ei_l
      k[4][1] = -ei_l3;  k[4][2] = -ei_l2; k[4][4] = ei_l3;   k[4][5] = -ei_l2
      k[5][1] = ei_l2;   k[5][2] = 2*ei_l; k[5][4] = -ei_l2;  k[5][5] = 4*ei_l
      
      k
    end

    def build_t(angle)
      c = Math.cos(angle)
      s = Math.sin(angle)
      [
        [ c,  s,  0,  0,  0,  0],
        [-s,  c,  0,  0,  0,  0],
        [ 0,  0,  1,  0,  0,  0],
        [ 0,  0,  0,  c,  s,  0],
        [ 0,  0,  0, -s,  c,  0],
        [ 0,  0,  0,  0,  0,  1]
      ]
    end

    def build_tt(angle)
      c = Math.cos(angle)
      s = Math.sin(angle)
      [
        [ c, -s,  0,  0,  0,  0],
        [ s,  c,  0,  0,  0,  0],
        [ 0,  0,  1,  0,  0,  0],
        [ 0,  0,  0,  c, -s,  0],
        [ 0,  0,  0,  s,  c,  0],
        [ 0,  0,  0,  0,  0,  1]
      ]
    end

    def analyze(data)
      nodes = data['nodes'] || []
      elements = data['elements'] || []
      sections = data['sections'] || []
      nloads = data['nloads'] || []
      eloads = data['eloads'] || []
      
      settings = data['settings'] || {}
      include_sw = settings['include_self_weight'] == true

      num_nodes = nodes.length
      total_dofs = num_nodes * 3

      # Map node ids to indices
      node_map = {}
      nodes.each_with_index { |n, i| node_map[n['id']] = i }

      # Map section ids to properties
      sec_map = {}
      sections.each do |s|
        # Convert A from cm2 to m2, I from cm4 to m4
        a_m2 = s['a'].to_f * 1e-4
        i_m4 = s['i'].to_f * 1e-8
        sec_map[s['id']] = { e: s['e'].to_f, a: a_m2, i: i_m4, density: s['density'].to_f }
      end

      # 1. Assemble Global Stiffness Matrix (K) and Fixed End Forces
      k_global = Array.new(total_dofs) { Array.new(total_dofs, 0.0) }
      f_global = Array.new(total_dofs, 0.0)
      
      # Nodal Loads
      nloads.each do |nl|
        idx = node_map[nl['node']]
        next unless idx
        f_global[idx*3] += nl['fx'].to_f
        f_global[idx*3+1] += nl['fy'].to_f
        f_global[idx*3+2] += nl['mz'].to_f
      end

      elem_results = {}

      elements.each do |el|
        id = el['id']
        n1_idx = node_map[el['n1']]
        n2_idx = node_map[el['n2']]
        sec = sec_map[el['sec']]
        next unless n1_idx && n2_idx && sec

        x1 = nodes[n1_idx]['x'].to_f
        y1 = nodes[n1_idx]['y'].to_f
        x2 = nodes[n2_idx]['x'].to_f
        y2 = nodes[n2_idx]['y'].to_f

        dx = x2 - x1
        dy = y2 - y1
        l = Math.sqrt(dx**2 + dy**2)
        angle = Math.atan2(dy, dx)

        k_local = build_local_k(sec[:e], sec[:a], sec[:i], l)
        t = build_t(angle)
        tt = build_tt(angle)

        # Global element stiffness k_g = T^T * k_local * T
        k_temp = GOStructAnalysis::Suite::MatrixOperations.multiply(tt, k_local)
        k_g = GOStructAnalysis::Suite::MatrixOperations.multiply(k_temp, t)

        dof_map = [n1_idx*3, n1_idx*3+1, n1_idx*3+2, n2_idx*3, n2_idx*3+1, n2_idx*3+2]

        # Add to global K
        6.times do |i|
          6.times do |j|
            k_global[dof_map[i]][dof_map[j]] += k_g[i][j]
          end
        end

        # Calculate Element Loads and Fixed End Forces
        local_f_fixed = Array.new(6, 0.0)
        
        # Self-weight
        if include_sw && sec[:density] > 0
          w_self = sec[:a] * sec[:density] # kg/m
          sw_wx = (-w_self) * Math.sin(angle)
          sw_wy = (-w_self) * Math.cos(angle)
          
          local_f_fixed[0] += -sw_wx * l / 2.0
          local_f_fixed[1] += -sw_wy * l / 2.0
          local_f_fixed[2] += -sw_wy * (l**2) / 12.0
          local_f_fixed[3] += -sw_wx * l / 2.0
          local_f_fixed[4] += -sw_wy * l / 2.0
          local_f_fixed[5] += sw_wy * (l**2) / 12.0
        end
        
        el_loads = eloads.select { |load| load['elem'] == id }
        el_loads.each do |load|
          w = load['w'].to_f
          dir = load['dir']
          wx = 0.0
          wy = 0.0
          if dir == 'Local Y'
            wy = w
          elsif dir == 'Global Y'
            wx = w * Math.sin(angle)
            wy = w * Math.cos(angle)
          end

          # Fixed End Forces (Local)
          local_f_fixed[0] += -wx * l / 2.0
          local_f_fixed[1] += -wy * l / 2.0
          local_f_fixed[2] += -wy * (l**2) / 12.0
          local_f_fixed[3] += -wx * l / 2.0
          local_f_fixed[4] += -wy * l / 2.0
          local_f_fixed[5] += wy * (l**2) / 12.0
        end

        # Convert fixed end forces to global and subtract from global load vector (Equivalent Nodal Loads)
        has_elem_loads = el_loads.any? || (include_sw && sec[:density] > 0)
        if has_elem_loads
          global_f_fixed = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(tt, local_f_fixed)
          6.times do |i|
            f_global[dof_map[i]] -= global_f_fixed[i]
          end
        end

        elem_results[id] = {
          l: l, angle: angle, k_local: k_local, t: t, tt: tt, 
          dof_map: dof_map, local_f_fixed: local_f_fixed
        }
      end

      # Apply Boundary Conditions
      fixed_dofs = []
      nodes.each do |n|
        idx = node_map[n['id']]
        sup = n['support']
        if sup == 'Fixed'
          fixed_dofs.push(idx*3, idx*3+1, idx*3+2)
        elsif sup == 'Pinned'
          fixed_dofs.push(idx*3, idx*3+1)
        elsif sup == 'RollerX' # Free to move in X, fixed in Y
          fixed_dofs.push(idx*3+1)
        elsif sup == 'RollerY' # Free to move in Y, fixed in X
          fixed_dofs.push(idx*3)
        end
      end

      # Modify K and F for fixed DOFs
      fixed_dofs.each do |dof|
        total_dofs.times do |i|
          k_global[dof][i] = 0.0
          k_global[i][dof] = 0.0
        end
        k_global[dof][dof] = 1.0
        f_global[dof] = 0.0
      end

      # Solve Displacements (U)
      begin
        k_inv = GOStructAnalysis::Suite::MatrixOperations.invert(k_global)
        u_global = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(k_inv, f_global)
      rescue => e
        return { ok: false, error: "Matrix Singular. Structure may be unstable.\n#{e.message}" }
      end

      # Calculate Member Forces and Reactions
      member_forces = []
      nodes_results = nodes.map { |n| { id: n['id'], x: n['x'], y: n['y'], dx: 0, dy: 0, rz: 0, fx: 0, fy: 0, mz: 0 } }

      # Distribute Displacements
      nodes.each_with_index do |n, i|
        nodes_results[i][:dx] = u_global[i*3]
        nodes_results[i][:dy] = u_global[i*3+1]
        nodes_results[i][:rz] = u_global[i*3+2]
      end

      elements.each do |el|
        id = el['id']
        res = elem_results[id]
        
        # Global displacements for this element
        u_g = res[:dof_map].map { |dof| u_global[dof] }
        
        # Local displacements u_l = T * u_g
        u_l = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(res[:t], u_g)
        
        # Local forces f_l = k_local * u_l + local_f_fixed
        f_l_k = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(res[:k_local], u_l)
        f_l = Array.new(6, 0.0)
        6.times { |i| f_l[i] = f_l_k[i] + res[:local_f_fixed][i] }
        
        # Forces are at nodes 1 and 2:
        # N1: f_l[0]=Axial, f_l[1]=Shear, f_l[2]=Moment
        # N2: f_l[3]=Axial, f_l[4]=Shear, f_l[5]=Moment
        
        member_forces << {
          id: id,
          n1: el['n1'],
          n2: el['n2'],
          n1_forces: { axial: f_l[0], shear: f_l[1], moment: f_l[2] },
          n2_forces: { axial: f_l[3], shear: f_l[4], moment: f_l[5] }
        }

        # Accumulate Reactions at fixed nodes
        # Global element forces f_g = T^T * f_l
        f_g = GOStructAnalysis::Suite::MatrixOperations.multiply_vector(res[:tt], f_l)
        
        n1_idx = node_map[el['n1']]
        n2_idx = node_map[el['n2']]
        
        if fixed_dofs.include?(n1_idx*3) || fixed_dofs.include?(n1_idx*3+1) || fixed_dofs.include?(n1_idx*3+2)
          nodes_results[n1_idx][:fx] += f_g[0]
          nodes_results[n1_idx][:fy] += f_g[1]
          nodes_results[n1_idx][:mz] += f_g[2]
        end
        if fixed_dofs.include?(n2_idx*3) || fixed_dofs.include?(n2_idx*3+1) || fixed_dofs.include?(n2_idx*3+2)
          nodes_results[n2_idx][:fx] += f_g[3]
          nodes_results[n2_idx][:fy] += f_g[4]
          nodes_results[n2_idx][:mz] += f_g[5]
        end
      end
      
      # For nodal loads applied directly to supports, we must subtract them from the reaction
      # Because the reaction is balancing both member forces and applied loads
      nloads.each do |nl|
        idx = node_map[nl['node']]
        if fixed_dofs.include?(idx*3)
          nodes_results[idx][:fx] -= nl['fx'].to_f
        end
        if fixed_dofs.include?(idx*3+1)
          nodes_results[idx][:fy] -= nl['fy'].to_f
        end
        if fixed_dofs.include?(idx*3+2)
          nodes_results[idx][:mz] -= nl['mz'].to_f
        end
      end

      {
        ok: true,
        nodes: nodes_results,
        elements: member_forces
      }
    end

    def generate_report(data)
      model_data = data['model']
      result_data = data['result']

      template_path = File.join(GOStructAnalysis::TEMPLATE_ROOT, 'goframe_report.html')
      html = File.read(template_path, encoding: 'UTF-8')

      # Replace placeholders
      html.gsub!('{{MODEL_JSON}}', json_script_value(model_data))
      html.gsub!('{{RESULT_JSON}}', json_script_value(result_data))
      html.gsub!('{{REPORT_DATE}}', Time.now.strftime('%d/%m/%Y %H:%M'))

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

    def json_script_value(val)
      val.nil? ? 'null' : JSON.generate(val).gsub("</", "<\\/")
    end

    def round_value(val)
      val.to_f.round(3)
    end
  end
end

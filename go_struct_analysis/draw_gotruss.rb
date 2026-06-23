module GOStructAnalysis
  module DrawGotruss
    def gotruss_draw3d_callback(payload)
      data = parse_dialog_payload(payload)
      model_data = data['model']
      result = data['result']

      gotruss_draw3d(model_data, result)
      ensure_gotruss_dialog.execute_script("window.gotrussSetStatus('Drawn 3D Truss at origin.', true)")
    rescue StandardError => e
      ensure_gotruss_dialog.execute_script("window.gotrussSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def gotruss_draw3d(model_data, result)
      skp_model = Sketchup.active_model
      skp_model.start_operation('Draw GOTruss 3D', true)

      geo = model_data['geometry']
      res = result

      layers = skp_model.layers
      lyr_truss = layers['GOTruss_Members'] || layers.add('GOTruss_Members')
      lyr_forces = layers['GOTruss_Forces'] || layers.add('GOTruss_Forces')
      lyr_labels = layers['GOTruss_Labels'] || layers.add('GOTruss_Labels')
      lyr_loads = layers['GOTruss_Loads'] || layers.add('GOTruss_Loads')
      lyr_deform = layers['GOTruss_Deformation'] || layers.add('GOTruss_Deformation')

      mats = skp_model.materials

      mat_truss = mats['GOTruss_Base'] || mats.add('GOTruss_Base')
      mat_truss.color = Sketchup::Color.new(150, 150, 150)

      mat_tension = mats['GOTruss_Tension'] || mats.add('GOTruss_Tension')
      mat_tension.color = Sketchup::Color.new(0, 0, 255)
      mat_tension.alpha = 0.5

      mat_compression = mats['GOTruss_Compression'] || mats.add('GOTruss_Compression')
      mat_compression.color = Sketchup::Color.new(255, 0, 0)
      mat_compression.alpha = 0.5

      mat_load = mats['GOTruss_Load'] || mats.add('GOTruss_Load')
      mat_load.color = Sketchup::Color.new(255, 0, 0)

      main_group = skp_model.active_entities.add_group
      main_group.name = "GOTruss Result - #{model_data['trussName']}"
      main_group.set_attribute('GOStructAnalysis', 'module', 'Truss')
      main_group.set_attribute('GOStructAnalysis', 'model_data', model_data.to_json)
      attach_gotruss_analysis_attributes(main_group, model_data, res)
      ents = main_group.entities

      # 1. Draw Base Truss (Lines) and Node/Member Labels
      truss_grp = ents.add_group
      truss_grp.name = "Members & Nodes"
      truss_grp.layer = lyr_truss

      geo['elements'].each_with_index do |el, idx|
        n1 = geo['nodes'][el['n1']]
        n2 = geo['nodes'][el['n2']]

        pt1 = Geom::Point3d.new(n1['x'].to_f.m, 0, n1['y'].to_f.m)
        pt2 = Geom::Point3d.new(n2['x'].to_f.m, 0, n2['y'].to_f.m)

        line = truss_grp.entities.add_line(pt1, pt2)
        line.layer = lyr_truss
        attach_gotruss_member_attributes(line, model_data, geo, res, el, idx)

        # Member label
        mid_pt = Geom::Point3d.new((pt1.x + pt2.x) / 2.0, -0.1.m, (pt1.z + pt2.z) / 2.0)
        lbl = truss_grp.entities.add_text("M#{idx + 1}", mid_pt)
        lbl.layer = lyr_labels
      end

      geo['nodes'].each do |n|
        pt = Geom::Point3d.new(n['x'].to_f.m, 0.1.m, n['y'].to_f.m)
        lbl = truss_grp.entities.add_text("N#{n['id']}", pt)
        lbl.layer = lyr_labels
      end

      # 2. Draw Force Blocks
      forces_grp = ents.add_group
      forces_grp.name = "Member Forces"
      forces_grp.layer = lyr_forces

      max_f = [
        res['max_t_chord'].abs, res['max_c_chord'].abs,
        res['max_t_web'].abs, res['max_c_web'].abs
      ].max
      max_f = 1.0 if max_f == 0

      # Max block width in meters (e.g., 0.05m for max force)
      max_width = 0.05.m

      geo['elements'].each_with_index do |el, idx|
        f = res['member_forces'][idx].to_f
        next if f.abs < 0.1

        n1 = geo['nodes'][el['n1']]
        n2 = geo['nodes'][el['n2']]

        pt1 = Geom::Point3d.new(n1['x'].to_f.m, 0, n1['y'].to_f.m)
        pt2 = Geom::Point3d.new(n2['x'].to_f.m, 0, n2['y'].to_f.m)

        vec = pt1.vector_to(pt2)
        next unless vec.valid?

        up = Geom::Vector3d.new(0, 1, 0)
        perp = vec.cross(up) # normal vector in XZ plane
        perp.length = (f.abs / max_f) * max_width
        perp.length = 0.02.m if perp.length < 0.02.m # min visible thickness

        p1a = pt1.offset(perp)
        p1b = pt1.offset(perp.reverse)
        p2a = pt2.offset(perp)
        p2b = pt2.offset(perp.reverse)

        mat = f > 0 ? mat_tension : mat_compression

        begin
          face = forces_grp.entities.add_face(p1a, p2a, p2b, p1b)
          face.material = mat
          face.back_material = mat
          face.layer = lyr_forces
          face.edges.each { |e| e.layer = lyr_forces; e.material = "black" }
        rescue StandardError => e
          puts "GOTruss face error: #{e.message}"
        end

        # Add labels for maximums only (to avoid clutter)
        if (f.abs - res['max_t_chord'].abs).abs < 0.1 || (f.abs - res['max_c_chord'].abs).abs < 0.1 ||
           (f.abs - res['max_t_web'].abs).abs < 0.1 || (f.abs - res['max_c_web'].abs).abs < 0.1

           mid_pt = Geom::Point3d.new(
             (pt1.x + pt2.x) / 2.0,
             0.2.m, # Offset slightly in Y (green axis)
             (pt1.z + pt2.z) / 2.0
           )

           lbl = forces_grp.entities.add_text(sprintf("%.0f kg", f), mid_pt)
           lbl.layer = lyr_forces
        end
      end

      # 3. Draw Applied Loads (Uniform / Point Loads)
      lyr_applied_loads = layers['GOTruss_AppliedLoads'] || layers.add('GOTruss_AppliedLoads')
      mat_dl = mats['GOTruss_DL'] || mats.add('GOTruss_DL')
      mat_dl.color = Sketchup::Color.new(255, 0, 0)
      mat_dl.alpha = 0.3

      mat_ll = mats['GOTruss_LL'] || mats.add('GOTruss_LL')
      mat_ll.color = Sketchup::Color.new(0, 0, 255)
      mat_ll.alpha = 0.3

      applied_loads_grp = ents.add_group
      applied_loads_grp.name = "Applied Loads"
      applied_loads_grp.layer = lyr_applied_loads

      params = model_data['parameters']
      u_loads = params['uniform_loads'] || []
      p_loads = params['point_loads'] || []

      n_panels = params['N'].to_i
      l_panel = params['L'].to_f
      h_e = params['He'].to_f
      h_m = params['Hm'].to_f

      u_offset_top = 0
      u_offset_bot = 0

      u_loads.each do |ul|
        w = ul['w'].to_f
        next if w == 0
        x1 = ul['x1'].to_f
        x2 = ul['x2'].to_f
        chord = ul['chord'] || 'Top'
        type = ul['type'] || 'DL'
        is_dl = type == 'DL'
        is_top = chord.downcase == 'top'
        mat = is_dl ? mat_dl : mat_ll

        offset_idx = is_top ? u_offset_top : u_offset_bot
        if is_top
          u_offset_top += 1
        else
          u_offset_bot += 1
        end

        offset_y = is_top ? (0.2 + offset_idx * 0.4).m : (-0.2 - offset_idx * 0.4).m

        pts = []
        x = x1
        while x <= x2
          y = gotruss_get_y_on_chord(geo, x, is_top)
          pts << [x, y]
          x += l_panel
        end
        if pts.empty? || (pts.last[0] - x2).abs > 0.001
          y = gotruss_get_y_on_chord(geo, x2, is_top)
          pts << [x2, y]
        end

        poly_pts = []
        pts.each do |p|
          poly_pts << Geom::Point3d.new(p[0].m, 0, p[1].m + offset_y)
        end
        pts.reverse.each do |p|
          poly_pts << Geom::Point3d.new(p[0].m, 0, p[1].m + offset_y + (is_top ? 0.1.m : -0.1.m))
        end

        begin
          face = applied_loads_grp.entities.add_face(poly_pts)
          face.material = mat
          face.back_material = mat
          face.layer = lyr_applied_loads

          mid_pt = pts[pts.length / 2]
          lbl_pt = Geom::Point3d.new(mid_pt[0].m, 0, mid_pt[1].m + offset_y + (is_top ? 0.2.m : -0.2.m))
          lbl = applied_loads_grp.entities.add_text("#{w} kg/m [#{type}]", lbl_pt)
          lbl.layer = lyr_applied_loads
        rescue => e
          puts "GOTruss UL error: #{e.message}"
        end
      end

      p_offset_map = Hash.new(0)
      p_loads.each do |pl|
        p_val = pl['p'].to_f
        next if p_val == 0
        x = pl['x'].to_f
        chord = pl['chord'] || 'Top'
        type = pl['type'] || 'DL'
        is_dl = type == 'DL'
        is_top = chord.downcase == 'top'

        key = "#{x}_#{is_top}"
        offset_idx = p_offset_map[key]
        p_offset_map[key] += 1

        x_offset = (offset_idx % 2 == 1 ? 1 : -1) * (offset_idx / 2.0).ceil * 0.2.m

        y = gotruss_get_y_on_chord(geo, x, is_top)

        offset_y = is_top ? 0.2.m : -0.2.m

        pt1 = Geom::Point3d.new(x.m + x_offset, 0, y.m + offset_y + (is_top ? 0.4.m : -0.4.m))
        pt2 = Geom::Point3d.new(x.m + x_offset, 0, y.m + offset_y)

        line = applied_loads_grp.entities.add_line(pt1, pt2)
        line.layer = lyr_applied_loads

        # arrowhead
        vec = pt1.vector_to(pt2)
        if vec.valid?
          size = 0.1.m
          perp = Geom::Vector3d.new(1, 0, 0)
          perp.length = size / 2.0
          base_pt = pt2.offset(vec.reverse, size)
          left_pt = base_pt.offset(perp)
          right_pt = base_pt.offset(perp.reverse)
          begin
            face = applied_loads_grp.entities.add_face(pt2, left_pt, right_pt)
            face.material = is_dl ? "red" : "blue"
            face.layer = lyr_applied_loads
          rescue
          end
        end

        lbl = applied_loads_grp.entities.add_text("#{p_val} kg [#{type}]", pt1)
        lbl.layer = lyr_applied_loads
      end

      # 4. Draw Equivalent Nodal Loads
      loads_grp = ents.add_group
      loads_grp.name = "Equivalent Nodal Loads"
      loads_grp.layer = lyr_loads

      geo['loads'].each do |load|
        n = geo['nodes'][load['node']]
        next unless load['fy'] && load['fy'] < 0

        val = load['fy'].abs
        px = n['x'].to_f.m
        py = n['y'].to_f.m

        pt1 = Geom::Point3d.new(px, 0, py + 0.5.m)
        pt2 = Geom::Point3d.new(px, 0, py)

        vec = pt1.vector_to(pt2)
        next unless vec.valid?

        line = loads_grp.entities.add_line(pt1, pt2)
        line.layer = lyr_loads

        size = 0.1.m
        perp = Geom::Vector3d.new(1, 0, 0)
        perp.length = size / 2.0
        base_pt = pt2.offset(vec.reverse, size)
        left_pt = base_pt.offset(perp)
        right_pt = base_pt.offset(perp.reverse)

        begin
          face = loads_grp.entities.add_face(pt2, left_pt, right_pt)
          face.material = mat_load
          face.back_material = mat_load
          face.layer = lyr_loads
        rescue
        end

        lbl = loads_grp.entities.add_text(sprintf("%.0f kg", val), pt1)
        lbl.layer = lyr_loads
      end

      # 5. Draw Deformation
      deform_grp = ents.add_group
      deform_grp.name = "Deformation"
      deform_grp.layer = lyr_deform

      max_def_actual = [res['max_dx'], res['max_dy']].max
      def_scale = max_def_actual > 0 ? (0.2.m / max_def_actual) : 1.0

      geo['elements'].each do |el|
        n1 = geo['nodes'][el['n1']]
        n2 = geo['nodes'][el['n2']]

        d1x = res['displacements'][el['n1']]['dx'] * def_scale
        d1y = res['displacements'][el['n1']]['dy'] * def_scale
        d2x = res['displacements'][el['n2']]['dx'] * def_scale
        d2y = res['displacements'][el['n2']]['dy'] * def_scale

        pt1 = Geom::Point3d.new(n1['x'].to_f.m + d1x, 0, n1['y'].to_f.m + d1y)
        pt2 = Geom::Point3d.new(n2['x'].to_f.m + d2x, 0, n2['y'].to_f.m + d2y)

        line = deform_grp.entities.add_line(pt1, pt2)
        line.layer = lyr_deform
        line.material = "red"
      end

      if res['max_dy_n'] && res['max_dy_n'] >= 0
        node = geo['nodes'][res['max_dy_n']]
        dx = res['displacements'][res['max_dy_n']]['dx'] * def_scale
        dy = res['displacements'][res['max_dy_n']]['dy'] * def_scale
        pt = Geom::Point3d.new(node['x'].to_f.m + dx, 0, node['y'].to_f.m + dy)
        lbl = deform_grp.entities.add_text(sprintf("Max dy = %.2f mm", res['max_dy'] * 1000), pt)
        lbl.layer = lyr_deform
      end

      if res['max_dx_n'] && res['max_dx_n'] >= 0
        node = geo['nodes'][res['max_dx_n']]
        dx = res['displacements'][res['max_dx_n']]['dx'] * def_scale
        dy = res['displacements'][res['max_dx_n']]['dy'] * def_scale
        pt = Geom::Point3d.new(node['x'].to_f.m + dx, 0, node['y'].to_f.m + dy)
        lbl = deform_grp.entities.add_text(sprintf("Max dx = %.2f mm", res['max_dx'] * 1000), pt)
        lbl.layer = lyr_deform
      end

      skp_model.commit_operation
    end

    def attach_gotruss_member_attributes(entity, model_data, geo, result, element, index)
      dict = 'GOStructElement'
      n1 = geo['nodes'][element['n1']]
      n2 = geo['nodes'][element['n2']]
      length_m = if n1 && n2
                   Math.sqrt((n2['x'].to_f - n1['x'].to_f)**2 + (n2['y'].to_f - n1['y'].to_f)**2)
                 else
                   0.0
                 end
      force_kg = (result['member_forces'] || [])[index].to_f
      state = force_kg > 0.01 ? 'Tension' : (force_kg < -0.01 ? 'Compression' : 'Zero')
      d1 = (result['displacements'] || [])[element['n1']] || {}
      d2 = (result['displacements'] || [])[element['n2']] || {}
      max_node_displacement_mm = [d1, d2].map do |disp|
        dx = disp['dx'].to_f
        dy = disp['dy'].to_f
        Math.sqrt((dx * dx) + (dy * dy)) * 1000.0
      end.max || 0.0

      entity.set_attribute(dict, 'parent_module', 'Truss')
      entity.set_attribute(dict, 'element_kind', 'member')
      entity.set_attribute(dict, 'element_id', index + 1)
      entity.set_attribute(dict, 'element_index', index)
      entity.set_attribute(dict, 'element_type', element['type'].to_s)
      entity.set_attribute(dict, 'node_i', element['n1'])
      entity.set_attribute(dict, 'node_j', element['n2'])
      entity.set_attribute(dict, 'length_m', length_m)
      entity.set_attribute(dict, 'axial_kg', force_kg)
      entity.set_attribute(dict, 'force_state', state)
      entity.set_attribute(dict, 'n1_dx_mm', d1['dx'].to_f * 1000.0)
      entity.set_attribute(dict, 'n1_dy_mm', d1['dy'].to_f * 1000.0)
      entity.set_attribute(dict, 'n2_dx_mm', d2['dx'].to_f * 1000.0)
      entity.set_attribute(dict, 'n2_dy_mm', d2['dy'].to_f * 1000.0)
      entity.set_attribute(dict, 'max_node_displacement_mm', max_node_displacement_mm)
      entity.set_attribute(dict, 'parent_model_hash', GOStructAnalysis.bim_model_hash(model_data))
      entity.set_attribute(dict, 'result_json', JSON.generate({
        'axialKg' => force_kg,
        'forceState' => state,
        'nodeI' => element['n1'],
        'nodeJ' => element['n2'],
        'n1Displacement' => d1,
        'n2Displacement' => d2
      }))
    end

    def attach_gotruss_analysis_attributes(group, model_data, result)
      dict = 'GOStructAnalysis'
      member_forces = result['member_forces'] || []
      displacements = result['displacements'] || []
      max_abs_member_force = member_forces.map { |force| force.to_f.abs }.max || 0.0
      max_abs_displacement_m = displacements.map do |disp|
        dx = disp['dx'].to_f
        dy = disp['dy'].to_f
        Math.sqrt((dx * dx) + (dy * dy))
      end.max || 0.0
      max_dx_m = result['max_dx'].to_f
      max_dy_m = result['max_dy'].to_f

      group.set_attribute(dict, 'analysis_result', result.to_json)
      group.set_attribute(dict, 'analysis_generated_at', Time.now.iso8601)
      group.set_attribute(dict, 'analysis_ok', true)
      group.set_attribute(dict, 'schema_version', GOStructAnalysis::BIM_SCHEMA_VERSION)
      group.set_attribute(dict, 'plugin_version', GOStructAnalysis.plugin_version)
      group.set_attribute(dict, 'analysis_engine', 'GOTruss')
      group.set_attribute(dict, 'analysis_combo', 'Current')
      group.set_attribute(dict, 'model_hash', GOStructAnalysis.bim_model_hash(model_data))
      group.set_attribute(dict, 'analysis_model_hash', GOStructAnalysis.bim_model_hash(model_data))
      group.set_attribute(dict, 'store_full_analysis', true)
      group.set_attribute(dict, 'max_tension_chord_kg', result['max_t_chord'].to_f)
      group.set_attribute(dict, 'max_compression_chord_kg', result['max_c_chord'].to_f)
      group.set_attribute(dict, 'max_tension_web_kg', result['max_t_web'].to_f)
      group.set_attribute(dict, 'max_compression_web_kg', result['max_c_web'].to_f)
      group.set_attribute(dict, 'max_abs_member_force_kg', max_abs_member_force)
      group.set_attribute(dict, 'max_dx_mm', max_dx_m * 1000.0)
      group.set_attribute(dict, 'max_dy_mm', max_dy_m * 1000.0)
      group.set_attribute(dict, 'max_abs_displacement_mm', max_abs_displacement_m * 1000.0)
      group.set_attribute(dict, 'summary_json', JSON.generate({
        'trussName' => model_data['trussName'],
        'maxAbsMemberForceKg' => max_abs_member_force,
        'maxDxMm' => max_dx_m * 1000.0,
        'maxDyMm' => max_dy_m * 1000.0,
        'maxAbsDisplacementMm' => max_abs_displacement_m * 1000.0
      }))
    end

    def gotruss_get_y_on_chord(geo, target_x, is_top)
      target_type = is_top ? 'Top Chord' : 'Bottom Chord'
      chord_nodes = []
      geo['elements'].each do |el|
        if el['type'].to_s.downcase.include?(target_type.downcase)
          chord_nodes << geo['nodes'][el['n1']]
          chord_nodes << geo['nodes'][el['n2']]
        end
      end
      chord_nodes.uniq! { |n| n['id'] }
      chord_nodes.sort_by! { |n| n['x'].to_f }

      return 0.0 if chord_nodes.empty?

      target_x_f = target_x.to_f
      if target_x_f <= chord_nodes.first['x'].to_f
        return chord_nodes.first['y'].to_f
      end
      if target_x_f >= chord_nodes.last['x'].to_f
        return chord_nodes.last['y'].to_f
      end

      (0...chord_nodes.length - 1).each do |i|
        n1 = chord_nodes[i]
        n2 = chord_nodes[i + 1]
        x1 = n1['x'].to_f
        x2 = n2['x'].to_f
        if target_x_f >= x1 && target_x_f <= x2
          dx = x2 - x1
          return n1['y'].to_f if dx == 0
          ratio = (target_x_f - x1) / dx
          return n1['y'].to_f + ratio * (n2['y'].to_f - n1['y'].to_f)
        end
      end
      0.0
    end
  end
end

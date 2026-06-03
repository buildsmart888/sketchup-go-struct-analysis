module GOStructAnalysis
  module DrawGobeam
    def gobeam_draw3d_callback(payload)
      model = normalize_gobeam_model(parse_dialog_payload(payload))
      result = analyze_gobeam_model(model)
      gobeam_draw3d(model, result)
      ensure_gobeam_dialog.execute_script("window.gobeamSetStatus('Drawn 3D model at origin.', true)")
    rescue StandardError => e
      ensure_gobeam_dialog.execute_script("window.gobeamSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def gobeam_drawhud_callback(payload)
      model = normalize_gobeam_model(parse_dialog_payload(payload))
      result = analyze_gobeam_model(model)
      Sketchup.active_model.select_tool(GOBeamViewerTool.new(model, result))
      ensure_gobeam_dialog.execute_script("window.gobeamSetStatus('HUD Tool activated. Change tool to exit.', true)")
    rescue StandardError => e
      ensure_gobeam_dialog.execute_script("window.gobeamSetStatus(#{JSON.generate(format_error(e))}, false)")
    end

    def gobeam_draw3d(model_data, result)
      skp_model = Sketchup.active_model
      skp_model.start_operation('Draw GOBeam 3D', true)
      
      layers = skp_model.layers
      lyr_beam = layers['GOBeam_Beams'] || layers.add('GOBeam_Beams')
      lyr_shear = layers['GOBeam_Shear'] || layers.add('GOBeam_Shear')
      lyr_moment = layers['GOBeam_Moment'] || layers.add('GOBeam_Moment')
      lyr_defl = layers['GOBeam_Deflection'] || layers.add('GOBeam_Deflection')
      lyr_labels = layers['GOBeam_Labels'] || layers.add('GOBeam_Labels')
      
      mats = skp_model.materials
      mat_pos = mats['GOBeam_Positive'] || mats.add('GOBeam_Positive')
      mat_pos.color = Sketchup::Color.new(184, 232, 205) # #b8e8cd
      mat_pos.alpha = 0.5
      
      mat_neg = mats['GOBeam_Negative'] || mats.add('GOBeam_Negative')
      mat_neg.color = Sketchup::Color.new(244, 182, 182) # #f4b6b6
      mat_neg.alpha = 0.5

      main_group = skp_model.active_entities.add_group
      main_group.name = "GOBeam Result - #{model_data['beamName']}"
      ents = main_group.entities
      
      spans = result['spans']
      total_len_m = result['allSpanDiagrams']['totalLengthM'].to_f
      return if total_len_m <= 0
      
      max_h = total_len_m * 0.15 
      
      max_v = result['allSpanDiagrams']['shear'].map { |p| (p['v'] || 0).to_f.abs }.max || 0.001
      max_m = result['allSpanDiagrams']['moment'].map { |p| (p['m'] || 0).to_f.abs }.max || 0.001
      max_d = result['allSpanDiagrams']['deflection'].map { |p| (p['dMm'] || 0).to_f.abs }.max || 0.001
      
      max_v = 0.001 if max_v == 0
      max_m = 0.001 if max_m == 0
      max_d = 0.001 if max_d == 0
      
      v_scale = (max_h / max_v)
      m_scale = (max_h / max_m)
      d_scale = (max_h / max_d)
      
      offset = 0.0
      
      beam_group = ents.add_group
      beam_group.name = "Beams"
      beam_group.layer = lyr_beam
      
      spans.each_with_index do |span, idx|
        len = span['lengthM'].to_f.m
        b = (span['sectionBM'] || 0.2).to_f.m
        h = (span['sectionHM'] || 0.4).to_f.m
        
        span_grp = beam_group.entities.add_group
        span_grp.name = "Span #{idx + 1}"
        span_grp.layer = lyr_beam
        
        pt1 = Geom::Point3d.new(offset.m, -b/2.0, -h/2.0)
        pt2 = Geom::Point3d.new(offset.m, b/2.0, -h/2.0)
        pt3 = Geom::Point3d.new(offset.m, b/2.0, h/2.0)
        pt4 = Geom::Point3d.new(offset.m, -b/2.0, h/2.0)
        
        begin
          face = span_grp.entities.add_face(pt1, pt2, pt3, pt4)
          face.reverse! if face.normal.x < 0
          face.pushpull(len, true)
        rescue StandardError
        end
        
        offset += span['lengthM'].to_f
      end
      
      enhance_data = lambda do |data, value_key|
        out = []
        data.each_with_index do |point, idx|
          if idx == 0
            out << point
            next
          end
          prev = data[idx - 1]
          x1, x2 = prev['x'].to_f, point['x'].to_f
          y1, y2 = (prev[value_key] || 0).to_f, (point[value_key] || 0).to_f
          
          if x2 != x1 && y1 != 0 && y2 != 0 && ((y1 < 0 && y2 > 0) || (y1 > 0 && y2 < 0))
            ratio = y1.abs / (y1.abs + y2.abs)
            zero_pt = point.dup
            zero_pt['x'] = x1 + (x2 - x1) * ratio
            zero_pt[value_key] = 0.0
            out << zero_pt
          end
          out << point
        end
        out
      end
      
      draw_diagram = lambda do |name, layer, data_raw, scale, value_key, fmt_str, label_layer|
        grp = ents.add_group
        grp.name = name
        grp.layer = layer
        
        data = enhance_data.call(data_raw, value_key)
        
        data.each_cons(2) do |p1, p2|
          x1 = p1['x'].to_f.m
          y1 = (p1[value_key] || 0).to_f
          x2 = p2['x'].to_f.m
          y2 = (p2[value_key] || 0).to_f
          
          next if (x2 - x1).abs < 1e-4
          
          mid = (y1 + y2) / 2.0
          mid = y1 if mid == 0
          next if mid == 0
          
          mat = mid > 0 ? mat_pos : mat_neg
          
          pts = [
            Geom::Point3d.new(x1, 0, 0),
            Geom::Point3d.new(x1, 0, y1 * scale.m),
            Geom::Point3d.new(x2, 0, y2 * scale.m),
            Geom::Point3d.new(x2, 0, 0)
          ]
          begin
            face = grp.entities.add_face(pts)
            face.material = mat
            face.back_material = mat
          rescue StandardError
          end
        end
        
        spans.each_with_index do |s, idx|
          span_pts = data_raw.select { |p| p['spanIndex'].to_i == idx }
          if span_pts.length > 0
            max_pt = span_pts.max_by { |p| (p[value_key] || 0).to_f }
            min_pt = span_pts.min_by { |p| (p[value_key] || 0).to_f }
            
            eps = value_key == 'dMm' ? 0.0005 : 0.05
            
            if max_pt && (max_pt[value_key] || 0).to_f > eps
              pt3d = Geom::Point3d.new(max_pt['x'].to_f.m, 0, max_pt[value_key].to_f * scale.m)
              txt = grp.entities.add_text("MAX " + format(fmt_str, max_pt[value_key].to_f), pt3d)
              txt.layer = label_layer
            end
            
            if min_pt && (min_pt[value_key] || 0).to_f < -eps
              pt3d = Geom::Point3d.new(min_pt['x'].to_f.m, 0, min_pt[value_key].to_f * scale.m)
              txt = grp.entities.add_text("MIN " + format(fmt_str, min_pt[value_key].to_f), pt3d)
              txt.layer = label_layer
            end
          end
        end
      end
      
      lyr_shear_labels = layers['GOBeam_Labels_Shear'] || layers.add('GOBeam_Labels_Shear')
      lyr_moment_labels = layers['GOBeam_Labels_Moment'] || layers.add('GOBeam_Labels_Moment')
      lyr_defl_labels = layers['GOBeam_Labels_Deflection'] || layers.add('GOBeam_Labels_Deflection')
      
      draw_diagram.call("Shear Diagram", lyr_shear, result['allSpanDiagrams']['shear'], v_scale, 'v', "%.0f kg", lyr_shear_labels)
      draw_diagram.call("Moment Diagram", lyr_moment, result['allSpanDiagrams']['moment'], m_scale, 'm', "%.0f kg-m", lyr_moment_labels)
      draw_diagram.call("Deflection Diagram", lyr_defl, result['allSpanDiagrams']['deflection'], d_scale, 'dMm', "%.2f mm", lyr_defl_labels)
      
      max_section_h = spans.map { |s| (s['sectionHM'] || 0.4).to_f }.max.m
      
      mat_load = mats['GOBeam_Load'] || mats.add('GOBeam_Load')
      mat_load.color = Sketchup::Color.new(41, 128, 185)
      
      mat_reaction = mats['GOBeam_Reaction'] || mats.add('GOBeam_Reaction')
      mat_reaction.color = Sketchup::Color.new(8, 118, 79)
      
      lyr_loads = layers['GOBeam_Loads'] || layers.add('GOBeam_Loads')
      lyr_reactions = layers['GOBeam_Reactions'] || layers.add('GOBeam_Reactions')
      lyr_reaction_labels = layers['GOBeam_Labels_Reaction'] || layers.add('GOBeam_Labels_Reaction')
      
      main_load_group = ents.add_group
      main_load_group.name = "Loads"
      load_case_groups = {}
      
      draw_3d_arrow = lambda do |grp_ents, p1, p2, mat, layer|
        vec = p1.vector_to(p2)
        return if vec.length == 0
        edge = grp_ents.add_line(p1, p2)
        edge.layer = layer
        size = 0.15.m
        perp = vec.cross(Geom::Vector3d.new(0, 1, 0))
        perp = vec.cross(Geom::Vector3d.new(1, 0, 0)) if perp.length == 0
        perp.length = size / 2.0
        base_pt = p2.offset(vec.reverse, size)
        left_pt = base_pt.offset(perp)
        right_pt = base_pt.offset(perp.reverse)
        begin
          face = grp_ents.add_face(p2, left_pt, right_pt)
          face.material = mat
          face.back_material = mat
          face.layer = layer
          face.edges.each { |e| e.layer = layer }
        rescue StandardError
        end
      end
      
      reaction_group = ents.add_group
      reaction_group.name = "Reactions"
      reaction_group.layer = lyr_reactions
      
      (result['allSpanDiagrams']['supports'] || []).each do |sup|
        x = sup['x'].to_f.m
        val = sup['reactionKg'].to_f
        p1 = Geom::Point3d.new(x, 0, -max_section_h / 2.0 - 0.6.m)
        p2 = Geom::Point3d.new(x, 0, -max_section_h / 2.0)
        draw_3d_arrow.call(reaction_group.entities, p1, p2, mat_reaction, lyr_reactions)
        txt = reaction_group.entities.add_text("R = %.0f kg" % val, p1)
        txt.layer = lyr_reaction_labels
      end
      
      uniform_levels = []
      loads_data = result['allSpanDiagrams']['loads'] || []
      
      loads_data.each do |load|
        if load['type'] == 'uniform' && load['wKgM'].to_f > 0
          level = 0
          uniform_levels.each do |placed|
            if [load['x1'].to_f, placed[:x1]].max < [load['x2'].to_f, placed[:x2]].min - 1e-9
              level = placed[:level] + 1 if placed[:level] >= level
            end
          end
          load['level'] = level
          uniform_levels << { x1: load['x1'].to_f, x2: load['x2'].to_f, level: level }
        end
      end
      
      max_uniform_level = uniform_levels.map { |u| u[:level] }.max || 0
      point_load_shift = max_uniform_level * 0.4.m
      
      loads_data.each do |load|
        case_name = load['case'] || 'DL'
        
        unless load_case_groups[case_name]
          grp = main_load_group.entities.add_group
          grp.name = "Load Case: #{case_name}"
          lyr = layers["GOBeam_Load_#{case_name}"] || layers.add("GOBeam_Load_#{case_name}")
          lbl_lyr = layers["GOBeam_Labels_Load_#{case_name}"] || layers.add("GOBeam_Labels_Load_#{case_name}")
          grp.layer = lyr
          load_case_groups[case_name] = { group: grp, layer: lyr, label_layer: lbl_lyr }
        end
        
        target = load_case_groups[case_name]
        grp_ents = target[:group].entities
        lyr = target[:layer]
        lbl_lyr = target[:label_layer]
        
        if load['type'] == 'uniform' && load['wKgM'].to_f > 0
          x1 = load['x1'].to_f.m
          x2 = load['x2'].to_f.m
          val = load['wKgM'].to_f
          shift = (load['level'] || 0) * 0.4.m
          
          z_line = max_section_h / 2.0 + 0.4.m + shift
          z_arrow_start = z_line
          z_arrow_end = max_section_h / 2.0 + shift
          
          l_edge = grp_ents.add_line(Geom::Point3d.new(x1, 0, z_line), Geom::Point3d.new(x2, 0, z_line))
          l_edge.layer = lyr
          
          span_len = (x2 - x1).to_f
          num_arrows = [((span_len / 1.m).to_i), 2].max
          
          (0..num_arrows).each do |i|
            xx = x1 + (x2 - x1) * (i.to_f / num_arrows)
            p1 = Geom::Point3d.new(xx, 0, z_arrow_start)
            p2 = Geom::Point3d.new(xx, 0, z_arrow_end)
            draw_3d_arrow.call(grp_ents, p1, p2, mat_load, lyr)
          end
          
          txt_pt = Geom::Point3d.new(x1 + (x2 - x1)/2.0, 0, z_line + 0.1.m)
          txt = grp_ents.add_text("%.0f kg/m (%s)" % [val, case_name], txt_pt)
          txt.layer = lbl_lyr
        end
        
        if load['type'] == 'point'
          x = load['x'].to_f.m
          val = load['pKg'].to_f
          
          p1 = Geom::Point3d.new(x, 0, max_section_h / 2.0 + 0.8.m + point_load_shift)
          p2 = Geom::Point3d.new(x, 0, max_section_h / 2.0)
          
          draw_3d_arrow.call(grp_ents, p1, p2, mat_load, lyr)
          
          txt = grp_ents.add_text("%.0f kg (%s)" % [val, case_name], p1)
          txt.layer = lbl_lyr
        end
      end
      
      skp_model.commit_operation
    end

    class GOBeamViewerTool
      def initialize(model_data, result)
        @model = model_data
        @result = result
      end
      
      def activate
        Sketchup.active_model.active_view.invalidate
      end
      
      def deactivate(view)
        view.invalidate
      end
      
      def draw(view)
        len = @result['allSpanDiagrams']['totalLengthM'].to_f.m
        total_len_m = @result['allSpanDiagrams']['totalLengthM'].to_f
        return if total_len_m <= 0
        
        max_h = total_len_m * 0.15
        
        max_v = @result['allSpanDiagrams']['shear'].map { |p| (p['v'] || 0).to_f.abs }.max || 0.001
        max_m = @result['allSpanDiagrams']['moment'].map { |p| (p['m'] || 0).to_f.abs }.max || 0.001
        
        max_v = 0.001 if max_v == 0
        max_m = 0.001 if max_m == 0
        
        v_scale = (max_h / max_v)
        m_scale = (max_h / max_m)
        
        pos_color = Sketchup::Color.new(184, 232, 205)
        neg_color = Sketchup::Color.new(244, 182, 182)
        
        draw_hud_graph(view, @result['allSpanDiagrams']['moment'], 'm', m_scale, pos_color, neg_color)
        draw_hud_graph(view, @result['allSpanDiagrams']['shear'], 'v', v_scale, pos_color, neg_color)
        
        view.drawing_color = 'black'
        view.line_width = 3
        view.draw(GL_LINES, [Geom::Point3d.new(0,0,0), Geom::Point3d.new(len, 0, 0)])
      end
      
      def draw_hud_graph(view, data_raw, value_key, scale, pos_color, neg_color)
        out = []
        data_raw.each_with_index do |point, idx|
          if idx == 0
            out << point
            next
          end
          prev = data_raw[idx - 1]
          x1, x2 = prev['x'].to_f, point['x'].to_f
          y1, y2 = (prev[value_key] || 0).to_f, (point[value_key] || 0).to_f
          
          if x2 != x1 && y1 != 0 && y2 != 0 && ((y1 < 0 && y2 > 0) || (y1 > 0 && y2 < 0))
            ratio = y1.abs / (y1.abs + y2.abs)
            zero_pt = point.dup
            zero_pt['x'] = x1 + (x2 - x1) * ratio
            zero_pt[value_key] = 0.0
            out << zero_pt
          end
          out << point
        end
        data = out
        
        data.each_cons(2) do |p1, p2|
          x1, y1 = p1['x'].to_f.m, (p1[value_key] || 0).to_f * scale.m
          x2, y2 = p2['x'].to_f.m, (p2[value_key] || 0).to_f * scale.m
          
          next if (x2 - x1).abs < 1e-4
          mid = (y1 + y2) / 2.0
          mid = y1 if mid == 0
          next if mid == 0
          
          color = mid > 0 ? pos_color : neg_color
          view.drawing_color = Sketchup::Color.new(color.red, color.green, color.blue, 180)
          
          triangles = [
            Geom::Point3d.new(x1, 0, 0), Geom::Point3d.new(x1, 0, y1), Geom::Point3d.new(x2, 0, y2),
            Geom::Point3d.new(x1, 0, 0), Geom::Point3d.new(x2, 0, y2), Geom::Point3d.new(x2, 0, 0)
          ]
          view.draw(GL_TRIANGLES, triangles)
        end
        
        pts = data_raw.map { |pt| Geom::Point3d.new(pt['x'].to_f.m, 0, (pt[value_key] || 0).to_f * scale.m) }
        if pts.length > 0
          view.drawing_color = Sketchup::Color.new(23, 32, 37)
          view.line_width = 2
          view.draw(GL_LINE_STRIP, pts)
        end
      end
    end
  end
end

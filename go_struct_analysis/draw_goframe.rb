module GOStructAnalysis
  module DrawGoframe
    extend self

    def draw(data)
      model_data = data['model'] || {}
      result = data['result']
      options = data['options'] || { 'showNodes' => true, 'showMembers' => true, 'showReactions' => true }

      skp_model = Sketchup.active_model
      skp_model.start_operation('Draw GO Frame 3D', true)

      begin
        layers = skp_model.layers
        lyr_frame = layers['GOFrame_Members'] || layers.add('GOFrame_Members')
        lyr_labels = layers['GOFrame_Labels'] || layers.add('GOFrame_Labels')
        lyr_loads = layers['GOFrame_Loads'] || layers.add('GOFrame_Loads')
        lyr_deform = layers['GOFrame_Deformation'] || layers.add('GOFrame_Deformation')
        lyr_diag_afd = layers['GOFrame_Diag_AFD'] || layers.add('GOFrame_Diag_AFD')
        lyr_diag_sfd = layers['GOFrame_Diag_SFD'] || layers.add('GOFrame_Diag_SFD')
        lyr_diag_bmd = layers['GOFrame_Diag_BMD'] || layers.add('GOFrame_Diag_BMD')
        lyr_diag_labels = layers['GOFrame_Labels_Diag'] || layers.add('GOFrame_Labels_Diag')

        mats = skp_model.materials
        mat_frame = mats['GOFrame_Base'] || mats.add('GOFrame_Base')
        mat_frame.color = Sketchup::Color.new(100, 100, 100)

        main_group = skp_model.active_entities.add_group
        main_group.name = "GO Frame Analysis - #{Time.now.strftime('%Y-%m-%d %H:%M')}"
        ents = main_group.entities

        frame_grp = ents.add_group
        frame_grp.name = "Members"
        frame_grp.layer = lyr_frame

        nodes = model_data['nodes'] || []
        elements = model_data['elements'] || []
        
        min_x = nodes.map { |n| n['x'].to_f }.min || 0.0
        max_x = nodes.map { |n| n['x'].to_f }.max || 1.0
        min_y = nodes.map { |n| n['y'].to_f }.min || 0.0
        max_y = nodes.map { |n| n['y'].to_f }.max || 1.0
        frame_span = [max_x - min_x, max_y - min_y].max
        frame_span = 1.0 if frame_span < 1e-3

        sections = model_data['sections'] || []

        # 1. Draw Members
        elements.each do |el|
          n1 = nodes.find { |n| n['id'] == el['n1'] }
          n2 = nodes.find { |n| n['id'] == el['n2'] }
          next unless n1 && n2

          pt1 = Geom::Point3d.new(n1['x'].to_f.m, 0, n1['y'].to_f.m)
          pt2 = Geom::Point3d.new(n2['x'].to_f.m, 0, n2['y'].to_f.m)

          # Draw center line
          line = frame_grp.entities.add_line(pt1, pt2)
          line.layer = lyr_frame

          # Draw profile (simple box)
          vec = pt1.vector_to(pt2)
          if vec.valid?
            up = (vec.parallel?(Z_AXIS) || vec.parallel?(Z_AXIS.reverse)) ? X_AXIS : Z_AXIS
            right = vec.cross(up).normalize
            up2 = right.cross(vec).normalize

            w_val = 0.05
            h_val = 0.05
            shape_type = 'Rectangular'
            sec = sections.find { |s| s['id'] == el['sec'] }
            if sec
              if sec['shape'] && sec['shape'].is_a?(Hash)
                shape_type = sec['shape']['type'] || 'Rectangular'
              end
              
              if sec['a'].to_f > 0 && sec['i'].to_f > 0 && shape_type == 'Rectangular'
                a_m2 = sec['a'].to_f / 10000.0
                i_m4 = sec['i'].to_f / 100000000.0
                calc_h = Math.sqrt(12.0 * i_m4 / a_m2)
                calc_w = a_m2 / calc_h
                
                if calc_h > 0.001 && calc_h < 5.0 && calc_w > 0.001 && calc_w < 5.0
                  h_val = calc_h / 2.0
                  w_val = calc_w / 2.0
                end
              end
            end

            sub_grp = frame_grp.entities.add_group
            
            if shape_type == 'I-Section'
              hh = sec['shape']['h'].to_f.m
              bb = sec['shape']['b'].to_f.m
              tw = sec['shape']['tw'].to_f.m
              tf = sec['shape']['tf'].to_f.m
              
              p1 = pt1.offset(right, tw/2).offset(up2, hh/2 - tf)
              p2 = pt1.offset(right, bb/2).offset(up2, hh/2 - tf)
              p3 = pt1.offset(right, bb/2).offset(up2, hh/2)
              p4 = pt1.offset(right, -bb/2).offset(up2, hh/2)
              p5 = pt1.offset(right, -bb/2).offset(up2, hh/2 - tf)
              p6 = pt1.offset(right, -tw/2).offset(up2, hh/2 - tf)
              
              p7 = pt1.offset(right, -tw/2).offset(up2, -hh/2 + tf)
              p8 = pt1.offset(right, -bb/2).offset(up2, -hh/2 + tf)
              p9 = pt1.offset(right, -bb/2).offset(up2, -hh/2)
              p10 = pt1.offset(right, bb/2).offset(up2, -hh/2)
              p11 = pt1.offset(right, bb/2).offset(up2, -hh/2 + tf)
              p12 = pt1.offset(right, tw/2).offset(up2, -hh/2 + tf)

              face = sub_grp.entities.add_face(p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12)
              if face && face.valid?
                dist = face.normal % vec > 0 ? vec.length : -vec.length
                face.pushpull(dist)
              end
            elsif shape_type == 'Pipe'
              dd = sec['shape']['d'].to_f.m
              tt = sec['shape']['t'].to_f.m
              
              pts_outer = []
              pts_inner = []
              pts_outer_end = []
              pts_inner_end = []
              
              24.times do |i|
                angle = i * Math::PI * 2 / 24.0
                dx = Math.cos(angle)
                dy = Math.sin(angle)
                
                ro = dd / 2.0
                ri = dd / 2.0 - tt
                
                # Offset by scaled vectors
                # v_out = right * (dx * ro) + up2 * (dy * ro) # SketchUp 6+ supports Vector * Float
                vec_out_x = Geom::Vector3d.new(right.x * dx * ro, right.y * dx * ro, right.z * dx * ro)
                vec_out_y = Geom::Vector3d.new(up2.x * dy * ro, up2.y * dy * ro, up2.z * dy * ro)
                vec_in_x = Geom::Vector3d.new(right.x * dx * ri, right.y * dx * ri, right.z * dx * ri)
                vec_in_y = Geom::Vector3d.new(up2.x * dy * ri, up2.y * dy * ri, up2.z * dy * ri)
                
                vec_out = vec_out_x + vec_out_y
                vec_in = vec_in_x + vec_in_y
                
                pts_outer << pt1 + vec_out
                pts_inner << pt1 + vec_in
                pts_outer_end << pt2 + vec_out
                pts_inner_end << pt2 + vec_in
              end
              
              faces = []
              24.times do |i|
                j = (i + 1) % 24
                # Start cap
                sub_grp.entities.add_face(pts_outer[i], pts_outer[j], pts_inner[j], pts_inner[i]) rescue nil
                # End cap
                sub_grp.entities.add_face(pts_outer_end[i], pts_inner_end[i], pts_inner_end[j], pts_outer_end[j]) rescue nil
                # Outer tube
                f_out = sub_grp.entities.add_face(pts_outer[i], pts_outer[j], pts_outer_end[j], pts_outer_end[i]) rescue nil
                # Inner tube
                f_in = sub_grp.entities.add_face(pts_inner[i], pts_inner_end[i], pts_inner_end[j], pts_inner[j]) rescue nil
                
                faces << f_out if f_out
                faces << f_in if f_in
              end
              
              # Smooth the longitudinal edges
              faces.each do |f|
                f.edges.each do |e|
                  if e.line[1].parallel?(vec)
                    e.soft = true
                    e.smooth = true
                  end
                end
              end
            else
              w = w_val.m
              h = h_val.m
              p1_b = pt1.offset(right, w).offset(up2, h)
              p2_b = pt1.offset(right, -w).offset(up2, h)
              p3_b = pt1.offset(right, -w).offset(up2, -h)
              p4_b = pt1.offset(right, w).offset(up2, -h)
  
              face = sub_grp.entities.add_face(p1_b, p2_b, p3_b, p4_b)
              if face && face.valid?
                dist = face.normal % vec > 0 ? vec.length : -vec.length
                face.pushpull(dist)
              end
            end
            
            sub_grp.material = mat_frame
          end
          
          # Member label
          if options['showMembers']
            mid_pt = Geom::Point3d.new((pt1.x + pt2.x) / 2.0, -0.2.m, (pt1.z + pt2.z) / 2.0)
            lbl = frame_grp.entities.add_text("M#{el['id']}", mid_pt)
            lbl.layer = lyr_labels
          end
        end

        # 2. Draw Nodes & Supports
        nodes.each do |n|
          pt = Geom::Point3d.new(n['x'].to_f.m, 0.2.m, n['y'].to_f.m)
          
          if options['showNodes']
            lbl = frame_grp.entities.add_text("N#{n['id']}", pt)
            lbl.layer = lyr_labels
          end

          # Draw support
          sup = n['support']
          if sup != 'Free'
            sup_grp = ents.add_group
            sup_grp.layer = lyr_frame
            sp = Geom::Point3d.new(n['x'].to_f.m, 0, n['y'].to_f.m)
            if sup == 'Fixed'
              sup_grp.entities.add_face(
                sp.offset(X_AXIS, -0.2.m).offset(Z_AXIS, -0.1.m),
                sp.offset(X_AXIS, 0.2.m).offset(Z_AXIS, -0.1.m),
                sp.offset(X_AXIS, 0.2.m).offset(Z_AXIS, -0.2.m),
                sp.offset(X_AXIS, -0.2.m).offset(Z_AXIS, -0.2.m)
              )
            elsif sup == 'Pinned' || sup.start_with?('Roller')
              sup_grp.entities.add_face(
                sp,
                sp.offset(X_AXIS, -0.15.m).offset(Z_AXIS, -0.2.m),
                sp.offset(X_AXIS, 0.15.m).offset(Z_AXIS, -0.2.m)
              )
            end
          end
        end

        # 3. Draw Reactions if available
        if options['showReactions'] && result && result['ok']
          res_nodes = result['nodes']
          
          res_nodes.each do |rn|
            fx = rn['fx'].to_f
            fy = rn['fy'].to_f
            mz = rn['mz'].to_f
            next if fx.abs < 0.1 && fy.abs < 0.1 && mz.abs < 0.1

            pt = Geom::Point3d.new(rn['x'].to_f.m, 0, rn['y'].to_f.m)
            texts = []
            texts << "Rx: #{fx.round(1)} kg" if fx.abs > 0.1
            texts << "Ry: #{fy.round(1)} kg" if fy.abs > 0.1
            texts << "Mz: #{mz.round(1)} kg.m" if mz.abs > 0.1
            
            unless texts.empty?
              arrow_pt = pt.offset(Z_AXIS.reverse, 0.5.m).offset(X_AXIS.reverse, 0.5.m)
              t = ents.add_text(texts.join("\n"), arrow_pt)
              t.layer = lyr_labels
            end
          end
        end

        # 4. Draw Applied Loads
        if options['show3DLoads']
          nloads = model_data['nloads'] || []
          eloads = model_data['eloads'] || []
          
          lc_colors_map = { 
            'DL' => Sketchup::Color.new(230, 126, 34),
            'LL' => Sketchup::Color.new(52, 152, 219),
            'WL' => Sketchup::Color.new(155, 89, 182),
            'EX' => Sketchup::Color.new(26, 188, 156),
            'EY' => Sketchup::Color.new(241, 196, 15),
            'W(X-)' => Sketchup::Color.new(155, 89, 182),
            'W(X+)' => Sketchup::Color.new(155, 89, 182)
          }
          default_colors = [
            Sketchup::Color.new(230, 126, 34),
            Sketchup::Color.new(52, 152, 219),
            Sketchup::Color.new(155, 89, 182),
            Sketchup::Color.new(26, 188, 156),
            Sketchup::Color.new(241, 196, 15),
            Sketchup::Color.new(231, 76, 60),
            Sketchup::Color.new(52, 73, 94)
          ]
          get_color = -> (lc) {
            return lc_colors_map[lc] if lc_colors_map[lc]
            hash = 0
            lc.each_byte { |b| hash = b + ((hash << 5) - hash) }
            default_colors[hash.abs % default_colors.length]
          }

          loads_main_grp = ents.add_group
          loads_main_grp.name = "Applied Loads"
          loads_main_grp.layer = lyr_loads
          
          lc_groups = {}
          get_lc_group = -> (lc) {
            unless lc_groups[lc]
              grp = loads_main_grp.entities.add_group
              grp.name = "Load Case: #{lc}"
              lc_layer_name = "GOFrame_Loads_#{lc}"
              lc_layer = layers[lc_layer_name] || layers.add(lc_layer_name)
              grp.layer = lc_layer
              
              lc_mat_name = "GOFrame_Mat_#{lc}"
              lc_mat = mats[lc_mat_name] || mats.add(lc_mat_name)
              lc_mat.color = get_color.call(lc)
              grp.material = lc_mat
              
              lc_groups[lc] = grp
            end
            lc_groups[lc]
          }
          
          nload_counts = {}
          nloads.each do |nl|
            nd = nodes.find { |n| n['id'] == nl['node'] }
            next unless nd
            
            nd_id = nl['node']
            nload_counts[nd_id] ||= 0
            depth_offset = nload_counts[nd_id] * 0.4.m
            nload_counts[nd_id] += 1
            
            pt = Geom::Point3d.new(nd['x'].to_f.m, depth_offset, nd['y'].to_f.m)
            fx = nl['fx'].to_f
            fy = nl['fy'].to_f
            mz = nl['mz'].to_f
            lcase = nl['lcase'] || 'DL'
            
            grp = get_lc_group.call(lcase)
            
            if fx.abs > 1e-3
              dir = fx > 0 ? X_AXIS : X_AXIS.reverse
              p1 = pt.offset(dir.reverse, 1.0.m)
              grp.entities.add_line(p1, pt)
              grp.entities.add_line(pt, pt.offset(dir.reverse, 0.2.m).offset(Z_AXIS, 0.1.m))
              grp.entities.add_line(pt, pt.offset(dir.reverse, 0.2.m).offset(Z_AXIS, -0.1.m))
              t = grp.entities.add_text("#{lcase}=#{fx.round(1)} kg", p1)
              t.layer = lyr_labels
            end
            if fy.abs > 1e-3
              dir = fy > 0 ? Z_AXIS : Z_AXIS.reverse
              p1 = pt.offset(dir.reverse, 1.0.m)
              grp.entities.add_line(p1, pt)
              grp.entities.add_line(pt, pt.offset(dir.reverse, 0.2.m).offset(X_AXIS, 0.1.m))
              grp.entities.add_line(pt, pt.offset(dir.reverse, 0.2.m).offset(X_AXIS, -0.1.m))
              t = grp.entities.add_text("#{lcase}=#{fy.round(1)} kg", p1)
              t.layer = lyr_labels
            end
          end
          
          eload_counts = {}
          eloads.each do |el_ld|
            el = elements.find { |e| e['id'] == el_ld['elem'] }
            next unless el
            n1 = nodes.find { |n| n['id'] == el['n1'] }
            n2 = nodes.find { |n| n['id'] == el['n2'] }
            next unless n1 && n2
            
            elem_id = el_ld['elem']
            eload_counts[elem_id] ||= 0
            depth_offset = eload_counts[elem_id] * 0.4.m
            eload_counts[elem_id] += 1
            
            pt1 = Geom::Point3d.new(n1['x'].to_f.m, depth_offset, n1['y'].to_f.m)
            pt2 = Geom::Point3d.new(n2['x'].to_f.m, depth_offset, n2['y'].to_f.m)
            vec = pt1.vector_to(pt2)
            next unless vec.valid?
            
            w1 = el_ld['w1'] ? el_ld['w1'].to_f : (el_ld['w'] ? el_ld['w'].to_f : 0.0)
            w2 = el_ld['w2'] ? el_ld['w2'].to_f : w1
            
            lcase = el_ld['lcase'] || 'DL'
            grp = get_lc_group.call(lcase)
            
            dir_str = el_ld['dir']
            norm_vec = Geom::Vector3d.new(-vec.z, 0, vec.x).normalize
            
            max_w = [w1.abs, w2.abs].max
            next if max_w < 1e-4
            
            len = pt1.distance(pt2).to_m
            num_arrows = [3, len.to_i].max
            pts = []
            
            (0..num_arrows).each do |i|
              t = i.to_f / num_arrows
              p_base = pt1.offset(vec, vec.length * t)
              current_w = w1 + (w2 - w1) * t
              sign = current_w < 0 ? -1 : 1
              arrow_len = (current_w.abs / max_w) * 0.8
              arrow_len = 0.2 if arrow_len < 0.2 && current_w != 0.0
              
              load_vec = dir_str == 'Global Y' ? Z_AXIS.reverse : norm_vec.reverse
              load_vec = load_vec.reverse if sign > 0
              
              p_top = p_base.offset(load_vec.reverse, arrow_len.m)
              pts << p_top
              grp.entities.add_line(p_top, p_base)
              
              if arrow_len > 0.3
                grp.entities.add_line(p_base, p_base.offset(load_vec.reverse, 0.15.m).offset(vec, 0.1.m))
                grp.entities.add_line(p_base, p_base.offset(load_vec.reverse, 0.15.m).offset(vec.reverse, 0.1.m))
              end
            end
            
            if pts.length > 1
              (0...pts.length-1).each do |i|
                grp.entities.add_line(pts[i], pts[i+1])
              end
            end
            
            # Text
            if (w1 - w2).abs < 1e-3
              sign_w = w1 < 0 ? -1 : 1
              t_pt = pt1.offset(vec, vec.length * 0.5).offset(dir_str == 'Global Y' ? Z_AXIS : norm_vec, sign_w > 0 ? 1.0.m : -1.0.m)
              t = grp.entities.add_text("#{lcase}=#{w1.round(1)} kg/m", t_pt)
              t.layer = lyr_labels
            else
              s1 = w1 < 0 ? -1 : 1
              a1 = (w1.abs / max_w) * 0.8
              t1_pt = pt1.offset(dir_str == 'Global Y' ? Z_AXIS : norm_vec, s1 > 0 ? a1.m + 0.2.m : -a1.m - 0.2.m)
              if w1.abs > 1e-3
                t1 = grp.entities.add_text("#{lcase}=#{w1.round(1)}", t1_pt)
                t1.layer = lyr_labels
              end
              
              s2 = w2 < 0 ? -1 : 1
              a2 = (w2.abs / max_w) * 0.8
              t2_pt = pt2.offset(dir_str == 'Global Y' ? Z_AXIS : norm_vec, s2 > 0 ? a2.m + 0.2.m : -a2.m - 0.2.m)
              if w2.abs > 1e-3
                t2 = grp.entities.add_text("#{lcase}=#{w2.round(1)}", t2_pt)
                t2.layer = lyr_labels
              end
            end
          end
        end

        # 5. Draw Deformed Shape
        if options['show3DDeformed'] && result && result['ok']
          res_nodes = result['nodes']
          max_d = res_nodes.map { |rn| Math.sqrt((rn['dx'].to_f)**2 + (rn['dy'].to_f)**2) }.max || 0.0
          if max_d > 1e-6
            def_scale = (frame_span * 0.1) / max_d
            
            def_grp = ents.add_group
            def_grp.name = "Deformed Shape"
            def_mat = mats['GOFrame_Deformed'] || mats.add('GOFrame_Deformed')
            def_mat.color = 'blue'
            
            def_grp.layer = lyr_deform
            
            elements.each do |el|
              n1 = nodes.find { |n| n['id'] == el['n1'] }
              n2 = nodes.find { |n| n['id'] == el['n2'] }
              rn1 = res_nodes.find { |n| n['id'] == el['n1'] }
              rn2 = res_nodes.find { |n| n['id'] == el['n2'] }
              next unless n1 && n2 && rn1 && rn2
              
              dx = n2['x'].to_f - n1['x'].to_f
              dy = n2['y'].to_f - n1['y'].to_f
              l = Math.sqrt(dx**2 + dy**2)
              l = 1.0 if l < 1e-4
              c = dx / l
              s = dy / l
              
              u1 = c * rn1['dx'].to_f + s * rn1['dy'].to_f
              v1 = -s * rn1['dx'].to_f + c * rn1['dy'].to_f
              th1 = rn1['rz'].to_f
              
              u2 = c * rn2['dx'].to_f + s * rn2['dy'].to_f
              v2 = -s * rn2['dx'].to_f + c * rn2['dy'].to_f
              th2 = rn2['rz'].to_f
              
              num_segs = 10
              pts = []
              (0..num_segs).each do |i|
                xl = i.to_f / num_segs
                x = l * xl
                
                ux = u1 + (u2 - u1) * xl
                
                n1_f = 1.0 - 3.0*xl**2 + 2.0*xl**3
                n2_f = x * (1.0 - xl)**2
                n3_f = 3.0*xl**2 - 2.0*xl**3
                n4_f = x * (xl**2 - xl)
                vx = n1_f*v1 + n2_f*th1 + n3_f*v2 + n4_f*th2
                
                gx = c * ux - s * vx
                gy = s * ux + c * vx
                
                px = n1['x'].to_f + x * c + gx * def_scale
                py = n1['y'].to_f + x * s + gy * def_scale
                pts << Geom::Point3d.new(px.m, 0, py.m)
              end
              
              (0...num_segs).each do |i|
                edge = def_grp.entities.add_line(pts[i], pts[i+1])
                edge.material = def_mat
                edge.layer = lyr_deform
              end
            end
            
            # Find and label max dx and dy
            max_dx_node = res_nodes.max_by { |rn| rn['dx'].to_f.abs }
            max_dy_node = res_nodes.max_by { |rn| rn['dy'].to_f.abs }
            
            if max_dx_node && max_dx_node['dx'].to_f.abs > 1e-5
              n = nodes.find { |nd| nd['id'] == max_dx_node['id'] }
              if n
                pt = Geom::Point3d.new((n['x'].to_f + max_dx_node['dx'].to_f * def_scale).m, 0, (n['y'].to_f + max_dx_node['dy'].to_f * def_scale).m)
                lbl = def_grp.entities.add_text(sprintf("Max dx = %.2f mm", max_dx_node['dx'].to_f * 1000), pt)
                lbl.layer = lyr_diag_labels
              end
            end
            
            if max_dy_node && max_dy_node['dy'].to_f.abs > 1e-5
              n = nodes.find { |nd| nd['id'] == max_dy_node['id'] }
              if n
                pt = Geom::Point3d.new((n['x'].to_f + max_dy_node['dx'].to_f * def_scale).m, 0, (n['y'].to_f + max_dy_node['dy'].to_f * def_scale).m)
                lbl = def_grp.entities.add_text(sprintf("Max dy = %.2f mm", max_dy_node['dy'].to_f * 1000), pt)
                lbl.layer = lyr_diag_labels
              end
            end
          end
        end

        # 6. Draw Force Diagrams
        force_types = []
        force_types << 'afd' if options['show3DAFD']
        force_types << 'sfd' if options['show3DSFD']
        force_types << 'bmd' if options['show3DBMD']
        
        if result && result['ok']
          res_elems = result['elements']
          
          force_types.each do |force_type|
            max_val = 1e-6
            res_elems.each do |re|
              v1 = force_type == 'afd' ? re['n1_forces']['axial'].to_f : (force_type == 'sfd' ? re['n1_forces']['shear'].to_f : -re['n1_forces']['moment'].to_f)
              v2 = force_type == 'afd' ? -re['n2_forces']['axial'].to_f : (force_type == 'sfd' ? -re['n2_forces']['shear'].to_f : re['n2_forces']['moment'].to_f)
              max_val = [max_val, v1.abs, v2.abs].max
              
              if force_type == 'bmd'
                el = elements.find { |e| e['id'] == re['id'] }
                if el
                  n1 = nodes.find { |n| n['id'] == el['n1'] }
                  n2 = nodes.find { |n| n['id'] == el['n2'] }
                  len = Math.sqrt((n2['x'].to_f - n1['x'].to_f)**2 + (n2['y'].to_f - n1['y'].to_f)**2)
                  el_loads = model_data['eloads'] ? model_data['eloads'].select { |ld| ld['elem'] == el['id'] } : []
                  has_sw = model_data['settings'] && model_data['settings']['include_self_weight']
                  wy = 0.0
                  angle = Math.atan2(n2['y'].to_f - n1['y'].to_f, n2['x'].to_f - n1['x'].to_f)
                  
                  if has_sw
                    sec = (model_data['sections'] || []).find { |s| s['id'] == el['sec'] }
                    if sec
                      wy -= (sec['a'].to_f / 10000.0) * sec['density'].to_f * Math.cos(angle)
                    end
                  end
                  
                  el_loads.each do |ld|
                    wy += ld['dir'] == 'Local Y' ? ld['w'].to_f : ld['w'].to_f * Math.cos(angle)
                  end
                  m_mid = (v1 + v2) / 2.0 - (wy * len**2) / 8.0
                  max_val = [max_val, m_mid.abs].max
                end
              end
            end
            scale_factor = force_type == 'afd' ? 0.05 : 0.15
            diag_scale = (frame_span * scale_factor) / max_val
            diag_grp = ents.add_group
            diag_grp.name = "Force Diagram (#{force_type.upcase})"
            diag_grp.layer = (force_type == 'afd' ? lyr_diag_afd : (force_type == 'sfd' ? lyr_diag_sfd : lyr_diag_bmd))
            
            mat_pos = mats['GOFrame_Diag_Pos'] || mats.add('GOFrame_Diag_Pos')
            mat_pos.color = Sketchup::Color.new(100, 200, 100, 128)
            mat_neg = mats['GOFrame_Diag_Neg'] || mats.add('GOFrame_Diag_Neg')
            mat_neg.color = Sketchup::Color.new(200, 100, 100, 128)
            
            elements.each do |el|
              re = res_elems.find { |r| r['id'] == el['id'] }
              next unless re
              n1 = nodes.find { |n| n['id'] == el['n1'] }
              n2 = nodes.find { |n| n['id'] == el['n2'] }
              next unless n1 && n2
              
              v1 = force_type == 'afd' ? re['n1_forces']['axial'].to_f : (force_type == 'sfd' ? re['n1_forces']['shear'].to_f : -re['n1_forces']['moment'].to_f)
              v2 = force_type == 'afd' ? -re['n2_forces']['axial'].to_f : (force_type == 'sfd' ? -re['n2_forces']['shear'].to_f : re['n2_forces']['moment'].to_f)
              
              pt1 = Geom::Point3d.new(n1['x'].to_f.m, 0, n1['y'].to_f.m)
              pt2 = Geom::Point3d.new(n2['x'].to_f.m, 0, n2['y'].to_f.m)
              vec = pt1.vector_to(pt2)
              next unless vec.valid?
              len = vec.length.to_m
              
              norm_vec = Geom::Vector3d.new(vec.z, 0, -vec.x).normalize
              
              if force_type != 'bmd'
                p1_top = pt1.offset(norm_vec, (v1 * diag_scale).m)
                p2_top = pt2.offset(norm_vec, (v2 * diag_scale).m)
                
                if v1 * v2 < 0
                  x_zero = len * (v1.abs / (v1.abs + v2.abs))
                  p_zero = pt1.offset(vec.normalize, x_zero.m)
                  
                  begin
                    f1 = diag_grp.entities.add_face(pt1, p1_top, p_zero) if p1_top.distance(pt1) > 1e-4
                    f1.material = f1.back_material = (v1 > 0 ? mat_pos : mat_neg) if f1
                  rescue
                  end
                  
                  begin
                    f2 = diag_grp.entities.add_face(p_zero, p2_top, pt2) if p2_top.distance(pt2) > 1e-4
                    f2.material = f2.back_material = (v2 > 0 ? mat_pos : mat_neg) if f2
                  rescue
                  end
                else
                  pts_face = []
                  pts_face << pt1
                  pts_face << p1_top if p1_top.distance(pt1) > 1e-4
                  pts_face << p2_top if p2_top.distance(pt2) > 1e-4
                  pts_face << pt2
                  
                  begin
                    if pts_face.length >= 3
                      f = diag_grp.entities.add_face(pts_face)
                      f.material = f.back_material = (v1 > 0 ? mat_pos : mat_neg) if f
                    end
                  rescue
                  end
                end
                diag_grp.entities.add_line(p1_top, p2_top)
                
                # Add Labels
                if v1.abs > 1e-4
                  txt1 = diag_grp.entities.add_text(sprintf("%.0f", v1), p1_top.offset(norm_vec, 0.2.m))
                  txt1.layer = lyr_diag_labels
                end
                if v2.abs > 1e-4
                  txt2 = diag_grp.entities.add_text(sprintf("%.0f", v2), p2_top.offset(norm_vec, 0.2.m))
                  txt2.layer = lyr_diag_labels
                end
              else
                el_loads = model_data['eloads'] ? model_data['eloads'].select { |ld| ld['elem'] == el['id'] } : []
                has_sw = model_data['settings'] && model_data['settings']['include_self_weight']
                wy = 0.0
                angle = Math.atan2(n2['y'].to_f - n1['y'].to_f, n2['x'].to_f - n1['x'].to_f)
                
                if has_sw
                  sec = (model_data['sections'] || []).find { |s| s['id'] == el['sec'] }
                  if sec
                    wy -= (sec['a'].to_f / 10000.0) * sec['density'].to_f * Math.cos(angle)
                  end
                end
                
                el_loads.each do |ld|
                  w1_ld = ld['w1'] ? ld['w1'].to_f : (ld['w'] ? ld['w'].to_f : 0.0)
                  w2_ld = ld['w2'] ? ld['w2'].to_f : w1_ld
                  wAvg = (w1_ld + w2_ld) / 2.0
                  wy += ld['dir'] == 'Local Y' ? wAvg : wAvg * Math.cos(angle)
                end
                
                num_segs = 10
                pts = []
                vals = []
                (0..num_segs).each do |i|
                  x_ratio = i.to_f / num_segs
                  x_len = len * x_ratio
                  m_lin = v1 + (v2 - v1) * x_ratio
                  m_par = (-wy * x_len * (len - x_len)) / 2.0
                  m_total = m_lin + m_par
                  
                  pts << pt1.offset(vec, x_len.m).offset(norm_vec, (m_total * diag_scale).m)
                  vals << { pt: pts.last, val: m_total }
                end
                
                (0...num_segs).each do |i|
                  pA = pt1.offset(vec.normalize, (len * (i.to_f/num_segs)).m)
                  pB = pt1.offset(vec.normalize, (len * ((i+1).to_f/num_segs)).m)
                  
                  begin
                    f = diag_grp.entities.add_face(pA, pts[i], pts[i+1], pB)
                    m_mid_val = (vals[i][:val] + vals[i+1][:val]) / 2.0
                    f.material = f.back_material = (m_mid_val > 0 ? mat_pos : mat_neg) if f
                  rescue
                    # Ignore face creation error if points are collinear
                  end
                  diag_grp.entities.add_line(pts[i], pts[i+1])
                end
                
                # Add Label for maximum peak in segment
                max_pt_info = vals.max_by { |v| v[:val].abs }
                if max_pt_info && max_pt_info[:val].abs > 1e-4
                  txt = diag_grp.entities.add_text(sprintf("%.0f", max_pt_info[:val]), max_pt_info[:pt].offset(norm_vec, 0.2.m))
                  txt.layer = lyr_diag_labels
                end
              end
            end
          end
        end

      rescue StandardError => e
        skp_model.abort_operation
        raise e
      end

      skp_model.commit_operation
      skp_model.active_view.zoom_extents
    end
  end
end

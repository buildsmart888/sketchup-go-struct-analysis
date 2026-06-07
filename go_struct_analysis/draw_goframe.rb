module GOStructAnalysis
  module DrawGoframe
    extend self

    def draw(data)
      model_data = data['model']
      result = data['result']

      skp_model = Sketchup.active_model
      skp_model.start_operation('Draw GO Frame 3D', true)

      begin
        layers = skp_model.layers
        lyr_frame = layers['GOFrame_Members'] || layers.add('GOFrame_Members')
        lyr_labels = layers['GOFrame_Labels'] || layers.add('GOFrame_Labels')
        lyr_loads = layers['GOFrame_Loads'] || layers.add('GOFrame_Loads')

        mats = skp_model.materials
        mat_frame = mats['GOFrame_Base'] || mats.add('GOFrame_Base')
        mat_frame.color = Sketchup::Color.new(100, 100, 100)

        mat_load = mats['GOFrame_Load'] || mats.add('GOFrame_Load')
        mat_load.color = Sketchup::Color.new(200, 0, 0)

        main_group = skp_model.active_entities.add_group
        main_group.name = "GO Frame Analysis - #{Time.now.strftime('%Y-%m-%d %H:%M')}"
        ents = main_group.entities

        # 1. Draw Members
        frame_grp = ents.add_group
        frame_grp.name = "Members"
        frame_grp.layer = lyr_frame

        nodes = model_data['nodes']
        elements = model_data['elements']

        elements.each do |el|
          n1 = nodes.find { |n| n['id'] == el['n1'] }
          n2 = nodes.find { |n| n['id'] == el['n2'] }
          next unless n1 && n2

          pt1 = Geom::Point3d.new(n1['x'].to_f.m, 0, n1['y'].to_f.m)
          pt2 = Geom::Point3d.new(n2['x'].to_f.m, 0, n2['y'].to_f.m)

          # Draw center line
          line = frame_grp.entities.add_line(pt1, pt2)
          line.layer = lyr_frame

          # Draw profile (simple square for visual)
          vec = pt1.vector_to(pt2)
          if vec.valid?
            up = (vec.parallel?(Z_AXIS) || vec.parallel?(Z_AXIS.reverse)) ? X_AXIS : Z_AXIS
            right = vec.cross(up).normalize
            up2 = right.cross(vec).normalize

            # Let's draw a simple 0.1m x 0.1m box along the line
            w = 0.05.m
            p1 = pt1.offset(right, w).offset(up2, w)
            p2 = pt1.offset(right, -w).offset(up2, w)
            p3 = pt1.offset(right, -w).offset(up2, -w)
            p4 = pt1.offset(right, w).offset(up2, -w)

            face = frame_grp.entities.add_face(p1, p2, p3, p4)
            if face
              face.pushpull(vec.length)
              face.material = mat_frame
              face.back_material = mat_frame
            end
          end
          
          # Member label
          mid_pt = Geom::Point3d.new((pt1.x + pt2.x) / 2.0, -0.2.m, (pt1.z + pt2.z) / 2.0)
          lbl = frame_grp.entities.add_text("M#{el['id']}", mid_pt)
          lbl.layer = lyr_labels
        end

        # 2. Draw Nodes
        nodes.each do |n|
          pt = Geom::Point3d.new(n['x'].to_f.m, 0.2.m, n['y'].to_f.m)
          lbl = frame_grp.entities.add_text("N#{n['id']}", pt)
          lbl.layer = lyr_labels

          # Draw support if any
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

        # 3. Output BMD/SFD/AFD if result exists
        if result && result['ok']
          res_nodes = result['nodes']
          res_elems = result['elements']
          
          # Draw Reactions
          res_nodes.each do |rn|
            fx = rn['fx'].to_f
            fy = rn['fy'].to_f
            next if fx.abs < 0.1 && fy.abs < 0.1

            pt = Geom::Point3d.new(rn['x'].to_f.m, 0, rn['y'].to_f.m)
            if fx.abs > 0.1
              v_x = fx > 0 ? X_AXIS : X_AXIS.reverse
              arrow_pt = pt.offset(v_x, -0.5.m)
              ents.add_text("#{fx.round(1)} kg", arrow_pt)
            end
            if fy.abs > 0.1
              v_y = fy > 0 ? Z_AXIS : Z_AXIS.reverse
              arrow_pt = pt.offset(v_y, -0.5.m)
              ents.add_text("#{fy.round(1)} kg", arrow_pt)
            end
          end
        end

      rescue StandardError => e
        skp_model.abort_operation
        raise e
      end

      skp_model.commit_operation
      # Zoom extents
      skp_model.active_view.zoom_extents
    end
  end
end

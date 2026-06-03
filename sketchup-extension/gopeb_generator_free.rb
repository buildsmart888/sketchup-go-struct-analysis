require 'sketchup.rb'
require 'json'
require 'tmpdir'

module GOPEBFree
  module Generator

    STEEL_DENSITY = 7850.0 # kg/m3
    TEMPLATE_DIR = File.join(File.dirname(__FILE__), "gopeb_templates")

    LIMITS = {
      min_width_m: 12.0,
      max_width_m: 40.0,
      min_bay_count: 3,
      max_bay_count: 10
    }

    DEFAULTS = {
      width_m: 20.0,
      eave_height_m: 6.0,
      ridge_height_m: 8.0,
      bay_count: 4,
      bay_spacing_m: 6.0,
      purlin_spacing_m: 1.5
    }

    SECTIONS = {
      column: {
        start_depth: 350.mm,
        end_depth: 600.mm,
        flange_width: 200.mm,
        web_thickness: 6.mm,
        flange_thickness: 10.mm
      },
      rafter: {
        start_depth: 600.mm,
        end_depth: 350.mm,
        flange_width: 200.mm,
        web_thickness: 6.mm,
        flange_thickness: 10.mm
      },
      purlin: {
        type: "Z",
        depth: 150.mm,
        flange_width: 60.mm,
        lip: 20.mm,
        thickness: 2.3.mm
      },
      brace: {
        diameter: 19.mm
      }
    }

    def self.run
      show_generator_dialog
    end

    def self.show_generator_dialog
      dialog = UI::HtmlDialog.new(
        dialog_title: "GO PEB Free",
        preferences_key: "gopeb.free.generator",
        scrollable: true,
        resizable: true,
        width: 760,
        height: 580,
        style: UI::HtmlDialog::STYLE_DIALOG
      )

      dialog.add_action_callback("createPeb") do |_context, payload_json|
        begin
          payload = DEFAULTS.merge(symbolize_keys(JSON.parse(payload_json)))
          validate_inputs!(payload)
          Sketchup.active_model.set_attribute("GOPEB_FREE", "last_generator_payload", JSON.generate(payload))
          create_peb_from_payload(payload)
          dialog.execute_script("window.gopebSetStatus('Free model created. BOQ opened.', true)")
        rescue => e
          dialog.execute_script("window.gopebSetStatus(#{JSON.generate(e.message)}, false)")
          UI.messagebox("GO PEB Free Error: #{e.message}")
          puts e.backtrace
        end
      end

      dialog.set_html(generator_dialog_html)
      dialog.show
    end

    def self.generator_dialog_html
      render_template(
        "generator_dialog.html",
        "TITLE" => "GO PEB Free",
        "SUBTITLE" => "Trial generator with locked I/H frame, Z purlin, RB19 bracing, and BOQ summary.",
        "MODE" => "free",
        "CONFIG_JSON" => JSON.generate(free_form_config),
        "PAYLOAD_JSON" => dialog_defaults_json,
        "LIMITS_JSON" => JSON.generate(LIMITS)
      )
    end

    def self.dialog_defaults_json
      raw = Sketchup.active_model.get_attribute("GOPEB_FREE", "last_generator_payload")
      payload = raw ? JSON.parse(raw) : {}
      JSON.generate(DEFAULTS.merge(symbolize_keys(payload)))
    rescue
      JSON.generate(DEFAULTS)
    end

    def self.free_form_config
      {
        tabs: [
          {
            label: "Free Building",
            upgrade: [
              "Pro unlocks custom I/H section sizes.",
              "Pro unlocks C/Z/BOX purlin controls.",
              "Pro unlocks detailed member BOQ and CSV controls."
            ],
            fields: [
              free_field(:width_m, "ความกว้างอาคาร", "m"),
              free_field(:eave_height_m, "ความสูงเสา/eave", "m"),
              free_field(:ridge_height_m, "ความสูงจั่ว/ridge", "m"),
              free_field(:bay_count, "จำนวน bay", "bay", 1),
              free_field(:bay_spacing_m, "ระยะ bay", "m"),
              free_field(:purlin_spacing_m, "ระยะห่างแป", "m")
            ]
          },
          {
            label: "Locked Defaults",
            upgrade: [
              "Column/Rafter: default tapered I/H beam.",
              "Purlin: Z D150 B60 L20 t2.3.",
              "Bracing: RB19 round bar at end bays."
            ],
            fields: [
              locked_field("column_section", "Column", "I/H D350-600 B200 tw6 tf10"),
              locked_field("rafter_section", "Rafter", "I/H D600-350 B200 tw6 tf10"),
              locked_field("purlin_section", "Purlin", "Z D150 B60 L20 t2.3"),
              locked_field("brace_section", "Bracing", "RB19")
            ]
          }
        ]
      }
    end

    def self.free_field(key, label, unit = nil, step = "any")
      { key: key, label: label, unit: unit, type: "number", step: step, default: DEFAULTS[key] }
    end

    def self.locked_field(key, label, value)
      { key: key, label: label, type: "text", default: value, locked: true, hint: "Locked in Free Trial" }
    end

    def self.create_peb_from_payload(payload)
      create_peb(DEFAULTS.merge(symbolize_keys(payload)))
    end

    def self.symbolize_keys(hash)
      hash.each_with_object({}) { |(key, value), out| out[key.to_sym] = value }
    end

    def self.render_template(name, replacements)
      html = File.read(File.join(TEMPLATE_DIR, name))
      replacements.each { |key, value| html = html.gsub("{{#{key}}}", value.to_s) }
      html
    end

    def self.run_legacy
      prompts = [
        "ความกว้างอาคาร 12-40 m",
        "ความสูงเสา/eave (m)",
        "ความสูงจั่ว/ridge (m)",
        "จำนวน bay 3-10",
        "ระยะ bay (m)",
        "ระยะห่างแป (m)"
      ]

      defaults = [
        DEFAULTS[:width_m],
        DEFAULTS[:eave_height_m],
        DEFAULTS[:ridge_height_m],
        DEFAULTS[:bay_count],
        DEFAULTS[:bay_spacing_m],
        DEFAULTS[:purlin_spacing_m]
      ]

      input = UI.inputbox(prompts, defaults, "GO PEB Free")
      return unless input

      data = {
        width_m: input[0].to_f,
        eave_height_m: input[1].to_f,
        ridge_height_m: input[2].to_f,
        bay_count: input[3].to_i,
        bay_spacing_m: input[4].to_f,
        purlin_spacing_m: input[5].to_f
      }

      validate_inputs!(data)
      create_peb(data)
    rescue => e
      UI.messagebox("GO PEB Free Error: #{e.message}")
      puts e.backtrace
    end

    def self.validate_inputs!(data)
      unless data[:width_m].between?(LIMITS[:min_width_m], LIMITS[:max_width_m])
        raise "เวอร์ชั่นฟรีรองรับความกว้าง #{LIMITS[:min_width_m].to_i}-#{LIMITS[:max_width_m].to_i} m"
      end

      unless data[:bay_count].between?(LIMITS[:min_bay_count], LIMITS[:max_bay_count])
        raise "เวอร์ชั่นฟรีรองรับจำนวน bay #{LIMITS[:min_bay_count]}-#{LIMITS[:max_bay_count]}"
      end

      raise "ความสูงจั่วต้องมากกว่าความสูงเสา" if data[:ridge_height_m] <= data[:eave_height_m]
      raise "ระยะ bay ต้องมากกว่า 0 m" if data[:bay_spacing_m] <= 0
      raise "ระยะห่างแปต้องมากกว่า 0 m" if data[:purlin_spacing_m] <= 0
    end

    def self.create_peb(data)
      model = Sketchup.active_model
      model.start_operation("Create GO PEB Free", true)

      tags = create_tags(model)
      root = model.entities.add_group
      root.name = "GO_PEB_FREE_BUILDING"

      boq = []
      width = data[:width_m].m
      eave = data[:eave_height_m].m
      ridge = data[:ridge_height_m].m
      bay_count = data[:bay_count]
      bay_spacing = data[:bay_spacing_m].m
      purlin_spacing = data[:purlin_spacing_m].m
      half = width / 2.0
      frame_flange_axis = Geom::Vector3d.new(0, 1, 0)

      frames = []

      (0..bay_count).each do |i|
        y = i * bay_spacing
        frame = {
          lb: Geom::Point3d.new(-half, y, 0),
          le: Geom::Point3d.new(-half, y, eave),
          rg: Geom::Point3d.new(0, y, ridge),
          re: Geom::Point3d.new(half, y, eave),
          rb: Geom::Point3d.new(half, y, 0)
        }
        frames << frame

        add_i_member(root, frame[:lb], frame[:le], SECTIONS[:column],
                     "Column_L_#{i}", tags[:column], tags[:centerline], boq, frame_flange_axis)
        add_i_member(root, frame[:rb], frame[:re], SECTIONS[:column],
                     "Column_R_#{i}", tags[:column], tags[:centerline], boq, frame_flange_axis)
        add_i_member(root, frame[:le], frame[:rg], SECTIONS[:rafter],
                     "Rafter_L_#{i}", tags[:rafter], tags[:centerline], boq, frame_flange_axis)
        add_i_member(root, frame[:rg], frame[:re], reverse_i_section(SECTIONS[:rafter]),
                     "Rafter_R_#{i}", tags[:rafter], tags[:centerline], boq, frame_flange_axis)
      end

      (0...bay_count).each do |i|
        f1 = frames[i]
        f2 = frames[i + 1]
        left_roof_axis = f1[:rg] - f1[:le]
        right_roof_axis = f1[:rg] - f1[:re]

        add_purlin_member(root, f1[:le], f2[:le], "Eave_Strut_L_#{i}",
                          tags[:eave], tags[:centerline], boq, left_roof_axis)
        add_purlin_member(root, f1[:re], f2[:re], "Eave_Strut_R_#{i}",
                          tags[:eave], tags[:centerline], boq, right_roof_axis)
        add_purlin_member(root, f1[:rg], f2[:rg], "Ridge_#{i}",
                          tags[:ridge], tags[:centerline], boq, Geom::Vector3d.new(1, 0, 0))

        purlin_t_values(f1[:le], f1[:rg], purlin_spacing).each_with_index do |t, idx|
          add_purlin_member(root, interp(f1[:le], f1[:rg], t), interp(f2[:le], f2[:rg], t),
                            "Purlin_L_#{i}_#{idx + 1}", tags[:purlin], tags[:centerline], boq, left_roof_axis)
        end

        purlin_t_values(f1[:re], f1[:rg], purlin_spacing).each_with_index do |t, idx|
          add_purlin_member(root, interp(f1[:re], f1[:rg], t), interp(f2[:re], f2[:rg], t),
                            "Purlin_R_#{i}_#{idx + 1}", tags[:purlin], tags[:centerline], boq, right_roof_axis)
        end
      end

      [0, bay_count - 1].uniq.each do |i|
        f1 = frames[i]
        f2 = frames[i + 1]

        add_round_member(root, f1[:le], f2[:rg], "Brace_Roof_L1_#{i}", tags[:brace], tags[:centerline], boq)
        add_round_member(root, f1[:rg], f2[:le], "Brace_Roof_L2_#{i}", tags[:brace], tags[:centerline], boq)
        add_round_member(root, f1[:rg], f2[:re], "Brace_Roof_R1_#{i}", tags[:brace], tags[:centerline], boq)
        add_round_member(root, f1[:re], f2[:rg], "Brace_Roof_R2_#{i}", tags[:brace], tags[:centerline], boq)

        add_round_member(root, f1[:lb], f2[:le], "Brace_Wall_L1_#{i}", tags[:brace], tags[:centerline], boq)
        add_round_member(root, f1[:le], f2[:lb], "Brace_Wall_L2_#{i}", tags[:brace], tags[:centerline], boq)
        add_round_member(root, f1[:rb], f2[:re], "Brace_Wall_R1_#{i}", tags[:brace], tags[:centerline], boq)
        add_round_member(root, f1[:re], f2[:rb], "Brace_Wall_R2_#{i}", tags[:brace], tags[:centerline], boq)
      end

      create_boq_summary(model, boq)
      add_free_label(model)
      model.commit_operation
      show_boq_dialog

      UI.messagebox(
        "GO PEB Free สร้างสำเร็จ\n" \
        "จำนวนชิ้นส่วน: #{boq.length}\n" \
        "น้ำหนักรวม: #{boq.sum { |x| x[:weight_kg] }.round(2)} kg"
      )
    rescue => e
      model.abort_operation
      raise e
    end

    def self.create_tags(model)
      names = {
        centerline: "GOPEB_FREE_CENTERLINE",
        column: "GOPEB_FREE_COLUMN",
        rafter: "GOPEB_FREE_RAFTER",
        eave: "GOPEB_FREE_EAVE_RIDGE",
        ridge: "GOPEB_FREE_EAVE_RIDGE",
        purlin: "GOPEB_FREE_PURLIN",
        brace: "GOPEB_FREE_BRACING"
      }

      names.each_with_object({}) do |(key, name), tags|
        tags[key] = model.layers[name] || model.layers.add(name)
      end
    end

    def self.add_i_member(root, p1, p2, section, name, solid_tag, centerline_tag, boq, profile_width_axis)
      add_centerline(root, p1, p2, name, centerline_tag)

      g = root.entities.add_group
      g.name = name
      g.layer = solid_tag
      create_i_beam_along_line(g.entities, p1, p2, section, profile_width_axis)

      length = p1.distance(p2)
      start_area = i_area_m2(section[:start_depth], section)
      end_area = i_area_m2(section[:end_depth], section)
      volume = ((start_area + end_area) / 2.0) * length.to_m
      push_boq(boq, g, name, "I/H Beam", i_section_label(section), length, volume)
    end

    def self.add_purlin_member(root, p1, p2, name, solid_tag, centerline_tag, boq, profile_width_axis)
      add_centerline(root, p1, p2, name, centerline_tag)

      g = root.entities.add_group
      g.name = name
      g.layer = solid_tag
      create_cz_purlin_along_line(g.entities, p1, p2, SECTIONS[:purlin], profile_width_axis)

      length = p1.distance(p2)
      volume = cz_area_m2(SECTIONS[:purlin]) * length.to_m
      push_boq(boq, g, name, "Z Purlin", "Z D150 B60 L20 t2.3", length, volume)
    end

    def self.add_round_member(root, p1, p2, name, solid_tag, centerline_tag, boq)
      add_centerline(root, p1, p2, name, centerline_tag)

      g = root.entities.add_group
      g.name = name
      g.layer = solid_tag
      create_round_bar_along_line(g.entities, p1, p2, SECTIONS[:brace][:diameter])

      length = p1.distance(p2)
      area = Math::PI * ((SECTIONS[:brace][:diameter].to_m / 2.0) ** 2)
      push_boq(boq, g, name, "Round Bar", "RB19", length, area * length.to_m)
    end

    def self.add_centerline(root, p1, p2, name, centerline_tag)
      cl_group = root.entities.add_group
      cl_group.name = "CL_#{name}"
      cl_group.layer = centerline_tag
      cl_group.entities.add_line(p1, p2)
    end

    def self.push_boq(boq, group, name, profile, section, length, volume)
      weight = volume * STEEL_DENSITY

      group.set_attribute("GOPEB_FREE", "name", name)
      group.set_attribute("GOPEB_FREE", "persistent_id", entity_persistent_id(group))
      group.set_attribute("GOPEB_FREE", "profile", profile)
      group.set_attribute("GOPEB_FREE", "section", section)
      group.set_attribute("GOPEB_FREE", "length_m", length.to_m)
      group.set_attribute("GOPEB_FREE", "volume_m3", volume)
      group.set_attribute("GOPEB_FREE", "weight_kg", weight)

      boq << {
        name: name,
        persistent_id: entity_persistent_id(group),
        category: free_category(name),
        profile: profile,
        section: section,
        length_m: length.to_m,
        volume_m3: volume,
        weight_kg: weight
      }
    end

    def self.create_i_beam_along_line(entities, p1, p2, section, profile_width_axis)
      vec = p2 - p1
      return if vec.length < 0.001

      x_axis = vec.clone
      x_axis.normalize!
      y_axis = profile_y_axis(x_axis, profile_width_axis)
      z_axis = x_axis.cross(y_axis)
      z_axis.normalize!

      start_points = i_section_points(p1, y_axis, z_axis, section[:start_depth], section)
      end_points = i_section_points(p2, y_axis, z_axis, section[:end_depth], section)

      faces = []
      faces << add_face(entities, start_points.reverse)
      faces << add_face(entities, end_points)

      start_points.each_index do |idx|
        next_idx = (idx + 1) % start_points.length
        faces << add_face(entities, [start_points[idx], start_points[next_idx], end_points[next_idx], end_points[idx]])
      end

      clear_face_materials(faces)
    end

    def self.create_cz_purlin_along_line(entities, p1, p2, section, profile_width_axis)
      vec = p2 - p1
      return if vec.length < 0.001

      x_axis = vec.clone
      x_axis.normalize!
      y_axis = profile_y_axis(x_axis, profile_width_axis)
      z_axis = x_axis.cross(y_axis)
      z_axis.normalize!

      depth = section[:depth]
      flange = section[:flange_width]
      lip = section[:lip]
      t = section[:thickness]

      create_box_along_axes(entities, p1, p2, y_axis, z_axis, t, depth)
      create_box_along_axes(entities, p1.offset(z_axis, (depth / 2.0) - (t / 2.0)).offset(y_axis, flange / 2.0),
                            p2.offset(z_axis, (depth / 2.0) - (t / 2.0)).offset(y_axis, flange / 2.0),
                            y_axis, z_axis, flange, t)
      create_box_along_axes(entities, p1.offset(z_axis, (-depth / 2.0) + (t / 2.0)).offset(y_axis, -flange / 2.0),
                            p2.offset(z_axis, (-depth / 2.0) + (t / 2.0)).offset(y_axis, -flange / 2.0),
                            y_axis, z_axis, flange, t)
      create_box_along_axes(entities, p1.offset(z_axis, (depth / 2.0) - t - (lip / 2.0)).offset(y_axis, flange - (t / 2.0)),
                            p2.offset(z_axis, (depth / 2.0) - t - (lip / 2.0)).offset(y_axis, flange - (t / 2.0)),
                            y_axis, z_axis, t, lip)
      create_box_along_axes(entities, p1.offset(z_axis, (-depth / 2.0) + t + (lip / 2.0)).offset(y_axis, -flange + (t / 2.0)),
                            p2.offset(z_axis, (-depth / 2.0) + t + (lip / 2.0)).offset(y_axis, -flange + (t / 2.0)),
                            y_axis, z_axis, t, lip)
    end

    def self.create_round_bar_along_line(entities, p1, p2, diameter, segments = 12)
      vec = p2 - p1
      return if vec.length < 0.001

      x_axis = vec.clone
      x_axis.normalize!
      y_axis = profile_y_axis(x_axis, nil)
      z_axis = x_axis.cross(y_axis)
      z_axis.normalize!
      radius = diameter / 2.0
      start_points = []
      end_points = []

      segments.times do |idx|
        angle = (2.0 * Math::PI * idx) / segments
        start_points << p1.offset(y_axis, Math.cos(angle) * radius).offset(z_axis, Math.sin(angle) * radius)
        end_points << p2.offset(y_axis, Math.cos(angle) * radius).offset(z_axis, Math.sin(angle) * radius)
      end

      solid_center = average_point(start_points + end_points)
      faces = []
      faces << add_oriented_face(entities, start_points.reverse, solid_center)
      faces << add_oriented_face(entities, end_points, solid_center)
      segments.times do |idx|
        next_idx = (idx + 1) % segments
        faces << add_oriented_face(entities, [start_points[idx], start_points[next_idx], end_points[next_idx], end_points[idx]], solid_center)
      end
      clear_face_materials(faces)
    end

    def self.create_box_along_axes(entities, p1, p2, y_axis, z_axis, w, h)
      hw = w / 2.0
      hh = h / 2.0
      a = p1.offset(y_axis, -hw).offset(z_axis, -hh)
      b = p1.offset(y_axis,  hw).offset(z_axis, -hh)
      c = p1.offset(y_axis,  hw).offset(z_axis,  hh)
      d = p1.offset(y_axis, -hw).offset(z_axis,  hh)
      e = p2.offset(y_axis, -hw).offset(z_axis, -hh)
      f = p2.offset(y_axis,  hw).offset(z_axis, -hh)
      g = p2.offset(y_axis,  hw).offset(z_axis,  hh)
      h2 = p2.offset(y_axis, -hw).offset(z_axis,  hh)
      solid_center = average_point([a, b, c, d, e, f, g, h2])

      faces = []
      faces << add_oriented_face(entities, [a, d, c, b], solid_center)
      faces << add_oriented_face(entities, [e, f, g, h2], solid_center)
      faces << add_oriented_face(entities, [a, b, f, e], solid_center)
      faces << add_oriented_face(entities, [b, c, g, f], solid_center)
      faces << add_oriented_face(entities, [c, d, h2, g], solid_center)
      faces << add_oriented_face(entities, [d, a, e, h2], solid_center)
      clear_face_materials(faces)
    end

    def self.i_section_points(base, y_axis, z_axis, depth, section)
      half_b = section[:flange_width] / 2.0
      half_tw = section[:web_thickness] / 2.0
      half_d = depth / 2.0
      tf = section[:flange_thickness]
      coords = [
        [-half_b, -half_d],
        [ half_b, -half_d],
        [ half_b, -half_d + tf],
        [ half_tw, -half_d + tf],
        [ half_tw,  half_d - tf],
        [ half_b,  half_d - tf],
        [ half_b,  half_d],
        [-half_b,  half_d],
        [-half_b,  half_d - tf],
        [-half_tw, half_d - tf],
        [-half_tw, -half_d + tf],
        [-half_b, -half_d + tf]
      ]
      coords.map { |y, z| base.offset(y_axis, y).offset(z_axis, z) }
    end

    def self.profile_y_axis(x_axis, preferred_axis)
      if preferred_axis
        y_axis = preferred_axis.clone
        dot = y_axis.dot(x_axis)
        y_axis = y_axis - Geom::Vector3d.new(x_axis.x * dot, x_axis.y * dot, x_axis.z * dot)
      else
        y_axis = Geom::Vector3d.new(0, 0, 1).cross(x_axis)
      end

      y_axis = Geom::Vector3d.new(1, 0, 0) if y_axis.length < 0.001
      y_axis.normalize!
      y_axis
    end

    def self.add_face(entities, points)
      face = entities.add_face(points)
      return nil unless face
      face
    end

    def self.add_oriented_face(entities, points, solid_center)
      face = entities.add_face(points)
      return nil unless face
      face_center = average_point(face.vertices.map { |vertex| vertex.position })
      outward = face_center - solid_center
      face.reverse! if outward.length > 0.001 && face.normal.dot(outward) < 0
      face
    end

    def self.clear_face_materials(faces)
      faces.compact.each do |face|
        face.material = nil
        face.back_material = nil
      end
    end

    def self.average_point(points)
      count = points.length.to_f
      Geom::Point3d.new(
        points.sum { |point| point.x } / count,
        points.sum { |point| point.y } / count,
        points.sum { |point| point.z } / count
      )
    end

    def self.reverse_i_section(section)
      {
        start_depth: section[:end_depth],
        end_depth: section[:start_depth],
        flange_width: section[:flange_width],
        web_thickness: section[:web_thickness],
        flange_thickness: section[:flange_thickness]
      }
    end

    def self.i_area_m2(depth, section)
      d = depth.to_m
      b = section[:flange_width].to_m
      tw = section[:web_thickness].to_m
      tf = section[:flange_thickness].to_m
      (2.0 * b * tf) + (tw * (d - (2.0 * tf)))
    end

    def self.cz_area_m2(section)
      section[:thickness].to_m * (
        section[:depth].to_m +
        (2.0 * section[:flange_width].to_m) +
        (2.0 * section[:lip].to_m)
      )
    end

    def self.i_section_label(section)
      "I/H D#{dim_mm(section[:start_depth])}-#{dim_mm(section[:end_depth])} " \
        "B#{dim_mm(section[:flange_width])} tw#{dim_mm(section[:web_thickness])} tf#{dim_mm(section[:flange_thickness])}"
    end

    def self.dim_mm(length)
      value = length.to_mm.round(2)
      value == value.to_i ? value.to_i.to_s : value.to_s
    end

    def self.entity_persistent_id(entity)
      entity.respond_to?(:persistent_id) ? entity.persistent_id : nil
    end

    def self.free_category(name)
      case name
      when /^Column/
        "Main Column"
      when /^Rafter/
        "Main Rafter"
      when /^Purlin/
        "Roof Purlin"
      when /^Eave_Strut/
        "Eave Strut"
      when /^Ridge/
        "Ridge Member"
      when /^Brace_Roof/
        "Roof Bracing"
      when /^Brace_Wall/
        "Wall Bracing"
      else
        "Other"
      end
    end

    def self.interp(p1, p2, t)
      Geom::Point3d.new(
        p1.x + (p2.x - p1.x) * t,
        p1.y + (p2.y - p1.y) * t,
        p1.z + (p2.z - p1.z) * t
      )
    end

    def self.purlin_t_values(p1, p2, spacing)
      length = p1.distance(p2)
      values = []
      distance = spacing

      while distance < length - 0.001
        values << (distance / length)
        distance += spacing
      end

      values
    end

    def self.create_boq_summary(model, boq)
      total_len = boq.sum { |x| x[:length_m] }
      total_volume = boq.sum { |x| x[:volume_m3] }
      total_weight = boq.sum { |x| x[:weight_kg] }

      text = "GO PEB FREE BOQ SUMMARY\n"
      text += "Limited Trial Version\n"
      text += "Total Members: #{boq.length}\n"
      text += "Total Length: #{total_len.round(2)} m\n"
      text += "Steel Volume: #{total_volume.round(4)} m3\n"
      text += "Steel Weight: #{total_weight.round(2)} kg\n"

      grouped = {}
      boq.each do |item|
        key = [item[:profile], item[:section]]
        grouped[key] ||= { category: "Free Summary", profile: item[:profile], section: item[:section], qty: 0, length_m: 0.0, volume_m3: 0.0, weight_kg: 0.0 }
        grouped[key][:qty] += 1
        grouped[key][:length_m] += item[:length_m]
        grouped[key][:volume_m3] += item[:volume_m3]
        grouped[key][:weight_kg] += item[:weight_kg]
      end

      text += "\nBY PROFILE\n"
      grouped.values.each do |row|
        text += "#{row[:profile]} | #{row[:section]} | Qty #{row[:qty]} | Len #{row[:length_m].round(2)} m | Wt #{row[:weight_kg].round(2)} kg\n"
      end

      model.set_attribute("GOPEB_FREE", "boq_summary", text)
      payload = {
        summary: {
          members: boq.length,
          length_m: total_len,
          surface_m2: 0.0,
          volume_m3: total_volume,
          weight_kg: total_weight
        },
        grouped: grouped.values,
        items: boq
      }
      model.set_attribute("GOPEB_FREE", "boq_json", JSON.generate(payload))
      @last_boq = boq
      @last_grouped = grouped.values
      puts text
    end

    def self.show_boq_dialog
      raw = Sketchup.active_model.get_attribute("GOPEB_FREE", "boq_json")
      return unless raw
      payload = JSON.parse(raw)
      @last_boq = symbolize_deep(payload["items"] || []) if !@last_boq || @last_boq.empty?
      @last_grouped = symbolize_deep(payload["grouped"] || []) if !@last_grouped || @last_grouped.empty?

      dialog = UI::HtmlDialog.new(
        dialog_title: "GO PEB Free BOQ",
        preferences_key: "gopeb.free.boq",
        scrollable: true,
        resizable: true,
        width: 860,
        height: 620,
        style: UI::HtmlDialog::STYLE_DIALOG
      )

      dialog.add_action_callback("exportBoq") do |_context, _payload_json|
        path = write_free_boq_csv(Sketchup.active_model, @last_boq || [], @last_grouped || [])
        message = path ? "Exported: #{path}" : "Export failed"
        dialog.execute_script("window.gopebBoqStatus(#{JSON.generate(message)})")
      end

      dialog.add_action_callback("selectMember") do |_context, payload_json|
        data = JSON.parse(payload_json)
        select_entity_by_persistent_id(data["persistent_id"].to_i)
      rescue => e
        dialog.execute_script("window.gopebBoqStatus(#{JSON.generate(e.message)})")
      end

      html = render_template(
        "boq_dialog.html",
        "TITLE" => "GO PEB Free BOQ",
        "SUBTITLE" => "Trial summary by locked steel profiles.",
        "MODE" => "free",
        "BOQ_JSON" => JSON.generate(payload)
      )
      dialog.set_html(html)
      dialog.show
    end

    def self.symbolize_deep(value)
      case value
      when Array
        value.map { |item| symbolize_deep(item) }
      when Hash
        value.each_with_object({}) do |(key, item), result|
          result[key.to_sym] = symbolize_deep(item)
        end
      else
        value
      end
    end

    def self.write_free_boq_csv(model, boq, grouped)
      folder = if model.path && !model.path.empty?
                 File.dirname(model.path)
               else
                 desktop = File.join(ENV["USERPROFILE"].to_s, "Desktop")
                 File.directory?(desktop) ? desktop : Dir.tmpdir
               end
      path = File.join(folder, "gopeb_free_boq_#{Time.now.strftime('%Y%m%d_%H%M%S')}.csv")
      File.open(path, "w") do |file|
        file.puts csv_row(["GO PEB FREE BOQ SUMMARY"])
        file.puts csv_row(["Total Members", boq.length])
        file.puts csv_row(["Total Length (m)", boq.sum { |x| x[:length_m] }.round(3)])
        file.puts csv_row(["Total Volume (m3)", boq.sum { |x| x[:volume_m3] }.round(5)])
        file.puts csv_row(["Total Weight (kg)", boq.sum { |x| x[:weight_kg] }.round(3)])
        file.puts
        file.puts csv_row(["BY PROFILE"])
        file.puts csv_row(["Profile", "Section", "Qty", "Length (m)", "Volume (m3)", "Weight (kg)"])
        grouped.each do |row|
          file.puts csv_row([row[:profile], row[:section], row[:qty], row[:length_m].round(3), row[:volume_m3].round(5), row[:weight_kg].round(3)])
        end
      end
      path
    rescue => e
      puts "GO PEB Free CSV export failed: #{e.message}"
      nil
    end

    def self.csv_row(values)
      values.map { |value| csv_escape(value) }.join(",")
    end

    def self.csv_escape(value)
      text = value.to_s
      escaped = text.gsub('"', '""')
      needs_quotes = escaped.include?(",") || escaped.include?('"') || escaped.include?("\n")
      needs_quotes ? "\"#{escaped}\"" : escaped
    end

    def self.select_entity_by_persistent_id(persistent_id)
      model = Sketchup.active_model
      entity = model.respond_to?(:find_entity_by_persistent_id) ? model.find_entity_by_persistent_id(persistent_id) : nil
      raise "Member not found in model" unless entity

      model.selection.clear
      model.selection.add(entity)
    end

    def self.add_free_label(model)
      model.entities.add_text(
        "Generated by GO PEB Free",
        Geom::Point3d.new(0, -3000.mm, 2500.mm)
      )
    end

    unless file_loaded?(__FILE__)
      menu = UI.menu("Plugins").add_submenu("GO PEB Free")
      menu.add_item("Create Free PEB") {
        self.run
      }
      menu.add_item("Show Last Free BOQ") {
        self.show_boq_dialog
      }
      file_loaded(__FILE__)
    end

  end
end

require 'sketchup.rb'
require 'tmpdir'
require 'json'

module GOPEB
  module Generator

    STEEL_DENSITY = 7850.0 # kg/m3
    TEMPLATE_DIR = File.join(File.dirname(__FILE__), "gopeb_templates")

    DEFAULTS = {
      width_m: 20.0,
      eave_height_m: 6.0,
      ridge_height_m: 8.0,
      bay_count: 4,
      bay_spacing_m: 6.0,
      purlin_spacing_m: 1.5,
      column_base_depth_mm: 350.0,
      column_top_depth_mm: 600.0,
      column_flange_width_mm: 200.0,
      column_web_thk_mm: 6.0,
      column_flange_thk_mm: 10.0,
      rafter_eave_depth_mm: 600.0,
      rafter_ridge_depth_mm: 350.0,
      rafter_flange_width_mm: 200.0,
      rafter_web_thk_mm: 6.0,
      rafter_flange_thk_mm: 10.0,
      purlin_type: "Z",
      purlin_depth_mm: 150.0,
      purlin_flange_width_mm: 60.0,
      purlin_lip_mm: 20.0,
      purlin_thk_mm: 2.3,
      roof_brace_bay_layout: "COUNT",
      roof_brace_max_bay_spacing_m: 18.0,
      roof_brace_bay_count: 2,
      roof_brace_left_x_per_bay: 3,
      roof_brace_right_x_per_bay: 3,
      roof_brace_profile: "ROUND",
      roof_brace_dia_mm: 19.0,
      roof_brace_box_w_mm: 50.0,
      roof_brace_box_h_mm: 50.0,
      roof_brace_angle_leg_mm: 50.0,
      roof_brace_angle_thk_mm: 5.0,
      brace_w_mm: 50.0,
      brace_h_mm: 50.0,
      boq_after_create: "OPEN BOQ TABLE",
      csv_export: "MANUAL FROM BOQ"
    }

    def self.run
      show_generator_dialog
    end

    def self.show_generator_dialog
      dialog = UI::HtmlDialog.new(
        dialog_title: "GO PEB Generator",
        preferences_key: "gopeb.generator",
        scrollable: true,
        resizable: true,
        width: 980,
        height: 720,
        style: UI::HtmlDialog::STYLE_DIALOG
      )

      dialog.add_action_callback("createPeb") do |_context, payload_json|
        begin
          payload = normalize_payload(JSON.parse(payload_json))
          validate_generator_payload(payload)
          Sketchup.active_model.set_attribute("GOPEB", "last_generator_payload", JSON.generate(payload))
          create_peb_from_payload(payload)
          dialog.execute_script("window.gopebSetStatus('Model created. BOQ opened.', true)")
        rescue => e
          dialog.execute_script("window.gopebSetStatus(#{JSON.generate(e.message)}, false)")
          UI.messagebox("Error: #{e.message}")
          puts e.backtrace
        end
      end

      dialog.set_html(generator_dialog_html)
      dialog.show
    end

    def self.dialog_defaults_json
      raw = Sketchup.active_model.get_attribute("GOPEB", "last_generator_payload")
      payload = raw ? JSON.parse(raw) : {}
      JSON.generate(DEFAULTS.merge(symbolize_keys(payload)))
    rescue
      JSON.generate(DEFAULTS)
    end

    def self.generator_dialog_html
      render_template(
        "generator_dialog.html",
        "TITLE" => "GO PEB Generator",
        "SUBTITLE" => "Parametric pre-engineered building frame, purlin, bracing, and BOQ.",
        "MODE" => "pro",
        "CONFIG_JSON" => JSON.generate(pro_form_config),
        "PAYLOAD_JSON" => dialog_defaults_json,
        "LIMITS_JSON" => JSON.generate({})
      )
    end

    def self.pro_form_config
      {
        tabs: [
          {
            label: "Building",
            fields: [
              field(:width_m, "ความกว้างอาคาร", "m"),
              field(:eave_height_m, "ความสูงเสา/eave", "m"),
              field(:ridge_height_m, "ความสูงจั่ว/ridge", "m"),
              field(:bay_count, "จำนวน bay", "bay", 1),
              field(:bay_spacing_m, "ระยะ bay", "m"),
              field(:purlin_spacing_m, "ระยะห่างแป", "m")
            ]
          },
          {
            label: "Main Frame",
            fields: [
              field(:column_base_depth_mm, "Column base depth D1", "mm"),
              field(:column_top_depth_mm, "Column top depth D2", "mm"),
              field(:column_flange_width_mm, "Column flange width B", "mm"),
              field(:column_web_thk_mm, "Column web thickness tw", "mm"),
              field(:column_flange_thk_mm, "Column flange thickness tf", "mm"),
              field(:rafter_eave_depth_mm, "Rafter eave depth D1", "mm"),
              field(:rafter_ridge_depth_mm, "Rafter ridge depth D2", "mm"),
              field(:rafter_flange_width_mm, "Rafter flange width B", "mm"),
              field(:rafter_web_thk_mm, "Rafter web thickness tw", "mm"),
              field(:rafter_flange_thk_mm, "Rafter flange thickness tf", "mm")
            ]
          },
          {
            label: "Purlin",
            fields: [
              select_field(:purlin_type, "Purlin type", ["BOX", "C", "Z"]),
              field(:purlin_depth_mm, "Purlin depth D", "mm"),
              field(:purlin_flange_width_mm, "Purlin flange width B", "mm"),
              field(:purlin_lip_mm, "Purlin lip L", "mm"),
              field(:purlin_thk_mm, "Purlin thickness t", "mm")
            ]
          },
          {
            label: "Bracing",
            fields: [
              select_field(:roof_brace_bay_layout, "Roof brace bay layout", ["COUNT", "AUTO"]),
              field(:roof_brace_max_bay_spacing_m, "Roof brace max bay spacing", "m"),
              field(:roof_brace_bay_count, "Roof brace braced bay count", "bay", 1),
              field(:roof_brace_left_x_per_bay, "Roof brace left X per bay", "X", 1),
              field(:roof_brace_right_x_per_bay, "Roof brace right X per bay", "X", 1),
              select_field(:roof_brace_profile, "Roof brace profile", ["ROUND", "BOX", "ANGLE"]),
              field(:roof_brace_dia_mm, "Round diameter", "mm"),
              field(:roof_brace_box_w_mm, "Box width", "mm"),
              field(:roof_brace_box_h_mm, "Box height", "mm"),
              field(:roof_brace_angle_leg_mm, "Angle leg", "mm"),
              field(:roof_brace_angle_thk_mm, "Angle thickness", "mm"),
              field(:brace_w_mm, "Wall/Base brace width", "mm"),
              field(:brace_h_mm, "Wall/Base brace height", "mm")
            ]
          },
          {
            label: "BOQ / Output",
            fields: [
              select_field(:boq_after_create, "After create", ["OPEN BOQ TABLE"]),
              select_field(:csv_export, "CSV export", ["MANUAL FROM BOQ"])
            ]
          }
        ]
      }
    end

    def self.field(key, label, unit = nil, step = "any")
      { key: key, label: label, unit: unit, type: "number", step: step, default: DEFAULTS[key] }
    end

    def self.select_field(key, label, options)
      { key: key, label: label, type: "select", options: options, default: DEFAULTS[key] }
    end

    def self.create_peb_from_payload(payload)
      create_peb(normalize_payload(payload))
    end

    def self.normalize_payload(payload)
      data = DEFAULTS.merge(symbolize_keys(payload))
      data[:purlin_type] = data[:purlin_type].to_s.strip.upcase
      data[:roof_brace_bay_layout] = data[:roof_brace_bay_layout].to_s.strip.upcase
      data[:roof_brace_profile] = data[:roof_brace_profile].to_s.strip.upcase
      data
    end

    def self.validate_generator_payload(payload)
      raise "ความสูงจั่วต้องมากกว่าความสูงเสา" if payload[:ridge_height_m].to_f <= payload[:eave_height_m].to_f
      raise "จำนวน bay ต้องมากกว่า 0" if payload[:bay_count].to_i <= 0
      raise "ระยะ bay ต้องมากกว่า 0 m" if payload[:bay_spacing_m].to_f <= 0
      raise "ระยะห่างแปต้องมากกว่า 0 m" if payload[:purlin_spacing_m].to_f <= 0
      raise "Roof brace braced bay count ต้องไม่เกินจำนวน bay" if payload[:roof_brace_bay_count].to_i > payload[:bay_count].to_i
      true
    end

    def self.symbolize_keys(hash)
      hash.each_with_object({}) { |(key, value), out| out[key.to_sym] = value }
    end

    def self.render_template(name, replacements)
      html = File.read(File.join(TEMPLATE_DIR, name))
      replacements.each do |key, value|
        html = html.gsub("{{#{key}}}", value.to_s)
      end
      html
    end

    def self.run_legacy
      prompts = [
        "ความกว้างอาคาร (m)",
        "ความสูงเสา/eave (m)",
        "ความสูงจั่ว/ridge (m)",
        "จำนวนช่วงเสา",
        "ระยะช่วงเสา (m)",
        "ระยะห่างแป (m)",
        "Column base depth D1 (mm)",
        "Column top depth D2 (mm)",
        "Column flange width B (mm)",
        "Column web thickness tw (mm)",
        "Column flange thickness tf (mm)",
        "Rafter eave depth D1 (mm)",
        "Rafter ridge depth D2 (mm)",
        "Rafter flange width B (mm)",
        "Rafter web thickness tw (mm)",
        "Rafter flange thickness tf (mm)",
        "Purlin type (BOX/C/Z)",
        "Purlin depth D (mm)",
        "Purlin flange width B (mm)",
        "Purlin lip L (mm)",
        "Purlin thickness t (mm)",
        "Roof brace bay layout (AUTO/COUNT)",
        "Roof brace max bay spacing (m)",
        "Roof brace braced bay count",
        "Roof brace left X per bay",
        "Roof brace right X per bay",
        "Roof brace profile (ROUND/BOX/ANGLE)",
        "Roof brace round diameter (mm)",
        "Roof brace box width (mm)",
        "Roof brace box height (mm)",
        "Roof brace angle leg (mm)",
        "Roof brace angle thickness (mm)",
        "Brace width (mm)",
        "Brace height (mm)"
      ]

      defaults = [
        DEFAULTS[:width_m],
        DEFAULTS[:eave_height_m],
        DEFAULTS[:ridge_height_m],
        DEFAULTS[:bay_count],
        DEFAULTS[:bay_spacing_m],
        DEFAULTS[:purlin_spacing_m],
        DEFAULTS[:column_base_depth_mm],
        DEFAULTS[:column_top_depth_mm],
        DEFAULTS[:column_flange_width_mm],
        DEFAULTS[:column_web_thk_mm],
        DEFAULTS[:column_flange_thk_mm],
        DEFAULTS[:rafter_eave_depth_mm],
        DEFAULTS[:rafter_ridge_depth_mm],
        DEFAULTS[:rafter_flange_width_mm],
        DEFAULTS[:rafter_web_thk_mm],
        DEFAULTS[:rafter_flange_thk_mm],
        DEFAULTS[:purlin_type],
        DEFAULTS[:purlin_depth_mm],
        DEFAULTS[:purlin_flange_width_mm],
        DEFAULTS[:purlin_lip_mm],
        DEFAULTS[:purlin_thk_mm],
        DEFAULTS[:roof_brace_bay_layout],
        DEFAULTS[:roof_brace_max_bay_spacing_m],
        DEFAULTS[:roof_brace_bay_count],
        DEFAULTS[:roof_brace_left_x_per_bay],
        DEFAULTS[:roof_brace_right_x_per_bay],
        DEFAULTS[:roof_brace_profile],
        DEFAULTS[:roof_brace_dia_mm],
        DEFAULTS[:roof_brace_box_w_mm],
        DEFAULTS[:roof_brace_box_h_mm],
        DEFAULTS[:roof_brace_angle_leg_mm],
        DEFAULTS[:roof_brace_angle_thk_mm],
        DEFAULTS[:brace_w_mm],
        DEFAULTS[:brace_h_mm]
      ]

      input = UI.inputbox(prompts, defaults, "GO PEB Generator")
      return unless input

      data = {
        width_m: input[0].to_f,
        eave_height_m: input[1].to_f,
        ridge_height_m: input[2].to_f,
        bay_count: input[3].to_i,
        bay_spacing_m: input[4].to_f,
        purlin_spacing_m: input[5].to_f,
        column_base_depth_mm: input[6].to_f,
        column_top_depth_mm: input[7].to_f,
        column_flange_width_mm: input[8].to_f,
        column_web_thk_mm: input[9].to_f,
        column_flange_thk_mm: input[10].to_f,
        rafter_eave_depth_mm: input[11].to_f,
        rafter_ridge_depth_mm: input[12].to_f,
        rafter_flange_width_mm: input[13].to_f,
        rafter_web_thk_mm: input[14].to_f,
        rafter_flange_thk_mm: input[15].to_f,
        purlin_type: input[16].to_s.strip.upcase,
        purlin_depth_mm: input[17].to_f,
        purlin_flange_width_mm: input[18].to_f,
        purlin_lip_mm: input[19].to_f,
        purlin_thk_mm: input[20].to_f,
        roof_brace_bay_layout: input[21].to_s.strip.upcase,
        roof_brace_max_bay_spacing_m: input[22].to_f,
        roof_brace_bay_count: input[23].to_i,
        roof_brace_left_x_per_bay: input[24].to_i,
        roof_brace_right_x_per_bay: input[25].to_i,
        roof_brace_profile: input[26].to_s.strip.upcase,
        roof_brace_dia_mm: input[27].to_f,
        roof_brace_box_w_mm: input[28].to_f,
        roof_brace_box_h_mm: input[29].to_f,
        roof_brace_angle_leg_mm: input[30].to_f,
        roof_brace_angle_thk_mm: input[31].to_f,
        brace_w_mm: input[32].to_f,
        brace_h_mm: input[33].to_f
      }

      create_peb(data)
    end

    def self.create_peb(data)
      model = Sketchup.active_model
      model.start_operation("Create GO PEB", true)

      tags = create_tags(model)

      root = model.entities.add_group
      root.name = "GO_PEB_BUILDING"

      boq = []

      width = data[:width_m].m
      eave = data[:eave_height_m].m
      ridge = data[:ridge_height_m].m
      bay_spacing = data[:bay_spacing_m].m
      purlin_spacing = data[:purlin_spacing_m].m
      bay_count = data[:bay_count]
      half = width / 2.0

      raise "ระยะห่างแปต้องมากกว่า 0 m" if purlin_spacing <= 0

      column_section = {
        start_depth: data[:column_base_depth_mm].mm,
        end_depth: data[:column_top_depth_mm].mm,
        flange_width: data[:column_flange_width_mm].mm,
        web_thickness: data[:column_web_thk_mm].mm,
        flange_thickness: data[:column_flange_thk_mm].mm
      }

      rafter_section = {
        start_depth: data[:rafter_eave_depth_mm].mm,
        end_depth: data[:rafter_ridge_depth_mm].mm,
        flange_width: data[:rafter_flange_width_mm].mm,
        web_thickness: data[:rafter_web_thk_mm].mm,
        flange_thickness: data[:rafter_flange_thk_mm].mm
      }

      purlin_section = {
        type: data[:purlin_type],
        depth: data[:purlin_depth_mm].mm,
        flange_width: data[:purlin_flange_width_mm].mm,
        lip: data[:purlin_lip_mm].mm,
        thickness: data[:purlin_thk_mm].mm
      }

      roof_brace_section = {
        profile: data[:roof_brace_profile],
        diameter: data[:roof_brace_dia_mm].mm,
        box_w: data[:roof_brace_box_w_mm].mm,
        box_h: data[:roof_brace_box_h_mm].mm,
        angle_leg: data[:roof_brace_angle_leg_mm].mm,
        angle_thickness: data[:roof_brace_angle_thk_mm].mm
      }

      validate_i_section!("Column", column_section)
      validate_i_section!("Rafter", rafter_section)
      validate_purlin_section!(purlin_section)
      validate_roof_brace_section!(roof_brace_section)
      validate_roof_brace_layout!(
        data[:roof_brace_bay_layout],
        data[:roof_brace_max_bay_spacing_m],
        data[:roof_brace_left_x_per_bay],
        data[:roof_brace_right_x_per_bay]
      )
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

        add_i_member(root, frame[:lb], frame[:le],
                     column_section,
                     "Column_L_#{i}", tags[:column], tags[:centerline], boq,
                     frame_flange_axis)

        add_i_member(root, frame[:rb], frame[:re],
                     column_section,
                     "Column_R_#{i}", tags[:column], tags[:centerline], boq,
                     frame_flange_axis)

        add_i_member(root, frame[:le], frame[:rg],
                     rafter_section,
                     "Rafter_L_#{i}", tags[:rafter], tags[:centerline], boq,
                     frame_flange_axis)

        add_i_member(root, frame[:rg], frame[:re],
                     reverse_i_section(rafter_section),
                     "Rafter_R_#{i}", tags[:rafter], tags[:centerline], boq,
                     frame_flange_axis)
      end

      (0...bay_count).each do |i|
        f1 = frames[i]
        f2 = frames[i + 1]
        left_roof_axis = f1[:rg] - f1[:le]
        right_roof_axis = f1[:rg] - f1[:re]

        add_purlin_member(root, f1[:le], f2[:le],
                          purlin_section, "Eave_Strut_L_#{i}",
                          tags[:eave], tags[:centerline], boq, left_roof_axis)

        add_purlin_member(root, f1[:re], f2[:re],
                          purlin_section, "Eave_Strut_R_#{i}",
                          tags[:eave], tags[:centerline], boq, right_roof_axis)

        add_purlin_member(root, f1[:rg], f2[:rg],
                          purlin_section, "Ridge_#{i}",
                          tags[:ridge], tags[:centerline], boq, Geom::Vector3d.new(1, 0, 0))

        # base tie
        add_member(root, f1[:lb], f2[:lb],
                   data[:brace_w_mm].mm, data[:brace_h_mm].mm,
                   "Base_Tie_L_#{i}", tags[:base_tie], tags[:centerline], boq)

        add_member(root, f1[:rb], f2[:rb],
                   data[:brace_w_mm].mm, data[:brace_h_mm].mm,
                   "Base_Tie_R_#{i}", tags[:base_tie], tags[:centerline], boq)

        purlin_t_values(f1[:le], f1[:rg], purlin_spacing).each_with_index do |t, idx|
          p1 = interp(f1[:le], f1[:rg], t)
          p2 = interp(f2[:le], f2[:rg], t)

          add_purlin_member(root, p1, p2,
                            purlin_section, "Purlin_L_#{i}_#{idx + 1}",
                            tags[:purlin], tags[:centerline], boq, left_roof_axis)
        end

        purlin_t_values(f1[:re], f1[:rg], purlin_spacing).each_with_index do |t, idx|
          p3 = interp(f1[:re], f1[:rg], t)
          p4 = interp(f2[:re], f2[:rg], t)

          add_purlin_member(root, p3, p4,
                            purlin_section, "Purlin_R_#{i}_#{idx + 1}",
                            tags[:purlin], tags[:centerline], boq, right_roof_axis)
        end
      end

      [0, bay_count - 1].uniq.each do |i|
        f1 = frames[i]
        f2 = frames[i + 1]

        add_member(root, f1[:lb], f2[:le],
                   data[:brace_w_mm].mm, data[:brace_h_mm].mm,
                   "Brace_Wall_L1_#{i}", tags[:brace], tags[:centerline], boq)

        add_member(root, f1[:le], f2[:lb],
                   data[:brace_w_mm].mm, data[:brace_h_mm].mm,
                   "Brace_Wall_L2_#{i}", tags[:brace], tags[:centerline], boq)

        add_member(root, f1[:rb], f2[:re],
                   data[:brace_w_mm].mm, data[:brace_h_mm].mm,
                   "Brace_Wall_R1_#{i}", tags[:brace], tags[:centerline], boq)

        add_member(root, f1[:re], f2[:rb],
                   data[:brace_w_mm].mm, data[:brace_h_mm].mm,
                   "Brace_Wall_R2_#{i}", tags[:brace], tags[:centerline], boq)
      end

      roof_brace_bays = roof_brace_bay_indices(
        bay_count,
        bay_spacing,
        data[:roof_brace_bay_count],
        data[:roof_brace_bay_layout],
        data[:roof_brace_max_bay_spacing_m].m
      )

      roof_brace_bays.each do |i|
        f1 = frames[i]
        f2 = frames[i + 1]

        add_roof_brace_x_set(root, f1[:le], f1[:rg], f2[:le], f2[:rg],
                             data[:roof_brace_left_x_per_bay],
                             roof_brace_section, "Brace_Roof_L_#{i}",
                             tags[:brace], tags[:centerline], boq)
      end

      roof_brace_bays.each do |i|
        f1 = frames[i]
        f2 = frames[i + 1]

        add_roof_brace_x_set(root, f1[:rg], f1[:re], f2[:rg], f2[:re],
                             data[:roof_brace_right_x_per_bay],
                             roof_brace_section, "Brace_Roof_R_#{i}",
                             tags[:brace], tags[:centerline], boq)
      end

      create_boq_report(model, boq)

      model.commit_operation
      show_boq_dialog

      UI.messagebox(
        "สร้าง PEB สำเร็จ\n" \
        "จำนวนชิ้นส่วน: #{boq.length}\n" \
        "น้ำหนักรวม: #{boq.sum { |x| x[:weight_kg] }.round(2)} kg"
      )

    rescue => e
      model.abort_operation
      UI.messagebox("Error: #{e.message}")
      puts e.backtrace
    end

    def self.create_tags(model)
      names = {
        centerline: "PEB_CENTERLINE",
        column: "PEB_MAIN_COLUMN",
        rafter: "PEB_MAIN_RAFTER",
        eave: "PEB_EAVE_STRUT",
        ridge: "PEB_RIDGE",
        purlin: "PEB_PURLIN",
        brace: "PEB_BRACING",
        base_tie: "PEB_BASE_TIE"
      }

      tags = {}

      names.each do |key, name|
        tags[key] = model.layers[name] || model.layers.add(name)
      end

      tags
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
      return [] if spacing <= 0 || length <= spacing

      values = []
      distance = spacing

      while distance < length - 0.001
        values << (distance / length)
        distance += spacing
      end

      values
    end

    def self.validate_i_section!(label, section)
      min_depth = [section[:start_depth], section[:end_depth]].min
      flange_width = section[:flange_width]
      web_thickness = section[:web_thickness]
      flange_thickness = section[:flange_thickness]

      raise "#{label} depth ต้องมากกว่า 2 x flange thickness" if min_depth <= (2.0 * flange_thickness)
      raise "#{label} flange width ต้องมากกว่า web thickness" if flange_width <= web_thickness
      raise "#{label} web thickness ต้องมากกว่า 0" if web_thickness <= 0
      raise "#{label} flange thickness ต้องมากกว่า 0" if flange_thickness <= 0
    end

    def self.validate_purlin_section!(section)
      type = section[:type]
      depth = section[:depth]
      flange_width = section[:flange_width]
      lip = section[:lip]
      thickness = section[:thickness]

      raise "Purlin type ต้องเป็น BOX, C หรือ Z" unless ["BOX", "C", "Z"].include?(type)
      raise "Purlin depth ต้องมากกว่า 2 x thickness" if depth <= (2.0 * thickness)
      raise "Purlin flange width ต้องมากกว่า thickness" if flange_width <= thickness
      raise "Purlin thickness ต้องมากกว่า 0" if thickness <= 0
      raise "Purlin lip ต้องไม่ติดลบ" if lip < 0
    end

    def self.validate_roof_brace_section!(section)
      profile = section[:profile]
      raise "Roof brace profile ต้องเป็น ROUND, BOX หรือ ANGLE" unless ["ROUND", "BOX", "ANGLE"].include?(profile)

      case profile
      when "ROUND"
        raise "Roof brace round diameter ต้องมากกว่า 0" if section[:diameter] <= 0
      when "BOX"
        raise "Roof brace box width ต้องมากกว่า 0" if section[:box_w] <= 0
        raise "Roof brace box height ต้องมากกว่า 0" if section[:box_h] <= 0
      when "ANGLE"
        raise "Roof brace angle leg ต้องมากกว่า thickness" if section[:angle_leg] <= section[:angle_thickness]
        raise "Roof brace angle thickness ต้องมากกว่า 0" if section[:angle_thickness] <= 0
      end
    end

    def self.validate_roof_brace_layout!(layout, max_spacing_m, left_x_per_bay, right_x_per_bay)
      raise "Roof brace layout ต้องเป็น AUTO หรือ COUNT" unless ["AUTO", "COUNT"].include?(layout)
      raise "Roof brace max bay spacing ต้องมากกว่า 0 m" if max_spacing_m <= 0
      raise "Roof brace left X per bay ต้องไม่ติดลบ" if left_x_per_bay < 0
      raise "Roof brace right X per bay ต้องไม่ติดลบ" if right_x_per_bay < 0
    end

    def self.roof_brace_bay_indices(bay_count, bay_spacing, requested_count, layout, max_spacing)
      count =
        if layout == "AUTO"
          total_length = bay_count * bay_spacing
          (total_length.to_m / max_spacing.to_m).ceil
        else
          requested_count.to_i
        end

      evenly_spaced_bay_indices(bay_count, count)
    end

    def self.evenly_spaced_bay_indices(bay_count, requested_count)
      count = [[requested_count.to_i, 0].max, bay_count].min
      return [] if count <= 0
      return [(bay_count - 1) / 2] if count == 1

      step = (bay_count - 1).to_f / (count - 1)
      indices = (0...count).map { |idx| (idx * step).round }
      indices.uniq
    end

    def self.add_roof_brace_x_set(root, f1_low, f1_high, f2_low, f2_high, x_count, section, name_prefix, solid_tag, centerline_tag, boq)
      count = x_count.to_i
      return if count <= 0

      count.times do |idx|
        t0 = idx.to_f / count
        t1 = (idx + 1).to_f / count

        p1_low = interp(f1_low, f1_high, t0)
        p1_high = interp(f1_low, f1_high, t1)
        p2_low = interp(f2_low, f2_high, t0)
        p2_high = interp(f2_low, f2_high, t1)
        set_no = idx + 1

        add_roof_brace_member(root, p1_low, p2_high,
                              section, "#{name_prefix}_X#{set_no}_A",
                              solid_tag, centerline_tag, boq)

        add_roof_brace_member(root, p1_high, p2_low,
                              section, "#{name_prefix}_X#{set_no}_B",
                              solid_tag, centerline_tag, boq)
      end
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

    def self.add_purlin_member(root, p1, p2, section, name, solid_tag, centerline_tag, boq, profile_width_axis)
      if section[:type] == "BOX"
        add_member(root, p1, p2, section[:flange_width], section[:depth],
                   name, solid_tag, centerline_tag, boq, profile_width_axis)
        return
      end

      ents = root.entities

      cl_group = ents.add_group
      cl_group.name = "CL_#{name}"
      cl_group.layer = centerline_tag
      cl_group.entities.add_line(p1, p2)

      g = ents.add_group
      g.name = name
      g.layer = solid_tag

      create_cz_purlin_along_line(g.entities, p1, p2, section, profile_width_axis)

      length = p1.distance(p2)
      area_m2 = cz_purlin_area_m2(section)
      volume_m3 = area_m2 * length.to_m
      weight_kg = volume_m3 * STEEL_DENSITY
      surface_m2 = cz_purlin_surface_m2(length, section)

      g.set_attribute("GOPEB", "name", name)
      g.set_attribute("GOPEB", "persistent_id", entity_persistent_id(g))
      g.set_attribute("GOPEB", "profile", "#{section[:type]} Purlin")
      g.set_attribute("GOPEB", "category", member_category(name))
      g.set_attribute("GOPEB", "section", purlin_section_label(section))
      g.set_attribute("GOPEB", "length_m", length.to_m)
      g.set_attribute("GOPEB", "depth_m", section[:depth].to_m)
      g.set_attribute("GOPEB", "flange_width_m", section[:flange_width].to_m)
      g.set_attribute("GOPEB", "lip_m", section[:lip].to_m)
      g.set_attribute("GOPEB", "thickness_m", section[:thickness].to_m)
      g.set_attribute("GOPEB", "volume_m3", volume_m3)
      g.set_attribute("GOPEB", "surface_m2", surface_m2)
      g.set_attribute("GOPEB", "weight_kg", weight_kg)

      boq << {
        name: name,
        persistent_id: entity_persistent_id(g),
        category: member_category(name),
        profile: "#{section[:type]} Purlin",
        section: purlin_section_label(section),
        length_m: length.to_m,
        depth_m: section[:depth].to_m,
        flange_width_m: section[:flange_width].to_m,
        lip_m: section[:lip].to_m,
        thickness_m: section[:thickness].to_m,
        volume_m3: volume_m3,
        surface_m2: surface_m2,
        weight_kg: weight_kg
      }
    end

    def self.add_roof_brace_member(root, p1, p2, section, name, solid_tag, centerline_tag, boq)
      if section[:profile] == "BOX"
        add_member(root, p1, p2, section[:box_w], section[:box_h],
                   name, solid_tag, centerline_tag, boq)
        return
      end

      ents = root.entities

      cl_group = ents.add_group
      cl_group.name = "CL_#{name}"
      cl_group.layer = centerline_tag
      cl_group.entities.add_line(p1, p2)

      g = ents.add_group
      g.name = name
      g.layer = solid_tag

      length = p1.distance(p2)

      case section[:profile]
      when "ROUND"
        create_round_bar_along_line(g.entities, p1, p2, section[:diameter])
        area_m2 = Math::PI * ((section[:diameter].to_m / 2.0) ** 2)
        surface_m2 = Math::PI * section[:diameter].to_m * length.to_m
      when "ANGLE"
        create_angle_along_line(g.entities, p1, p2, section[:angle_leg], section[:angle_thickness])
        area_m2 = angle_area_m2(section[:angle_leg], section[:angle_thickness])
        surface_m2 = angle_surface_m2(length, section[:angle_leg], section[:angle_thickness])
      end

      volume_m3 = area_m2 * length.to_m
      weight_kg = volume_m3 * STEEL_DENSITY

      g.set_attribute("GOPEB", "name", name)
      g.set_attribute("GOPEB", "persistent_id", entity_persistent_id(g))
      g.set_attribute("GOPEB", "category", member_category(name))
      g.set_attribute("GOPEB", "profile", roof_brace_profile_label(section))
      g.set_attribute("GOPEB", "section", roof_brace_section_label(section))
      g.set_attribute("GOPEB", "length_m", length.to_m)
      g.set_attribute("GOPEB", "volume_m3", volume_m3)
      g.set_attribute("GOPEB", "surface_m2", surface_m2)
      g.set_attribute("GOPEB", "weight_kg", weight_kg)

      boq << {
        name: name,
        persistent_id: entity_persistent_id(g),
        category: member_category(name),
        profile: roof_brace_profile_label(section),
        section: roof_brace_section_label(section),
        length_m: length.to_m,
        volume_m3: volume_m3,
        surface_m2: surface_m2,
        weight_kg: weight_kg
      }
    end

    def self.add_i_member(root, p1, p2, section, name, solid_tag, centerline_tag, boq, profile_width_axis = nil)
      ents = root.entities

      cl_group = ents.add_group
      cl_group.name = "CL_#{name}"
      cl_group.layer = centerline_tag
      cl_group.entities.add_line(p1, p2)

      g = ents.add_group
      g.name = name
      g.layer = solid_tag

      create_i_beam_along_line(g.entities, p1, p2, section, profile_width_axis)

      length = p1.distance(p2)
      start_area_m2 = i_section_area_m2(
        section[:start_depth],
        section[:flange_width],
        section[:web_thickness],
        section[:flange_thickness]
      )
      end_area_m2 = i_section_area_m2(
        section[:end_depth],
        section[:flange_width],
        section[:web_thickness],
        section[:flange_thickness]
      )
      volume_m3 = ((start_area_m2 + end_area_m2) / 2.0) * length.to_m
      weight_kg = volume_m3 * STEEL_DENSITY
      surface_m2 = i_section_tapered_surface_m2(length, section)

      g.set_attribute("GOPEB", "name", name)
      g.set_attribute("GOPEB", "persistent_id", entity_persistent_id(g))
      g.set_attribute("GOPEB", "profile", "I/H Beam")
      g.set_attribute("GOPEB", "category", member_category(name))
      g.set_attribute("GOPEB", "section", i_section_label(section))
      g.set_attribute("GOPEB", "length_m", length.to_m)
      g.set_attribute("GOPEB", "start_depth_m", section[:start_depth].to_m)
      g.set_attribute("GOPEB", "end_depth_m", section[:end_depth].to_m)
      g.set_attribute("GOPEB", "flange_width_m", section[:flange_width].to_m)
      g.set_attribute("GOPEB", "web_thickness_m", section[:web_thickness].to_m)
      g.set_attribute("GOPEB", "flange_thickness_m", section[:flange_thickness].to_m)
      g.set_attribute("GOPEB", "volume_m3", volume_m3)
      g.set_attribute("GOPEB", "surface_m2", surface_m2)
      g.set_attribute("GOPEB", "weight_kg", weight_kg)

      boq << {
        name: name,
        persistent_id: entity_persistent_id(g),
        category: member_category(name),
        profile: "I/H Beam",
        section: i_section_label(section),
        length_m: length.to_m,
        start_depth_m: section[:start_depth].to_m,
        end_depth_m: section[:end_depth].to_m,
        flange_width_m: section[:flange_width].to_m,
        web_thickness_m: section[:web_thickness].to_m,
        flange_thickness_m: section[:flange_thickness].to_m,
        volume_m3: volume_m3,
        surface_m2: surface_m2,
        weight_kg: weight_kg
      }
    end

    def self.add_member(root, p1, p2, w, h, name, solid_tag, centerline_tag, boq, profile_width_axis = nil, end_w = nil, end_h = nil)
      ents = root.entities
      end_w ||= w
      end_h ||= h

      cl_group = ents.add_group
      cl_group.name = "CL_#{name}"
      cl_group.layer = centerline_tag
      cl_group.entities.add_line(p1, p2)

      g = ents.add_group
      g.name = name
      g.layer = solid_tag

      create_box_along_line(g.entities, p1, p2, w, h, end_w, end_h, profile_width_axis)

      length = p1.distance(p2)

      volume_m3 = tapered_volume_m3(length, w, h, end_w, end_h)
      weight_kg = volume_m3 * STEEL_DENSITY
      surface_m2 = tapered_surface_m2(length, w, h, end_w, end_h)

      g.set_attribute("GOPEB", "name", name)
      g.set_attribute("GOPEB", "persistent_id", entity_persistent_id(g))
      g.set_attribute("GOPEB", "category", member_category(name))
      g.set_attribute("GOPEB", "profile", box_profile_label(name))
      g.set_attribute("GOPEB", "section", box_section_label(w, h, end_w, end_h))
      g.set_attribute("GOPEB", "length_m", length.to_m)
      g.set_attribute("GOPEB", "start_width_m", w.to_m)
      g.set_attribute("GOPEB", "start_height_m", h.to_m)
      g.set_attribute("GOPEB", "end_width_m", end_w.to_m)
      g.set_attribute("GOPEB", "end_height_m", end_h.to_m)
      g.set_attribute("GOPEB", "volume_m3", volume_m3)
      g.set_attribute("GOPEB", "surface_m2", surface_m2)
      g.set_attribute("GOPEB", "weight_kg", weight_kg)

      boq << {
        name: name,
        persistent_id: entity_persistent_id(g),
        category: member_category(name),
        profile: box_profile_label(name),
        section: box_section_label(w, h, end_w, end_h),
        length_m: length.to_m,
        start_width_m: w.to_m,
        start_height_m: h.to_m,
        end_width_m: end_w.to_m,
        end_height_m: end_h.to_m,
        volume_m3: volume_m3,
        surface_m2: surface_m2,
        weight_kg: weight_kg
      }
    end

    def self.create_box_along_line(entities, p1, p2, w1, h1, w2 = nil, h2 = nil, profile_width_axis = nil)
      vec = p2 - p1
      return if vec.length < 0.001
      w2 ||= w1
      h2 ||= h1

      x_axis = vec.clone
      x_axis.normalize!

      y_axis = profile_y_axis(x_axis, profile_width_axis)
      z_axis = x_axis.cross(y_axis)

      if profile_width_axis && z_axis.z < -0.001
        y_axis = Geom::Vector3d.new(-y_axis.x, -y_axis.y, -y_axis.z)
        z_axis = x_axis.cross(y_axis)
      end

      z_axis.normalize!
      create_box_along_axes(entities, p1, p2, y_axis, z_axis, w1, h1, w2, h2)
    end

    def self.create_box_along_axes(entities, p1, p2, y_axis, z_axis, w1, h1, w2 = nil, h2 = nil)
      w2 ||= w1
      h2 ||= h1
      hw1 = w1 / 2.0
      hh1 = h1 / 2.0
      hw2 = w2 / 2.0
      hh2 = h2 / 2.0

      a = p1.offset(y_axis, -hw1).offset(z_axis, -hh1)
      b = p1.offset(y_axis,  hw1).offset(z_axis, -hh1)
      c = p1.offset(y_axis,  hw1).offset(z_axis,  hh1)
      d = p1.offset(y_axis, -hw1).offset(z_axis,  hh1)

      e = p2.offset(y_axis, -hw2).offset(z_axis, -hh2)
      f = p2.offset(y_axis,  hw2).offset(z_axis, -hh2)
      g = p2.offset(y_axis,  hw2).offset(z_axis,  hh2)
      h2_point = p2.offset(y_axis, -hw2).offset(z_axis,  hh2)

      solid_center = average_point([a, b, c, d, e, f, g, h2_point])

      faces = []
      faces << add_oriented_face(entities, [a, d, c, b], solid_center)
      faces << add_oriented_face(entities, [e, f, g, h2_point], solid_center)
      faces << add_oriented_face(entities, [a, b, f, e], solid_center)
      faces << add_oriented_face(entities, [b, c, g, f], solid_center)
      faces << add_oriented_face(entities, [c, d, h2_point, g], solid_center)
      faces << add_oriented_face(entities, [d, a, e, h2_point], solid_center)

      faces.compact.each do |face|
        face.material = nil
        face.back_material = nil
      end
    end

    def self.create_i_beam_along_line(entities, p1, p2, section, profile_width_axis = nil)
      vec = p2 - p1
      return if vec.length < 0.001

      x_axis = vec.clone
      x_axis.normalize!

      y_axis = profile_y_axis(x_axis, profile_width_axis)
      z_axis = x_axis.cross(y_axis)
      z_axis.normalize!

      start_points = i_section_points(
        p1,
        y_axis,
        z_axis,
        section[:start_depth],
        section[:flange_width],
        section[:web_thickness],
        section[:flange_thickness]
      )
      end_points = i_section_points(
        p2,
        y_axis,
        z_axis,
        section[:end_depth],
        section[:flange_width],
        section[:web_thickness],
        section[:flange_thickness]
      )

      faces = []
      faces << add_clean_face(entities, start_points.reverse)
      faces << add_clean_face(entities, end_points)

      start_points.each_index do |idx|
        next_idx = (idx + 1) % start_points.length
        faces << add_clean_face(
          entities,
          [start_points[idx], start_points[next_idx], end_points[next_idx], end_points[idx]]
        )
      end

      faces.compact.each do |face|
        face.material = nil
        face.back_material = nil
      end
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
      flange_width = section[:flange_width]
      lip = section[:lip]
      thickness = section[:thickness]
      top_sign = 1.0
      bottom_sign = section[:type] == "Z" ? -1.0 : 1.0

      create_box_along_axes(
        entities, p1, p2, y_axis, z_axis,
        thickness, depth, thickness, depth
      )

      top_start = p1.offset(z_axis, (depth / 2.0) - (thickness / 2.0)).offset(y_axis, top_sign * (flange_width / 2.0))
      top_end = p2.offset(z_axis, (depth / 2.0) - (thickness / 2.0)).offset(y_axis, top_sign * (flange_width / 2.0))
      create_box_along_axes(
        entities, top_start, top_end, y_axis, z_axis,
        flange_width, thickness, flange_width, thickness
      )

      bottom_start = p1.offset(z_axis, (-depth / 2.0) + (thickness / 2.0)).offset(y_axis, bottom_sign * (flange_width / 2.0))
      bottom_end = p2.offset(z_axis, (-depth / 2.0) + (thickness / 2.0)).offset(y_axis, bottom_sign * (flange_width / 2.0))
      create_box_along_axes(
        entities, bottom_start, bottom_end, y_axis, z_axis,
        flange_width, thickness, flange_width, thickness
      )

      return if lip <= 0

      top_lip_start = p1.offset(z_axis, (depth / 2.0) - thickness - (lip / 2.0)).offset(y_axis, top_sign * (flange_width - (thickness / 2.0)))
      top_lip_end = p2.offset(z_axis, (depth / 2.0) - thickness - (lip / 2.0)).offset(y_axis, top_sign * (flange_width - (thickness / 2.0)))
      create_box_along_axes(
        entities, top_lip_start, top_lip_end, y_axis, z_axis,
        thickness, lip, thickness, lip
      )

      bottom_lip_start = p1.offset(z_axis, (-depth / 2.0) + thickness + (lip / 2.0)).offset(y_axis, bottom_sign * (flange_width - (thickness / 2.0)))
      bottom_lip_end = p2.offset(z_axis, (-depth / 2.0) + thickness + (lip / 2.0)).offset(y_axis, bottom_sign * (flange_width - (thickness / 2.0)))
      create_box_along_axes(
        entities, bottom_lip_start, bottom_lip_end, y_axis, z_axis,
        thickness, lip, thickness, lip
      )
    end

    def self.create_round_bar_along_line(entities, p1, p2, diameter, segments = 16)
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
        offset_y = Math.cos(angle) * radius
        offset_z = Math.sin(angle) * radius
        start_points << p1.offset(y_axis, offset_y).offset(z_axis, offset_z)
        end_points << p2.offset(y_axis, offset_y).offset(z_axis, offset_z)
      end

      solid_center = average_point(start_points + end_points)
      faces = []
      faces << add_oriented_face(entities, start_points.reverse, solid_center)
      faces << add_oriented_face(entities, end_points, solid_center)

      segments.times do |idx|
        next_idx = (idx + 1) % segments
        faces << add_oriented_face(
          entities,
          [start_points[idx], start_points[next_idx], end_points[next_idx], end_points[idx]],
          solid_center
        )
      end

      faces.compact.each do |face|
        face.material = nil
        face.back_material = nil
      end
    end

    def self.create_angle_along_line(entities, p1, p2, leg, thickness)
      vec = p2 - p1
      return if vec.length < 0.001

      x_axis = vec.clone
      x_axis.normalize!
      y_axis = profile_y_axis(x_axis, nil)
      z_axis = x_axis.cross(y_axis)
      z_axis.normalize!

      first_leg_start = p1.offset(y_axis, (leg / 2.0) - (thickness / 2.0))
      first_leg_end = p2.offset(y_axis, (leg / 2.0) - (thickness / 2.0))
      create_box_along_axes(
        entities, first_leg_start, first_leg_end, y_axis, z_axis,
        leg, thickness, leg, thickness
      )

      second_leg_start = p1.offset(z_axis, (leg / 2.0) - (thickness / 2.0))
      second_leg_end = p2.offset(z_axis, (leg / 2.0) - (thickness / 2.0))
      create_box_along_axes(
        entities, second_leg_start, second_leg_end, y_axis, z_axis,
        thickness, leg, thickness, leg
      )
    end

    def self.i_section_points(base, y_axis, z_axis, depth, flange_width, web_thickness, flange_thickness)
      half_b = flange_width / 2.0
      half_tw = web_thickness / 2.0
      half_d = depth / 2.0
      tf = flange_thickness

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

      coords.map do |y, z|
        base.offset(y_axis, y).offset(z_axis, z)
      end
    end

    def self.i_section_area_m2(depth, flange_width, web_thickness, flange_thickness)
      d = depth.to_m
      b = flange_width.to_m
      tw = web_thickness.to_m
      tf = flange_thickness.to_m

      (2.0 * b * tf) + (tw * (d - (2.0 * tf)))
    end

    def self.i_section_perimeter_m(depth, flange_width, web_thickness)
      d = depth.to_m
      b = flange_width.to_m
      tw = web_thickness.to_m

      (4.0 * b) + (2.0 * d) - (2.0 * tw)
    end

    def self.i_section_tapered_surface_m2(length, section)
      start_perimeter = i_section_perimeter_m(
        section[:start_depth],
        section[:flange_width],
        section[:web_thickness]
      )
      end_perimeter = i_section_perimeter_m(
        section[:end_depth],
        section[:flange_width],
        section[:web_thickness]
      )

      ((start_perimeter + end_perimeter) / 2.0) * length.to_m
    end

    def self.cz_purlin_area_m2(section)
      t = section[:thickness].to_m
      strip_width = section[:depth].to_m +
                    (2.0 * section[:flange_width].to_m) +
                    (2.0 * section[:lip].to_m)

      t * strip_width
    end

    def self.cz_purlin_surface_m2(length, section)
      strip_width = section[:depth].to_m +
                    (2.0 * section[:flange_width].to_m) +
                    (2.0 * section[:lip].to_m)

      2.0 * strip_width * length.to_m
    end

    def self.angle_area_m2(leg, thickness)
      l = leg.to_m
      t = thickness.to_m
      (2.0 * l * t) - (t * t)
    end

    def self.angle_surface_m2(length, leg, thickness)
      l = leg.to_m
      t = thickness.to_m
      perimeter = 4.0 * l
      area = perimeter * length.to_m
      area -= 2.0 * t * length.to_m
      area
    end

    def self.member_category(name)
      case name
      when /^Brace_Roof/
        "Roof Bracing"
      when /^Brace_Wall/
        "Wall Bracing"
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
      when /^Base_Tie/
        "Base Tie"
      when /^Brace/
        "Bracing"
      else
        "Other"
      end
    end

    def self.box_profile_label(name)
      if name.start_with?("Purlin", "Eave_Strut", "Ridge")
        "BOX Purlin"
      elsif name.start_with?("Brace_Roof")
        "BOX Roof Brace"
      else
        "Rectangular Box"
      end
    end

    def self.i_section_label(section)
      "I/H D#{dim_mm(section[:start_depth])}-#{dim_mm(section[:end_depth])} " \
        "B#{dim_mm(section[:flange_width])} tw#{dim_mm(section[:web_thickness])} " \
        "tf#{dim_mm(section[:flange_thickness])}"
    end

    def self.purlin_section_label(section)
      "#{section[:type]} D#{dim_mm(section[:depth])} B#{dim_mm(section[:flange_width])} " \
        "L#{dim_mm(section[:lip])} t#{dim_mm(section[:thickness])}"
    end

    def self.box_section_label(w, h, end_w, end_h)
      start_label = "#{dim_mm(w)}x#{dim_mm(h)}"
      end_label = "#{dim_mm(end_w)}x#{dim_mm(end_h)}"

      if start_label == end_label
        "BOX #{start_label}"
      else
        "TAPERED BOX #{start_label}-#{end_label}"
      end
    end

    def self.roof_brace_profile_label(section)
      case section[:profile]
      when "ROUND"
        "Round Bar"
      when "ANGLE"
        "Angle"
      when "BOX"
        "BOX Roof Brace"
      end
    end

    def self.roof_brace_section_label(section)
      case section[:profile]
      when "ROUND"
        "RB#{dim_mm(section[:diameter])}"
      when "ANGLE"
        "L#{dim_mm(section[:angle_leg])}x#{dim_mm(section[:angle_leg])}x#{dim_mm(section[:angle_thickness])}"
      when "BOX"
        "BOX #{dim_mm(section[:box_w])}x#{dim_mm(section[:box_h])}"
      end
    end

    def self.dim_mm(length)
      value = length.to_mm
      rounded = value.round(2)
      rounded == rounded.to_i ? rounded.to_i.to_s : rounded.to_s
    end

    def self.entity_persistent_id(entity)
      entity.respond_to?(:persistent_id) ? entity.persistent_id : nil
    end

    def self.tapered_volume_m3(length, w1, h1, w2, h2)
      l = length.to_m
      start_w = w1.to_m
      start_h = h1.to_m
      delta_w = w2.to_m - start_w
      delta_h = h2.to_m - start_h

      l * (
        (start_w * start_h) +
        ((start_w * delta_h + start_h * delta_w) / 2.0) +
        ((delta_w * delta_h) / 3.0)
      )
    end

    def self.tapered_surface_m2(length, w1, h1, w2, h2)
      l = length.to_m
      start_w = w1.to_m
      start_h = h1.to_m
      end_w = w2.to_m
      end_h = h2.to_m

      width_face_len = Math.sqrt((l * l) + (((end_h - start_h) / 2.0) ** 2))
      height_face_len = Math.sqrt((l * l) + (((end_w - start_w) / 2.0) ** 2))

      2.0 * (
        (((start_w + end_w) / 2.0) * width_face_len) +
        (((start_h + end_h) / 2.0) * height_face_len)
      )
    end

    def self.add_oriented_face(entities, points, solid_center)
      face = entities.add_face(points)
      return nil unless face

      face_center = average_point(face.vertices.map { |vertex| vertex.position })
      outward = face_center - solid_center
      face.reverse! if outward.length > 0.001 && face.normal.dot(outward) < 0
      face
    end

    def self.add_clean_face(entities, points)
      face = entities.add_face(points)
      return nil unless face

      face.material = nil
      face.back_material = nil
      face
    end

    def self.average_point(points)
      count = points.length.to_f
      Geom::Point3d.new(
        points.sum { |point| point.x } / count,
        points.sum { |point| point.y } / count,
        points.sum { |point| point.z } / count
      )
    end

    def self.profile_y_axis(x_axis, preferred_axis)
      if preferred_axis
        y_axis = preferred_axis.clone
        dot = y_axis.dot(x_axis)
        projection = Geom::Vector3d.new(
          x_axis.x * dot,
          x_axis.y * dot,
          x_axis.z * dot
        )
        y_axis = y_axis - projection
      else
        global_z = Geom::Vector3d.new(0, 0, 1)
        y_axis = global_z.cross(x_axis)
      end

      if y_axis.length < 0.001
        y_axis = Geom::Vector3d.new(1, 0, 0)
      end

      y_axis.normalize!
      y_axis
    end

    def self.create_boq_report(model, boq)
      total_len = boq.sum { |x| x[:length_m] }
      total_area = boq.sum { |x| x[:surface_m2] }
      total_volume = boq.sum { |x| x[:volume_m3] }
      total_weight = boq.sum { |x| x[:weight_kg] }
      grouped = boq_group_totals(boq)

      text = "PEB BOQ SUMMARY\n"
      text += "Total Members: #{boq.length}\n"
      text += "Total Length: #{total_len.round(2)} m\n"
      text += "Surface Area: #{total_area.round(2)} m2\n"
      text += "Steel Volume: #{total_volume.round(4)} m3\n"
      text += "Steel Weight: #{total_weight.round(2)} kg\n"
      text += "\nBOQ BY STEEL TYPE\n"
      text += "Category | Profile | Section | Qty | Len(m) | Area(m2) | Vol(m3) | Wt(kg) | kg/m\n"

      grouped.each do |row|
        kg_per_m = row[:length_m] > 0 ? row[:weight_kg] / row[:length_m] : 0
        text += "#{row[:category]} | #{row[:profile]} | #{row[:section]} | " \
                "#{row[:qty]} | #{row[:length_m].round(2)} | #{row[:surface_m2].round(2)} | " \
                "#{row[:volume_m3].round(4)} | #{row[:weight_kg].round(2)} | #{kg_per_m.round(2)}\n"
      end

      text += "\nMEMBER DETAILS\n"
      text += "Name | Category | Section | Len(m) | Vol(m3) | Wt(kg)\n"
      boq.each do |item|
        text += "#{item[:name]} | #{item[:category]} | #{item[:section]} | " \
                "#{item[:length_m].round(2)} | #{item[:volume_m3].round(4)} | #{item[:weight_kg].round(2)}\n"
      end

      model.set_attribute("GOPEB", "boq_report", text)
      model.set_attribute("GOPEB", "boq_json", JSON.generate(boq_dialog_payload(boq, grouped)))
      @last_boq = boq
      @last_grouped = grouped
      @last_boq_summary = {
        members: boq.length,
        length_m: total_len,
        surface_m2: total_area,
        volume_m3: total_volume,
        weight_kg: total_weight
      }
      puts text
    end

    def self.show_boq_dialog
      raw = Sketchup.active_model.get_attribute("GOPEB", "boq_json")
      return unless raw
      payload = JSON.parse(raw)
      @last_boq = symbolize_deep(payload["items"] || []) if !@last_boq || @last_boq.empty?
      @last_grouped = symbolize_deep(payload["grouped"] || []) if !@last_grouped || @last_grouped.empty?

      dialog = UI::HtmlDialog.new(
        dialog_title: "GO PEB BOQ",
        preferences_key: "gopeb.boq",
        scrollable: true,
        resizable: true,
        width: 1040,
        height: 720,
        style: UI::HtmlDialog::STYLE_DIALOG
      )

      dialog.add_action_callback("exportBoq") do |_context, _payload_json|
        path = write_boq_csv(Sketchup.active_model, @last_boq || [], @last_grouped || [])
        message = path ? "Exported: #{path}" : "Export failed"
        dialog.execute_script("window.gopebBoqStatus(#{JSON.generate(message)})")
      end

      dialog.add_action_callback("selectMember") do |_context, payload_json|
        data = JSON.parse(payload_json)
        select_entity_by_persistent_id(data["persistent_id"].to_i)
      rescue => e
        dialog.execute_script("window.gopebBoqStatus(#{JSON.generate(e.message)})")
      end

      dialog.set_html(boq_dialog_html(payload))
      dialog.show
    rescue => e
      UI.messagebox("BOQ Dialog Error: #{e.message}")
      puts e.backtrace
    end

    def self.boq_dialog_html(payload)
      render_template(
        "boq_dialog.html",
        "TITLE" => "GO PEB BOQ",
        "SUBTITLE" => "Grouped steel quantities and member details.",
        "MODE" => "pro",
        "BOQ_JSON" => JSON.generate(payload)
      )
    end

    def self.boq_dialog_payload(boq, grouped)
      {
        summary: {
          members: boq.length,
          length_m: boq.sum { |x| x[:length_m] },
          surface_m2: boq.sum { |x| x[:surface_m2] },
          volume_m3: boq.sum { |x| x[:volume_m3] },
          weight_kg: boq.sum { |x| x[:weight_kg] }
        },
        grouped: grouped,
        items: boq
      }
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

    def self.select_entity_by_persistent_id(persistent_id)
      model = Sketchup.active_model
      entity = if model.respond_to?(:find_entity_by_persistent_id)
                 model.find_entity_by_persistent_id(persistent_id)
               end
      raise "Member not found in model" unless entity

      model.selection.clear
      model.selection.add(entity)
    end

    def self.boq_group_totals(boq)
      grouped = {}

      boq.each do |item|
        key = [item[:category], item[:profile], item[:section]]
        grouped[key] ||= {
          category: item[:category],
          profile: item[:profile],
          section: item[:section],
          qty: 0,
          length_m: 0.0,
          surface_m2: 0.0,
          volume_m3: 0.0,
          weight_kg: 0.0
        }

        row = grouped[key]
        row[:qty] += 1
        row[:length_m] += item[:length_m]
        row[:surface_m2] += item[:surface_m2]
        row[:volume_m3] += item[:volume_m3]
        row[:weight_kg] += item[:weight_kg]
      end

      grouped.values.sort_by { |row| [row[:category], row[:profile], row[:section]] }
    end

    def self.write_boq_csv(model, boq, grouped)
      folder = boq_output_folder(model)
      return nil unless folder && File.directory?(folder)

      path = File.join(folder, "gopeb_boq_#{Time.now.strftime('%Y%m%d_%H%M%S')}.csv")

      File.open(path, "w") do |file|
        file.puts csv_row(["GO PEB BOQ SUMMARY"])
        file.puts csv_row(["Total Members", boq.length])
        file.puts csv_row(["Total Length (m)", boq.sum { |x| x[:length_m] }.round(3)])
        file.puts csv_row(["Total Surface Area (m2)", boq.sum { |x| x[:surface_m2] }.round(3)])
        file.puts csv_row(["Total Volume (m3)", boq.sum { |x| x[:volume_m3] }.round(5)])
        file.puts csv_row(["Total Weight (kg)", boq.sum { |x| x[:weight_kg] }.round(3)])
        file.puts

        file.puts csv_row(["BOQ BY STEEL TYPE"])
        file.puts csv_row(["Category", "Profile", "Section", "Qty", "Length (m)", "Surface Area (m2)", "Volume (m3)", "Weight (kg)", "kg/m"])
        grouped.each do |row|
          kg_per_m = row[:length_m] > 0 ? row[:weight_kg] / row[:length_m] : 0
          file.puts csv_row([
            row[:category],
            row[:profile],
            row[:section],
            row[:qty],
            row[:length_m].round(3),
            row[:surface_m2].round(3),
            row[:volume_m3].round(5),
            row[:weight_kg].round(3),
            kg_per_m.round(3)
          ])
        end
        file.puts

        file.puts csv_row(["MEMBER DETAILS"])
        file.puts csv_row(["Name", "Category", "Profile", "Section", "Length (m)", "Surface Area (m2)", "Volume (m3)", "Weight (kg)"])
        boq.each do |item|
          file.puts csv_row([
            item[:name],
            item[:category],
            item[:profile],
            item[:section],
            item[:length_m].round(3),
            item[:surface_m2].round(3),
            item[:volume_m3].round(5),
            item[:weight_kg].round(3)
          ])
        end
      end

      path
    rescue => e
      puts "BOQ CSV export failed: #{e.message}"
      nil
    end

    def self.boq_output_folder(model)
      if model.path && !model.path.empty?
        File.dirname(model.path)
      else
        desktop = File.join(ENV["USERPROFILE"].to_s, "Desktop")
        File.directory?(desktop) ? desktop : Dir.tmpdir
      end
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

    unless file_loaded?(__FILE__)
      menu = UI.menu("Plugins").add_submenu("GO PEB")
      menu.add_item("Create PEB Generator") {
        self.run
      }
      menu.add_item("Show Last BOQ") {
        self.show_boq_dialog
      }
      file_loaded(__FILE__)
    end

  end
end

GOPEB::Generator.run

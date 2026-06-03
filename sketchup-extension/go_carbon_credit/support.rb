# frozen_string_literal: true
# --------------------------------------------------------------------------
# GO Carbon Credit — Support (Shared Utility Helpers)
# ฟังก์ชันช่วยเหลือทั่วไป — ไม่มี dependency กับโมดูลอื่น
# Self-contained utilities used by Scanner, Matcher, and Report modules.
# --------------------------------------------------------------------------

require 'csv'

module GOCarbonCredit
  module Support
    extend self

    # ================================================================
    # Basic helpers / ฟังก์ชันพื้นฐาน
    # ================================================================

    # Safe round — returns nil when value is nil.
    # ปัดเศษอย่างปลอดภัย — คืน nil ถ้าค่าเป็น nil
    # @param value [Numeric, nil]
    # @param digits [Integer] number of decimal places
    # @return [Float, nil]
    def round(value, digits = 2)
      return nil if value.nil?
      value.round(digits)
    end

    # Check if value is nil or empty string.
    # ตรวจสอบว่าค่าเป็น nil หรือ string ว่าง
    # @param value [Object, nil]
    # @return [Boolean]
    def blank?(value)
      value.nil? || (value.is_a?(String) && value.strip.empty?)
    end

    # ================================================================
    # Entity attribute helpers / ดึงข้อมูลจาก Entity
    # ================================================================

    # Get entity instance name; fall back to definition name.
    # ดึงชื่อ entity — ถ้าไม่มีใช้ชื่อ definition แทน
    # @param entity [Sketchup::ComponentInstance, Sketchup::Group]
    # @return [String]
    def entity_name(entity)
      name = entity.respond_to?(:name) ? entity.name.to_s.strip : ''
      return name unless name.empty?
      definition_name(entity)
    end

    # Get the definition name of a component/group.
    # ดึงชื่อ definition ของ component/group
    # @param entity [Sketchup::ComponentInstance, Sketchup::Group]
    # @return [String]
    def definition_name(entity)
      if entity.respond_to?(:definition)
        entity.definition.name.to_s.strip
      else
        ''
      end
    end

    # Get layer/tag name. Default 'Untagged' (Layer0).
    # ดึงชื่อ Tag (Layer) — ค่าเริ่มต้น 'Untagged'
    # @param entity [Sketchup::Drawingelement]
    # @return [String]
    def entity_tag(entity)
      return 'Untagged' unless entity.respond_to?(:layer)
      tag = entity.layer
      return 'Untagged' if tag.nil?
      name = tag.name.to_s.strip
      (name.empty? || name == 'Layer0') ? 'Untagged' : name
    end

    # Get material display name safely.
    # ดึงชื่อวัสดุอย่างปลอดภัย
    # @param entity [Sketchup::Drawingelement]
    # @return [String]
    def entity_material(entity)
      return '' unless entity.respond_to?(:material)
      mat = entity.material
      return '' if mat.nil?
      mat.display_name.to_s.strip
    end

    # Human-readable label: name or "Type-EntityID" fallback.
    # ชื่อที่อ่านง่าย: ใช้ชื่อ entity หรือ "ประเภท-ID"
    # @param entity [Sketchup::Drawingelement]
    # @return [String]
    def entity_label(entity)
      name = entity_name(entity)
      return name unless name.empty?
      type = entity.is_a?(Sketchup::Group) ? 'Group' : 'Component'
      "#{type}-#{entity.entityID}"
    end

    # ================================================================
    # Geometry helpers / ฟังก์ชันเรขาคณิต
    # ================================================================

    # Volume in cubic inches. Returns nil if entity is not solid.
    # ปริมาตรเป็น cubic inches — คืน nil ถ้าไม่ใช่ solid
    # @param entity [Sketchup::ComponentInstance, Sketchup::Group]
    # @return [Float, nil]
    def entity_volume(entity)
      return nil unless entity.respond_to?(:volume)
      vol = entity.volume rescue nil
      return nil if vol.nil? || vol <= 0
      vol
    end

    # Total face area of an entity in square meters.
    # Recursively sums Face areas through nested Groups/Components.
    # พื้นที่ผิวรวมเป็นตารางเมตร (คำนวณแบบ recursive)
    # @param entity [Sketchup::ComponentInstance, Sketchup::Group]
    # @return [Float]
    def entity_surface_area(entity)
      return 0.0 unless entity.respond_to?(:definition) || entity.respond_to?(:entities)
      ents = entity.respond_to?(:definition) ? entity.definition.entities : entity.entities
      xform = entity.respond_to?(:transformation) ? entity.transformation : nil
      area_sq_in = entities_surface_area(ents, xform)
      area_sq_in * SQ_INCH_TO_M2
    end

    # Recursive surface area helper (returns area in square inches).
    # ฟังก์ชันช่วยคำนวณพื้นที่ผิวแบบ recursive (คืนค่าเป็น square inches)
    # @param entities [Sketchup::Entities]
    # @param transformation [Geom::Transformation, nil]
    # @return [Float]
    def entities_surface_area(entities, transformation)
      total = 0.0
      entities.each do |e|
        case e
        when Sketchup::Face
          # Face#area returns area in square inches in local coords.
          # Apply transformation scale if present.
          if transformation
            # Transform each vertex and compute polygon area
            pts = e.outer_loop.vertices.map { |v| v.position.transform(transformation) }
            total += polygon_area(pts)
          else
            total += e.area
          end
        when Sketchup::Group
          child_xform = transformation ? (transformation * e.transformation) : e.transformation
          total += entities_surface_area(e.entities, child_xform)
        when Sketchup::ComponentInstance
          child_xform = transformation ? (transformation * e.transformation) : e.transformation
          total += entities_surface_area(e.definition.entities, child_xform)
        end
      end
      total
    end

    # Compute polygon area from array of Point3d using cross-product.
    # คำนวณพื้นที่ polygon จากจุดต่าง ๆ ด้วย cross-product
    # @param pts [Array<Geom::Point3d>]
    # @return [Float]
    def polygon_area(pts)
      return 0.0 if pts.length < 3
      sum = Geom::Vector3d.new(0, 0, 0)
      pts.each_with_index do |_p, i|
        j = (i + 1) % pts.length
        cross = pts[i].vector_to(Geom::Point3d.new(0, 0, 0)).reverse.cross(
          pts[j].vector_to(Geom::Point3d.new(0, 0, 0)).reverse
        )
        sum = Geom::Vector3d.new(sum.x + cross.x, sum.y + cross.y, sum.z + cross.z)
      end
      0.5 * Math.sqrt(sum.x**2 + sum.y**2 + sum.z**2)
    end

    # Return sorted bounding box dimensions [longest, middle, shortest] in inches.
    # คืนค่ามิติกรอบ [ยาว, กลาง, สั้น] เป็นนิ้ว
    # @param bounds [Geom::BoundingBox]
    # @return [Array<Float>]
    def sorted_dimensions(bounds)
      dims = [bounds.width.to_f, bounds.height.to_f, bounds.depth.to_f]
      dims.sort.reverse
    end

    # ================================================================
    # Density inference / อนุมานค่าความหนาแน่น
    # ================================================================

    # Auto-detect density (kg/m³) from material, tag, name, or definition.
    # ตรวจจับความหนาแน่นอัตโนมัติจากวัสดุ แท็ก ชื่อ
    # @param entity [Sketchup::ComponentInstance, Sketchup::Group]
    # @return [Integer, nil]
    def infer_density(entity)
      text = [
        entity_material(entity),
        entity_tag(entity),
        entity_name(entity),
        definition_name(entity)
      ].join(' ').downcase

      case text
      when /steel|เหล็ก/
        DENSITY_PRESETS['steel']
      when /\brc\b|reinforced|concrete|beam|column|footing|คาน|เสา|ฐานราก/
        DENSITY_PRESETS['reinforced_concrete']
      when /timber|wood|ไม้/
        DENSITY_PRESETS['timber']
      when /alumin|อลูมิเนียม/
        DENSITY_PRESETS['aluminum']
      when /masonry|brick|อิฐ|ก่อ/
        DENSITY_PRESETS['masonry']
      when /concrete|คอนกรีต/
        DENSITY_PRESETS['concrete']
      else
        nil
      end
    end

    # ================================================================
    # CSV / Emission Factor parsing
    # การอ่านไฟล์ CSV สำหรับ Emission Factor
    # ================================================================

    # Parse an Emission Factor CSV file.
    # อ่านไฟล์ CSV ของ Emission Factor แล้วคืนค่าเป็น array ของ rule hashes
    # @param path [String] absolute file path
    # @param source [String] source label (e.g. 'built-in', 'project')
    # @param source_priority [Integer] priority of this source
    # @return [Array<Hash>]
    def parse_ef_csv(path, source, source_priority)
      return [] unless File.exist?(path)

      raw = File.read(path, encoding: 'bom|utf-8')
      # Strip UTF-8 BOM if still present
      raw.sub!("\xEF\xBB\xBF", '')
      raw.force_encoding('UTF-8')

      rules = []
      csv = CSV.parse(raw, headers: true, skip_blanks: true)
      csv.each do |row|
        next if row.to_h.values.all?(&:nil?)
        rule = normalize_ef_rule(row.to_h, source, source_priority)
        rules << rule unless rule.nil?
      end
      rules
    end

    # Normalize a raw CSV row hash into a clean rule hash.
    # แปลงข้อมูล CSV row ให้เป็น rule hash ที่สะอาด
    # @param raw [Hash] raw CSV row
    # @param source [String]
    # @param source_priority [Integer]
    # @return [Hash, nil]
    def normalize_ef_rule(raw, source, source_priority)
      return nil if raw.nil?

      ef_id = (raw['ef_id'] || '').to_s.strip
      return nil if ef_id.empty?

      {
        'enabled'         => (raw['enabled'] || 'true').to_s.strip.downcase,
        'priority'        => (raw['priority'] || '0').to_s.strip.to_i,
        'ef_id'           => ef_id,
        'match_type'      => (raw['match_type'] || 'keyword').to_s.strip.downcase,
        'match_value'     => (raw['match_value'] || '').to_s.strip,
        'material_name_th'=> (raw['material_name_th'] || '').to_s.strip,
        'ef_value'        => (raw['ef_value'] || '0').to_s.strip.to_f,
        'ef_unit'         => (raw['ef_unit'] || '').to_s.strip,
        'quantity_source'  => (raw['quantity_source'] || 'volumeM3').to_s.strip,
        'data_source'     => (raw['data_source'] || '').to_s.strip,
        'note'            => (raw['note'] || '').to_s.strip,
        'source'          => source.to_s,
        'sourcePriority'  => source_priority.to_i
      }
    end

    # De-duplicate rules: sort by sourcePriority desc, then priority desc.
    # Keep first occurrence of each ef_id.
    # ลบ rule ซ้ำ: เรียงตาม sourcePriority และ priority จากมากไปน้อย
    # @param rules [Array<Hash>]
    # @return [Array<Hash>]
    def deduplicate_rules(rules)
      sorted = rules.sort_by { |r| [-(r['sourcePriority'] || 0), -(r['priority'] || 0)] }
      seen = {}
      sorted.select do |r|
        id = r['ef_id']
        if seen[id]
          false
        else
          seen[id] = true
          true
        end
      end
    end

    # Join key fields of a record for keyword search haystack.
    # รวมฟิลด์หลักของ record เพื่อใช้ค้นหาด้วย keyword
    # @param record [Hash]
    # @return [String]
    def haystack(record)
      [
        record['name'],
        record['definitionName'],
        record['tag'],
        record['material'],
        record['category']
      ].compact.join(' ').downcase
    end

    # ================================================================
    # Export helpers — Excel XML / CSV
    # ฟังก์ชันส่งออก — Excel XML / CSV
    # ================================================================

    # Generate an Excel XML workbook string.
    # สร้าง Excel XML workbook จาก array ของ sheet hashes
    # @param sheets [Array<Hash>] each with :name and :rows (array of arrays)
    # @return [String]
    def excel_xml_workbook(sheets)
      xml = '<?xml version="1.0" encoding="UTF-8"?>' + "\n"
      xml << '<?mso-application progid="Excel.Sheet"?>' + "\n"
      xml << '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"' + "\n"
      xml << ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">' + "\n"

      sheets.each do |sheet|
        sheet_name = xml_escape(sheet[:name] || 'Sheet')
        xml << "  <Worksheet ss:Name=\"#{sheet_name}\">\n"
        xml << "    <Table>\n"

        (sheet[:rows] || []).each do |row|
          xml << "      <Row>\n"
          row.each do |cell_value|
            xml << "        #{excel_cell(cell_value)}\n"
          end
          xml << "      </Row>\n"
        end

        xml << "    </Table>\n"
        xml << "  </Worksheet>\n"
      end

      xml << "</Workbook>\n"
      xml
    end

    # Generate one Excel XML Cell element.
    # สร้าง Cell XML element หนึ่งตัว — ตรวจจับ Number vs String
    # @param value [Object]
    # @return [String]
    def excel_cell(value)
      if value.is_a?(Numeric)
        "<Cell><Data ss:Type=\"Number\">#{value}</Data></Cell>"
      else
        "<Cell><Data ss:Type=\"String\">#{xml_escape(value.to_s)}</Data></Cell>"
      end
    end

    # Escape special XML characters.
    # แปลงอักขระพิเศษสำหรับ XML
    # @param value [String]
    # @return [String]
    def xml_escape(value)
      value.to_s
           .gsub('&', '&amp;')
           .gsub('<', '&lt;')
           .gsub('>', '&gt;')
           .gsub('"', '&quot;')
    end

    # Escape a value for CSV output.
    # แปลงค่าสำหรับ CSV output — ครอบด้วย " และ escape " ภายใน
    # @param value [Object]
    # @return [String]
    def csv_escape(value)
      s = value.to_s
      '"' + s.gsub('"', '""') + '"'
    end

    # Generate CSV string from array of hashes.
    # สร้าง CSV string จาก array ของ hash
    # @param rows [Array<Hash>]
    # @param headers [Array<String>]
    # @return [String]
    def csv_from_rows(rows, headers)
      lines = []
      lines << headers.map { |h| csv_escape(h) }.join(',')
      rows.each do |row|
        line = headers.map { |h| csv_escape(row[h]) }.join(',')
        lines << line
      end
      lines.join("\n") + "\n"
    end

    # Format a number with fixed decimal places. Returns '' for nil.
    # จัดรูปแบบตัวเลขด้วยจำนวนทศนิยมคงที่ — คืน '' ถ้าเป็น nil
    # @param value [Numeric, nil]
    # @param digits [Integer]
    # @return [String]
    def format_number(value, digits = 2)
      return '' if value.nil?
      sprintf("%.#{digits}f", value)
    end

  end # module Support
end # module GOCarbonCredit

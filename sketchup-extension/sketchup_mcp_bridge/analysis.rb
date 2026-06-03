module Codex
  module SketchUpMCPBridge
    module Analysis
      def collect_component_records(entities, options, path = [], depth = 0)
        return [] if depth > 25

        records = []
        entities.each do |entity|
          next unless entity.is_a?(Sketchup::ComponentInstance) || entity.is_a?(Sketchup::Group)
          records << component_summary(entity, path, depth, options) if include_entity_in_component_list?(entity, options, depth)

          child_entities = nested_entities_for(entity)
          next unless child_entities

          child_path = path + [component_label(entity)]
          records.concat(collect_component_records(child_entities.to_a, options, child_path, depth + 1))
        end
        records
      end

      def include_entity_in_component_list?(entity, options, depth)
        matches_component_filters?(entity, options, depth)
      end

      def nested_entities_for(entity)
        return entity.entities if entity.is_a?(Sketchup::Group)
        return entity.definition.entities if entity.is_a?(Sketchup::ComponentInstance)
      end

      def component_summary(entity, path, depth, options)
        volume = entity_volume(entity)
        metrics = dimension_metrics(entity.bounds)
        density_info = density_info_for_entity(entity, options)
        {
          'type' => entity.typename,
          'entityID' => entity.entityID,
          'name' => entity_name(entity),
          'definitionName' => entity_definition_name(entity),
          'category' => component_category_name(entity),
          'tag' => entity_tag_name(entity),
          'path' => path + [component_label(entity)],
          'depth' => depth,
          'volume' => volume,
          'volumeM3' => volume_to_m3(volume),
          'surfaceAreaM2' => square_inches_to_square_meters(entity_surface_area(entity)),
          'dimensions' => metrics['display'],
          'lengthMm' => metrics['lengthMm'],
          'widthMm' => metrics['widthMm'],
          'heightMm' => metrics['heightMm'],
          'lengthM' => metrics['lengthM'],
          'widthM' => metrics['widthM'],
          'heightM' => metrics['heightM'],
          'material' => entity_material_name(entity),
          'isSolid' => !volume.nil?,
          'densityPresetUsed' => density_info[:density_preset],
          'densityKgM3Used' => density_info[:density_kg_m3],
          'estimatedWeightKg' => estimated_weight_kg(volume, density_info[:density_kg_m3])
        }
      end

      def metric_summary(entity)
        volume = entity_volume(entity)
        metrics = dimension_metrics(entity.bounds)
        density_info = density_info_for_entity(entity, @active_density_options || {})
        entity_summary(entity).merge(
          'volume' => volume,
          'volumeM3' => volume_to_m3(volume),
          'surfaceAreaM2' => square_inches_to_square_meters(entity_surface_area(entity)),
          'material' => entity_material_name(entity),
          'definitionName' => entity_definition_name(entity),
          'category' => component_category_name(entity),
          'isSolid' => !volume.nil?,
          'lengthMm' => metrics['lengthMm'],
          'widthMm' => metrics['widthMm'],
          'heightMm' => metrics['heightMm'],
          'lengthM' => metrics['lengthM'],
          'widthM' => metrics['widthM'],
          'heightM' => metrics['heightM'],
          'dimensions' => metrics['display'],
          'densityPresetUsed' => density_info[:density_preset],
          'densityKgM3Used' => density_info[:density_kg_m3],
          'estimatedWeightKg' => estimated_weight_kg(volume, density_info[:density_kg_m3])
        )
      end

      def entity_summary(entity)
        metrics = dimension_metrics(entity.bounds)
        {
          'type' => entity.typename,
          'entityID' => entity.entityID,
          'name' => entity_name(entity),
          'category' => component_category_name(entity),
          'tag' => entity_tag_name(entity),
          'dimensions' => metrics['display'],
          'lengthMm' => metrics['lengthMm'],
          'widthMm' => metrics['widthMm'],
          'heightMm' => metrics['heightMm'],
          'lengthM' => metrics['lengthM'],
          'widthM' => metrics['widthM'],
          'heightM' => metrics['heightM'],
          'isSolid' => solid_entity?(entity)
        }
      end

      def entity_name(entity)
        return entity.name.to_s unless blank?(entity.name)
        entity_definition_name(entity)
      end

      def entity_definition_name(entity)
        entity.respond_to?(:definition) && entity.definition ? entity.definition.name.to_s : entity.typename
      end

      def entity_tag_name(entity)
        entity.layer ? entity.layer.name.to_s : 'Untagged'
      end

      def entity_material_name(entity)
        return nil unless entity.respond_to?(:material) && entity.material
        material_display_name(entity.material)
      rescue StandardError
        nil
      end

      def entity_volume(entity)
        return nil unless entity.respond_to?(:volume)
        volume = entity.volume.to_f
        return nil if volume == -1.0
        volume < 0 ? volume.abs : volume
      rescue StandardError
        nil
      end

      def solid_entity?(entity)
        !entity_volume(entity).nil?
      end

      def entity_surface_area(entity)
        return entities_surface_area(entity.entities, entity.transformation) if entity.is_a?(Sketchup::Group)
        return entities_surface_area(entity.definition.entities, entity.transformation) if entity.is_a?(Sketchup::ComponentInstance)
      rescue StandardError
        nil
      end

      def entities_surface_area(entities, transformation)
        entities.reduce(0.0) do |sum, child|
          sum + if child.is_a?(Sketchup::Face)
                  child.area(transformation)
                elsif child.is_a?(Sketchup::Group)
                  entities_surface_area(child.entities, transformation * child.transformation)
                elsif child.is_a?(Sketchup::ComponentInstance)
                  entities_surface_area(child.definition.entities, transformation * child.transformation)
                else
                  0.0
                end
        end
      end

      def dimension_metrics(bounds)
        lengths = [bounds.width.to_f, bounds.height.to_f, bounds.depth.to_f].sort.reverse
        length_in = lengths[0] || 0.0
        width_in = lengths[1] || 0.0
        height_in = lengths[2] || 0.0
        {
          'lengthM' => inches_to_meters(length_in),
          'widthM' => inches_to_meters(width_in),
          'heightM' => inches_to_meters(height_in),
          'lengthMm' => inches_to_millimeters(length_in),
          'widthMm' => inches_to_millimeters(width_in),
          'heightMm' => inches_to_millimeters(height_in),
          'display' => format('%.0f x %.0f x %.0f mm', inches_to_millimeters(length_in), inches_to_millimeters(width_in), inches_to_millimeters(height_in))
        }
      end

      def component_label(entity)
        name = entity_name(entity)
        blank?(name) ? "#{entity.typename}-#{entity.entityID}" : name
      end

      def component_category_name(entity)
        haystack = [
          entity_name(entity),
          entity_definition_name(entity),
          entity_tag_name(entity),
          entity_material_name(entity)
        ].compact.join(' | ').downcase

        return 'door' if matches_density_keywords?(haystack, ['door', 'doors', 'ประตู'])
        return 'window' if matches_density_keywords?(haystack, ['window', 'windows', 'หน้าต่าง'])
        return 'beam' if matches_density_keywords?(haystack, ['beam', 'rc_beam', 'คาน'])
        return 'column' if matches_density_keywords?(haystack, ['column', 'rc_column', 'เสา'])
        return 'footing' if matches_density_keywords?(haystack, ['footing', 'foundation', 'rc_footing', 'ฐานราก'])
        return 'wall' if matches_density_keywords?(haystack, ['wall', 'walls', 'ผนัง'])
        return 'slab' if matches_density_keywords?(haystack, ['slab', 'floor', 'พื้น'])
        return 'roof' if matches_density_keywords?(haystack, ['roof', 'หลังคา'])
        return 'stair' if matches_density_keywords?(haystack, ['stair', 'stairs', 'บันได'])
        return 'opening' if matches_density_keywords?(haystack, ['opening', 'ช่องเปิด'])
        return 'mep' if matches_density_keywords?(haystack, ['pipe', 'duct', 'conduit', 'cable', 'mep'])
        return 'structure' if matches_density_keywords?(haystack, ['structure', 'structural', 'concrete', 'steel'])

        'generic'
      end

      def matches_tag_filter?(entity, tag_filters)
        return true if tag_filters.nil? || tag_filters.empty?
        tag_name = entity_tag_name(entity).downcase
        tag_filters.any? { |filter| tag_name == filter.downcase }
      end

      def matches_material_filter?(entity, material_filters)
        return true if material_filters.nil? || material_filters.empty?
        material_name = normalize_string(entity_material_name(entity))
        return false if material_name.nil?
        lowered = material_name.downcase
        material_filters.any? { |filter| lowered.include?(filter.downcase) }
      end

      def matches_definition_filter?(entity, definition_filters)
        return true if definition_filters.nil? || definition_filters.empty?
        haystack = [entity_definition_name(entity), entity_name(entity)].join(' ').downcase
        definition_filters.any? { |filter| haystack.include?(filter.downcase) }
      end

      def matches_name_filter?(entity, name_filter)
        return true if blank?(name_filter)
        haystack = [entity_name(entity), entity_definition_name(entity)].join(' ').downcase
        haystack.include?(name_filter.downcase)
      end

      def matches_depth_filter?(depth, min_depth, max_depth)
        return false if !min_depth.nil? && depth < min_depth
        return false if !max_depth.nil? && depth > max_depth
        true
      end

      def matches_component_filters?(entity, options, depth)
        return false if entity.is_a?(Sketchup::Group) && !options[:include_groups]
        return false unless matches_depth_filter?(depth, options[:min_depth], options[:max_depth])
        return false unless matches_tag_filter?(entity, options[:tag_filters] || [])
        excluded_tags = options[:exclude_tag_filters] || []
        return false if !excluded_tags.empty? && matches_tag_filter?(entity, excluded_tags)
        return false unless matches_name_filter?(entity, options[:name_filter])
        return false unless matches_material_filter?(entity, options[:material_filters] || [])
        return false unless matches_definition_filter?(entity, options[:definition_filters] || [])
        return false if options[:solid_only] && !solid_entity?(entity)
        true
      end

      def component_filter_options(args)
        density_kg_m3, density_preset = resolve_density(args)
        density_mode = density_kg_m3.nil? ? 'auto' : 'fixed'
        @active_density_kg_m3 = density_kg_m3
        @active_density_options = {
          density_kg_m3: density_kg_m3,
          density_preset: density_preset,
          density_mode: density_mode
        }
        {
          include_groups: truthy?(args['include_groups'], true),
          tag_filters: normalize_filters(args['tag_filter'] || args['tag_filters']),
          exclude_tag_filters: normalize_filters(args['exclude_tag_filter'] || args['exclude_tag_filters']),
          name_filter: normalize_string(args['name_filter']),
          material_filters: normalize_filters(args['material_filter'] || args['material_filters']),
          definition_filters: normalize_filters(args['definition_filter'] || args['definition_filters']),
          min_depth: integer_or_nil(args['min_depth']),
          max_depth: integer_or_nil(args['max_depth']),
          solid_only: truthy?(args['solid_only'], false),
          density_kg_m3: density_kg_m3,
          density_preset: density_preset,
          density_mode: density_mode
        }
      end

      def filter_summary(filters)
        {
          'includeGroups' => filters[:include_groups],
          'tagFilters' => filters[:tag_filters],
          'excludeTagFilters' => filters[:exclude_tag_filters],
          'nameFilter' => filters[:name_filter],
          'materialFilters' => filters[:material_filters],
          'definitionFilters' => filters[:definition_filters],
          'minDepth' => filters[:min_depth],
          'maxDepth' => filters[:max_depth],
          'solidOnly' => filters[:solid_only]
        }
      end

      def weight_summary(filters)
        {
          'densityMode' => filters[:density_mode],
          'densityPreset' => filters[:density_preset],
          'densityKgM3' => filters[:density_kg_m3],
          'autoRules' => filters[:density_mode] == 'auto' ? 'material/tag/name/definition keywords' : nil
        }
      end

      def edge_filter_options(args)
        {
          tag_filters: normalize_filters(args['tag_filter'] || args['tag_filters']),
          exclude_tag_filters: normalize_filters(args['exclude_tag_filter'] || args['exclude_tag_filters']),
          name_filter: normalize_string(args['name_filter']),
          include_hidden: truthy?(args['include_hidden'], true),
          short_edge_threshold_mm: numeric_or_default(args['short_edge_threshold_mm'], 5.0)
        }
      end

      def collect_edge_records(entities, options, path = [], depth = 0, transformation = nil)
        return [] if depth > 25

        records = []
        current_transformation = transformation || Geom::Transformation.new
        entities.each do |entity|
          case entity
          when Sketchup::Edge
            record = edge_summary(entity, current_transformation, path, depth, options)
            records << record if record
          when Sketchup::Group
            child_path = path + [component_label(entity)]
            child_transformation = current_transformation * entity.transformation
            records.concat(collect_edge_records(entity.entities.to_a, options, child_path, depth + 1, child_transformation))
          when Sketchup::ComponentInstance
            child_path = path + [component_label(entity)]
            child_transformation = current_transformation * entity.transformation
            records.concat(collect_edge_records(entity.definition.entities.to_a, options, child_path, depth + 1, child_transformation))
          end
        end
        records
      end

      def edge_summary(edge, transformation, path, depth, options)
        length_in = edge.length(transformation).to_f
        tag = entity_tag_name(edge)
        hidden = edge.hidden?
        path_text = path.join(' > ')
        return nil unless matches_edge_filters?(tag, path_text, hidden, options)

        faces_count = edge.faces.length
        {
          'entityID' => edge.entityID,
          'tag' => tag,
          'path' => path,
          'depth' => depth,
          'lengthMm' => inches_to_millimeters(length_in),
          'lengthM' => inches_to_meters(length_in),
          'hidden' => hidden,
          'soft' => edge.soft?,
          'smooth' => edge.smooth?,
          'curve' => !edge.curve.nil?,
          'facesCount' => faces_count,
          'isLoose' => faces_count.zero?,
          'isShortEdge' => inches_to_millimeters(length_in) < options[:short_edge_threshold_mm]
        }
      rescue StandardError
        nil
      end

      def matches_edge_filters?(tag, path_text, hidden, options)
        return false if !options[:include_hidden] && hidden
        return false if !options[:tag_filters].empty? && !options[:tag_filters].any? { |filter| tag.downcase == filter.downcase }
        return false if !options[:exclude_tag_filters].empty? && options[:exclude_tag_filters].any? { |filter| tag.downcase == filter.downcase }
        return true if blank?(options[:name_filter])

        path_text.downcase.include?(options[:name_filter].downcase)
      end

      def top_level_geometry_summary(entities)
        summary = {
          'rawEdges' => 0,
          'rawFaces' => 0,
          'rawGroups' => 0,
          'rawComponents' => 0
        }
        entities.each do |entity|
          case entity
          when Sketchup::Edge
            summary['rawEdges'] += 1
          when Sketchup::Face
            summary['rawFaces'] += 1
          when Sketchup::Group
            summary['rawGroups'] += 1
          when Sketchup::ComponentInstance
            summary['rawComponents'] += 1
          end
        end
        summary
      end

      def audit_issue_rows(component_records, edge_records, top_level_summary)
        rows = []
        rows << build_record_issue(component_records, 'warning', 'default_tag_components', 'Components on Layer0 / ชิ้นงานอยู่ Layer0') { |row| %w[Layer0 Untagged].include?(row['tag']) }
        rows << build_record_issue(component_records, 'warning', 'unnamed_groups', 'Unnamed groups / กลุ่มไม่ตั้งชื่อ') { |row| row['type'] == 'Group' && unnamed_component_record?(row) }
        rows << build_record_issue(component_records, 'info', 'non_solids', 'Non-solid groups/components / ชิ้นงานไม่เป็น solid') { |row| !row['isSolid'] }
        rows << build_record_issue(component_records, 'warning', 'door_window_default_tag', 'Door/window on Layer0 / ประตูหน้าต่างอยู่ Layer0') { |row| %w[door window].include?(row['category']) && %w[Layer0 Untagged].include?(row['tag']) }
        rows << build_record_issue(component_records, 'warning', 'door_window_missing_name', 'Door/window missing name / ประตูหน้าต่างไม่ตั้งชื่อ') { |row| %w[door window].include?(row['category']) && unnamed_component_record?(row) }
        rows << build_record_issue(component_records, 'info', 'door_window_missing_material', 'Door/window missing material / ประตูหน้าต่างไม่ระบุวัสดุ') { |row| %w[door window].include?(row['category']) && blank?(row['material']) }
        rows << build_record_issue(component_records, 'warning', 'door_window_as_group', 'Door/window modeled as group / ประตูหน้าต่างทำเป็น group') { |row| %w[door window].include?(row['category']) && row['type'] == 'Group' }
        rows << build_record_issue(component_records, 'warning', 'door_window_missing_size', 'Door/window suspicious size / ประตูหน้าต่างขนาดผิดปกติ') { |row| %w[door window].include?(row['category']) && suspicious_opening_size?(row) }
        rows << build_record_issue(component_records, 'info', 'opening_default_tag', 'Opening on Layer0 / ช่องเปิดอยู่ Layer0') { |row| row['category'] == 'opening' && %w[Layer0 Untagged].include?(row['tag']) }
        rows << build_record_issue(component_records, 'info', 'generic_large_items', 'Large generic items / ชิ้นงานทั่วไปขนาดใหญ่') { |row| row['category'] == 'generic' && (row['volumeM3'].to_f > 0.05 || row['surfaceAreaM2'].to_f > 1.0) }
        rows << build_dimension_variation_issue(component_records)
        rows << audit_issue_row('warning', 'top_level_edges', 'Loose top-level edges / เส้นลอยระดับบน', top_level_summary['rawEdges'])
        rows << audit_issue_row('warning', 'top_level_faces', 'Loose top-level faces / หน้าเปิดระดับบน', top_level_summary['rawFaces'])
        rows << audit_issue_row('warning', 'short_edges', 'Short edges / เส้นสั้น', edge_records.count { |row| row['isShortEdge'] })
        rows << audit_issue_row('warning', 'loose_edges', 'Loose edges / เส้นไม่ขึ้นหน้า', edge_records.count { |row| row['isLoose'] })
        rows << audit_issue_row('info', 'hidden_edges', 'Hidden edges / เส้นซ่อน', edge_records.count { |row| row['hidden'] })
        rows.reject { |row| row['count'].to_i.zero? }
      end

      def audit_issue_row(severity, code, label, count, sample_names = [], entity_ids = [])
        {
          'severity' => severity,
          'code' => code,
          'label' => label,
          'count' => count,
          'sampleNames' => sample_names,
          'entityIds' => entity_ids
        }
      end

      def build_record_issue(records, severity, code, label)
        matches = records.select { |row| yield(row) }
        audit_issue_row(severity, code, label, matches.length, sample_record_names(matches), matches.map { |row| row['entityID'] }.uniq.first(20))
      end

      def build_dimension_variation_issue(records)
        grouped = records.group_by { |row| [row['category'], row['definitionName']].join('|') }
        offenders = grouped.values.select do |items|
          next false unless items.any? { |row| %w[door window opening].include?(row['category']) }
          items.map { |row| [row['lengthMm'].to_i, row['widthMm'].to_i, row['heightMm'].to_i] }.uniq.length > 1
        end.flatten

        audit_issue_row(
          'warning',
          'definition_dimension_variation',
          'Same definition with varying sizes / แบบเดียวแต่หลายขนาด',
          offenders.map { |row| row['definitionName'] }.uniq.length,
          sample_record_names(offenders),
          offenders.map { |row| row['entityID'] }.uniq.first(20)
        )
      end

      def suspicious_opening_size?(row)
        width = row['widthMm'].to_f
        height = row['heightMm'].to_f
        width <= 300 || height <= 300 || width >= 5000 || height >= 5000
      end

      def sample_record_names(records, max_count = 5)
        records.map { |row| normalize_string(row['name']) || normalize_string(row['definitionName']) || "Entity #{row['entityID']}" }.reject(&:nil?).uniq.first(max_count)
      end

      def unnamed_component_record?(row)
        name = normalize_string(row['name'])
        definition = normalize_string(row['definitionName'])
        return true if blank?(name)
        return true if definition && definition =~ /\AGroup\d*#?\d*\z/i

        false
      end
    end
  end
end

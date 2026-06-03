module GOCarbonCredit
  module Heatmap
    HEATMAP_PREFIX = 'GOCarbon_HM_'.freeze

    def apply_heatmap(args = {})
      result = calculate_carbon(args)
      comps  = result['components']
      
      max_co2 = comps.map { |r| r['kgCO2e'].to_f }.max || 1.0
      
      model = Sketchup.active_model
      model.start_operation('GO Carbon Heatmap', true)
      
      colored = 0
      
      # We iterate over model entities to find components matching the IDs
      # since find_entity_by_id may not exist in older SketchUp versions
      entity_map = {}
      scan_for_heatmap_entities(model.entities, entity_map)
      
      comps.each do |rec|
        entity = entity_map[rec['entityID']]
        next unless entity
        
        ratio = rec['kgCO2e'].to_f / max_co2
        color_arr = gradient_color(ratio)
        
        mat_name = "#{HEATMAP_PREFIX}#{rec['entityID']}"
        mat = model.materials[mat_name]
        unless mat
          mat = model.materials.add(mat_name)
        end
        mat.color = Sketchup::Color.new(*color_arr)
        
        entity.material = mat
        colored += 1
      end
      
      model.commit_operation
      
      { 'coloredCount' => colored, 'maxKgCO2e' => round(max_co2, 2) }
    rescue => e
      model.abort_operation
      raise
    end

    def remove_heatmap(args = {})
      model = Sketchup.active_model
      model.start_operation('Remove GO Carbon Heatmap', true)
      
      removed = 0
      materials_to_remove = []
      
      model.materials.to_a.each do |mat|
        if mat.name.start_with?(HEATMAP_PREFIX)
          materials_to_remove << mat
        end
      end
      
      # Remove materials. Entities using them will revert to default.
      materials_to_remove.each do |mat|
        begin
          model.materials.remove(mat)
          removed += 1
        rescue
          # some old SU versions don't support remove, so we just purge unused later
        end
      end
      
      model.commit_operation
      { 'removedCount' => removed }
    end

    private

    def scan_for_heatmap_entities(entities, map)
      entities.each do |e|
        next unless e.is_a?(Sketchup::ComponentInstance) || e.is_a?(Sketchup::Group)
        map[e.entityID] = e
        
        children = e.is_a?(Sketchup::Group) ? e.entities : e.definition.entities
        scan_for_heatmap_entities(children, map)
      end
    end

    def gradient_color(ratio)
      # Clamp ratio
      ratio = 1.0 if ratio > 1.0
      ratio = 0.0 if ratio < 0.0
      
      colors = HEATMAP_COLORS
      t = ratio * (colors.length - 1)
      i = t.floor
      i = colors.length - 2 if i >= colors.length - 1
      f = t - i
      
      # Interpolate
      c1 = colors[i]
      c2 = colors[i + 1]
      
      r = (c1.red + (c2.red - c1.red) * f).round
      g = (c1.green + (c2.green - c1.green) * f).round
      b = (c1.blue + (c2.blue - c1.blue) * f).round
      
      [r, g, b]
    end
  end
end

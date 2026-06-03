module GOCarbonCredit
  module CarbonEngine
    def calculate_carbon(args = {})
      records = scan_model(args)
      rules   = load_ef_rules(args)
      
      building_type = args['building_type'] || 'office'
      floor_area    = args['floor_area_m2'] ? args['floor_area_m2'].to_f : estimate_floor_area(records)
      
      matched, unmatched = match_all(records, rules)
      
      total_kgco2e = matched.reduce(0.0) { |sum, r| sum + r['kgCO2e'].to_f }
      
      bm    = carbon_rating(total_kgco2e, floor_area, building_type)
      env   = analyze_envelope(records)
      tips  = build_suggestions(matched, building_type, env)
      
      {
        'meta'           => build_meta(args, building_type, floor_area),
        'summary'        => build_summary(total_kgco2e, floor_area, matched, unmatched, bm),
        'byMaterial'     => group_by_field(matched, 'ef_material', total_kgco2e),
        'byCategory'     => group_by_field(matched, 'category', total_kgco2e),
        'byTag'          => group_by_field(matched, 'tag', total_kgco2e),
        'benchmark'      => bm,
        'envelope'       => env,
        'suggestions'    => tips,
        'components'     => matched,
        'unmatchedItems' => unmatched,
        'efRules'        => rules
      }
    end

    def load_ef_rules(args = {})
      paths = [
        [project_ef_path(args),  'project',  300],
        [global_ef_path(args),   'global',   200],
        [default_ef_path,        'default',  100]
      ]
      
      rules = []
      paths.each do |path, source, priority|
        rules.concat(parse_ef_csv(path, source, priority)) if path && !path.empty?
      end
      
      deduplicate_rules(rules)
    end

    def default_ef_path
      File.join(TEMPLATE_ROOT, 'carbon_emission_factors.csv')
    end

    def global_ef_path(args)
      args['global_ef_path'] || default_ef_path
    end

    def project_ef_path(args)
      return args['project_ef_path'] if args['project_ef_path']
      
      model = Sketchup.active_model
      if model && model.path && !model.path.empty?
        base = File.basename(model.path, File.extname(model.path))
        return File.join(File.dirname(model.path), "#{base}_carbon_ef.csv")
      end
      nil
    end

    def match_all(records, rules)
      matched   = []
      unmatched = []
      
      records.each do |rec|
        rule = rules.find { |r| ef_matches?(r, rec) }
        
        if rule
          qty = quantity_for(rec, rule['quantity_source'])
          
          if qty && qty > 0
            co2 = qty * rule['ef_value'].to_f
            
            matched << rec.merge(
              'ef_id'           => rule['ef_id'],
              'ef_material'     => rule['material_name_th'],
              'ef_value'        => rule['ef_value'],
              'ef_unit'         => rule['ef_unit'],
              'quantity_source' => rule['quantity_source'],
              'quantity_used'   => round(qty, 4),
              'kgCO2e'          => round(co2, 2)
            )
          else
            unmatched << rec.merge('reason' => "No usable quantity for #{rule['quantity_source']}")
          end
        else
          unmatched << rec.merge('reason' => 'No matching emission factor rule')
        end
      end
      
      [matched, unmatched]
    end

    def ef_matches?(rule, record)
      mt = (rule['match_type'] || '').downcase
      mv = (rule['match_value'] || '').downcase
      
      case mt
      when 'tag'        then record['tag'].to_s.downcase == mv
      when 'material'   then record['material'].to_s.downcase.include?(mv)
      when 'category'   then record['category'].to_s.downcase == mv
      when 'definition' then record['definitionName'].to_s.downcase.include?(mv)
      when 'name'       then record['name'].to_s.downcase.include?(mv)
      when 'any'        then true
      else haystack(record).downcase.include?(mv)
      end
    end

    def quantity_for(record, source)
      case source.to_s
      when 'volumeM3'          then record['volumeM3']
      when 'surfaceAreaM2'     then record['surfaceAreaM2']
      when 'estimatedWeightKg' then record['estimatedWeightKg']
      when 'lengthM'           then record['lengthM']
      when 'count'             then 1.0
      else nil
      end
    end

    def group_by_field(matched, field, total_co2)
      buckets = {}
      
      matched.each do |rec|
        key = blank?(rec[field]) ? 'Unspecified' : rec[field]
        b = buckets[key] ||= { 'name' => key, 'kgCO2e' => 0.0, 'count' => 0 }
        b['kgCO2e'] += rec['kgCO2e'].to_f
        b['count']  += 1
      end
      
      sorted = buckets.values.sort_by { |b| -b['kgCO2e'] }
      
      sorted.each do |b|
        b['kgCO2e']  = round(b['kgCO2e'], 2)
        b['percent'] = total_co2 > 0 ? round(b['kgCO2e'] / total_co2 * 100, 1) : 0
      end
      
      sorted
    end

    def build_meta(args, building_type, floor_area)
      model = Sketchup.active_model
      {
        'projectName'      => model.title.to_s.empty? ? 'Untitled' : model.title.to_s,
        'modelPath'        => model.path.to_s,
        'exportedAt'       => Time.now.to_s,
        'pluginVersion'    => VERSION,
        'buildingType'     => building_type,
        'totalFloorAreaM2' => round(floor_area, 2)
      }
    end

    def build_summary(total, floor_area, matched, unmatched, bm)
      {
        'totalKgCO2e'    => round(total, 2),
        'totalTCO2e'     => round(total / 1000.0, 2),
        'carbonPerM2'    => round(total / (floor_area > 0 ? floor_area : 1.0), 1),
        'rating'         => bm['rating'],
        'matchedCount'   => matched.length,
        'unmatchedCount' => unmatched.length,
        'componentCount' => matched.length + unmatched.length
      }
    end
  end
end

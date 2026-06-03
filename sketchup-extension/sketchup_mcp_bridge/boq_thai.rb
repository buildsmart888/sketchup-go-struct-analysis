module Codex
  module SketchUpMCPBridge
    module BoqThai
      BOQ_THAI_HEADERS = %w[
        no category item_code description_th unit quantity material_unit_cost material_amount
        labor_unit_cost labor_amount total_amount source note
      ].freeze

      RAW_TAKEOFF_HEADERS = %w[
        type entityID name definitionName category tag dimensions lengthM widthM heightM
        volumeM3 surfaceAreaM2 estimatedWeightKg material isSolid path
      ].freeze

      PRICE_RULE_HEADERS = %w[
        enabled priority rule_id match_type match_value category item_code description_th unit
        quantity_source material_unit_cost labor_unit_cost waste_percent note
      ].freeze

      UNMATCHED_HEADERS = %w[
        entityID name definitionName category tag material quantity_hint reason suggested_match_type suggested_match_value
      ].freeze

      FALLBACK_BOQ_THAI_RULES = [
        {
          'enabled' => 'true',
          'priority' => '0',
          'rule_id' => 'RC_BEAM',
          'match_type' => 'category',
          'match_value' => 'beam',
          'category' => 'Structural',
          'item_code' => 'STR-RC-BEAM',
          'description_th' => 'RC beam',
          'unit' => 'm3',
          'quantity_source' => 'volumeM3',
          'material_unit_cost' => 0,
          'labor_unit_cost' => 0,
          'waste_percent' => 0,
          'note' => 'Set material and labor cost in price rules'
        },
        {
          'enabled' => 'true',
          'priority' => '0',
          'rule_id' => 'WALL',
          'match_type' => 'category',
          'match_value' => 'wall',
          'category' => 'Wall',
          'item_code' => 'ARC-WALL',
          'description_th' => 'Wall',
          'unit' => 'm2',
          'quantity_source' => 'surfaceAreaM2',
          'material_unit_cost' => 0,
          'labor_unit_cost' => 0,
          'waste_percent' => 0,
          'note' => 'Set material and labor cost in price rules'
        }
      ].freeze

      def summarize_boq_thai(args = {})
        merged = apply_filter_defaults(args, true)
        filters = component_filter_options(merged)
        selected_only = truthy?(merged['selected_only'], false)
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        records = collect_component_records(entities, filters)
        rules = load_boq_thai_rules(merged)
        rows, unmatched = build_boq_thai_rows(records, rules)

        {
          'count' => rows.length,
          'selectedOnly' => selected_only,
          'globalPriceRulesPath' => boq_global_rules_path(merged),
          'projectOverridesPath' => boq_project_overrides_path(merged),
          'priceRulesCount' => rules.length,
          'totals' => boq_thai_totals(rows, unmatched.length),
          'warnings' => boq_thai_warnings(rows, unmatched, records),
          'rows' => rows,
          'rawTakeoff' => component_export_rows(records),
          'priceRules' => rules,
          'unmatchedItems' => unmatched,
          'modelAudit' => summarize_model_audit(merged)
        }
      end

      def export_boq_thai_report(args = {})
        merged = apply_filter_defaults(args, true)
        path = merged['path']
        raise ArgumentError, 'path is required' if blank?(path)

        result = summarize_boq_thai(merged)
        FileUtils.mkdir_p(File.dirname(path))
        ext = File.extname(path).downcase
        format =
          case ext
          when '.json'
            File.write(path, JSON.pretty_generate(result))
            'json'
          when '.html', '.htm'
            File.write(path, boq_thai_html(result))
            'html'
          when '.xls', '.xml'
            write_excel_workbook(path, boq_thai_workbook_sheets(result))
            'excel-xml'
          when '.xlsx'
            raise ArgumentError, 'Ruby SketchUp export supports .xls/.xml/.html/.json. Use the MCP export_boq_thai_report tool for real .xlsx output.'
          else
            File.write(path, csv_from_rows(result['rows'], BOQ_THAI_HEADERS, 'th'))
            'csv'
          end

        result.merge('path' => path, 'format' => format)
      end

      def default_boq_thai_rules_path
        File.join(TEMPLATE_ROOT, 'boq_thai_price_rules.csv')
      end

      def boq_global_rules_path(args = {})
        merged = stringify_keys(args)
        normalize_string(merged['global_price_rules_path']) ||
          normalize_string(merged['price_rules_path']) ||
          default_boq_thai_rules_path
      end

      def boq_project_overrides_path(args = {})
        merged = stringify_keys(args)
        explicit = normalize_string(merged['project_overrides_path'])
        return explicit if explicit

        model = Sketchup.active_model
        if model && !blank?(model.path)
          base = File.basename(model.path, File.extname(model.path))
          return File.join(File.dirname(model.path), "#{base}_boq_overrides.csv")
        end

        File.join(QUEUE_ROOT, 'boq_thai_project_overrides.csv')
      end

      def load_boq_thai_rules(args = {})
        merged = stringify_keys(args)
        groups = [
          ['project', boq_project_overrides_path(merged), 300],
          ['global', boq_global_rules_path(merged), 200],
          ['default', default_boq_thai_rules_path, 100]
        ]

        rules = []
        groups.each do |source, path, source_priority|
          rules.concat(load_boq_rule_file(path, source, source_priority))
        end

        rules = FALLBACK_BOQ_THAI_RULES.map { |rule| normalize_boq_rule(rule, 'fallback', 0) } if rules.empty?
        sorted_rules = rules.select { |rule| truthy?(rule['enabled'], true) }.sort_by do |rule|
          [-rule['sourcePriority'].to_i, -rule['priority'].to_i, rule['rule_id'].to_s]
        end
        seen = {}
        sorted_rules.each_with_object([]) do |rule, result|
          key = normalize_string(rule['rule_id']) || "#{rule['match_type']}|#{rule['match_value']}"
          next if seen[key]

          seen[key] = true
          result << rule
        end
      end

      def load_boq_rule_file(path, source, source_priority)
        return [] if blank?(path) || !File.exist?(path) || File.extname(path).downcase != '.csv'

        csv_text = File.open(path, 'rb') { |file| file.read }
        csv_text.force_encoding('UTF-8') if csv_text.respond_to?(:force_encoding)
        csv_text = csv_text.sub(/\A\xEF\xBB\xBF/, '')
        CSV.parse(csv_text, headers: true).map do |row|
          raw = PRICE_RULE_HEADERS.each_with_object({}) { |key, rule| rule[key] = row[key] }
          normalize_boq_rule(raw, source, source_priority)
        end
      rescue StandardError
        []
      end

      def normalize_boq_rule(raw, source, source_priority)
        rule = PRICE_RULE_HEADERS.each_with_object({}) do |key, result|
          result[key] = raw[key]
        end
        rule['enabled'] = missing_filter_value?(rule['enabled']) ? 'true' : rule['enabled']
        rule['priority'] = numeric_or_default(rule['priority'], 0)
        rule['match_type'] = normalize_string(rule['match_type']) || 'keyword'
        rule['category'] = normalize_string(rule['category']) || 'Unspecified'
        rule['item_code'] = normalize_string(rule['item_code']) || normalize_string(rule['rule_id']) || ''
        rule['description_th'] = normalize_string(rule['description_th']) || 'Unspecified item'
        rule['unit'] = normalize_string(rule['unit']) || 'set'
        rule['quantity_source'] = normalize_string(rule['quantity_source']) || 'count'
        rule['material_unit_cost'] = numeric_or_default(rule['material_unit_cost'], 0)
        rule['labor_unit_cost'] = numeric_or_default(rule['labor_unit_cost'], 0)
        rule['waste_percent'] = numeric_or_default(rule['waste_percent'], 0)
        rule['note'] = normalize_string(rule['note']) || ''
        rule['source'] = source
        rule['sourcePriority'] = source_priority
        rule
      end

      def build_boq_thai_rows(records, rules)
        buckets = {}
        unmatched = []

        records.each do |record|
          rule = rules.find { |candidate| boq_rule_matches_record?(candidate, record) }
          unless rule
            unmatched << unmatched_boq_item(record, 'No matching price rule')
            next
          end

          source = normalize_string(rule['quantity_source']) || 'count'
          quantity = boq_quantity_for(record, source)
          if quantity.nil? || quantity.to_f <= 0
            unmatched << unmatched_boq_item(record, "No usable quantity for #{source}")
            next
          end

          rule_id = normalize_string(rule['rule_id']) || normalize_string(rule['item_code']) || "rule-#{buckets.length + 1}"
          bucket = buckets[rule_id] ||= seed_boq_bucket(rule)
          bucket['quantity'] += quantity.to_f
          bucket['sourceNames'] << boq_source_name(record)
        end

        rows = buckets.values.each_with_index.map do |bucket, index|
          quantity = bucket['quantity']
          material_unit_cost = bucket['material_unit_cost'].to_f
          labor_unit_cost = bucket['labor_unit_cost'].to_f
          waste_multiplier = 1.0 + (bucket['waste_percent'].to_f / 100.0)
          material_amount = quantity * material_unit_cost * waste_multiplier
          labor_amount = quantity * labor_unit_cost
          {
            'no' => index + 1,
            'category' => bucket['category'],
            'item_code' => bucket['item_code'],
            'description_th' => bucket['description_th'],
            'unit' => bucket['unit'],
            'quantity' => round_number(quantity, 3),
            'material_unit_cost' => round_number(material_unit_cost, 2),
            'material_amount' => round_number(material_amount, 2),
            'labor_unit_cost' => round_number(labor_unit_cost, 2),
            'labor_amount' => round_number(labor_amount, 2),
            'total_amount' => round_number(material_amount + labor_amount, 2),
            'source' => bucket['sourceNames'].uniq.first(10).join(' | '),
            'note' => bucket['note']
          }
        end

        [rows, unmatched]
      end

      def seed_boq_bucket(rule)
        {
          'category' => rule['category'],
          'item_code' => rule['item_code'],
          'description_th' => rule['description_th'],
          'unit' => rule['unit'],
          'material_unit_cost' => rule['material_unit_cost'],
          'labor_unit_cost' => rule['labor_unit_cost'],
          'waste_percent' => rule['waste_percent'],
          'note' => rule['note'],
          'quantity' => 0.0,
          'sourceNames' => []
        }
      end

      def boq_rule_matches_record?(rule, record)
        match_type = normalize_string(rule['match_type']).to_s.downcase
        match_value = normalize_string(rule['match_value']).to_s.downcase
        return true if match_type == 'any'
        return false if match_value.empty?

        case match_type
        when 'tag'
          record['tag'].to_s.downcase == match_value
        when 'material'
          record['material'].to_s.downcase.include?(match_value)
        when 'definition', 'definitionname'
          record['definitionName'].to_s.downcase.include?(match_value)
        when 'category'
          record['category'].to_s.downcase == match_value
        when 'name'
          record['name'].to_s.downcase.include?(match_value)
        else
          boq_record_haystack(record).include?(match_value)
        end
      end

      def boq_record_haystack(record)
        [
          record['tag'],
          record['material'],
          record['definitionName'],
          record['name'],
          record['category'],
          Array(record['path']).join(' ')
        ].compact.join(' | ').downcase
      end

      def boq_quantity_for(record, source)
        case source.to_s
        when 'volumeM3' then record['volumeM3']
        when 'surfaceAreaM2' then record['surfaceAreaM2']
        when 'lengthM' then record['lengthM']
        when 'estimatedWeightKg' then record['estimatedWeightKg']
        when 'count' then 1.0
        else record[source.to_s]
        end
      end

      def unmatched_boq_item(record, reason)
        match_type, match_value = suggested_match_for_record(record)
        {
          'entityID' => record['entityID'],
          'name' => record['name'],
          'definitionName' => record['definitionName'],
          'category' => record['category'],
          'tag' => record['tag'],
          'material' => record['material'],
          'quantity_hint' => first_present_quantity(record),
          'reason' => reason,
          'suggested_match_type' => match_type,
          'suggested_match_value' => match_value
        }
      end

      def suggested_match_for_record(record)
        return ['tag', record['tag']] unless blank?(record['tag']) || %w[Layer0 Untagged].include?(record['tag'])
        return ['category', record['category']] unless blank?(record['category']) || record['category'] == 'generic'
        return ['definition', record['definitionName']] unless blank?(record['definitionName'])
        ['name', record['name']]
      end

      def first_present_quantity(record)
        %w[volumeM3 surfaceAreaM2 lengthM estimatedWeightKg].each do |key|
          value = record[key]
          return "#{key}: #{round_number(value.to_f, 3)}" if value && value.to_f > 0
        end
        'count: 1'
      end

      def boq_source_name(record)
        [record['tag'], record['definitionName'], record['name']].compact.reject(&:empty?).join(' / ')
      end

      def boq_thai_totals(rows, unmatched_count = 0)
        {
          'materialAmount' => round_number(sum_numeric(rows, 'material_amount'), 2),
          'laborAmount' => round_number(sum_numeric(rows, 'labor_amount'), 2),
          'totalAmount' => round_number(sum_numeric(rows, 'total_amount'), 2),
          'unmatchedCount' => unmatched_count
        }
      end

      def boq_thai_warnings(rows, unmatched, records)
        warnings = []
        warnings << "#{unmatched.length} unmatched item(s)" if unmatched.length > 0
        warnings << "#{records.count { |row| !row['isSolid'] }} non-solid item(s)" if records.any? { |row| !row['isSolid'] }
        warnings << "#{rows.count { |row| row['material_unit_cost'].to_f.zero? && row['labor_unit_cost'].to_f.zero? }} BOQ row(s) with zero unit cost"
        warnings
      end

      def boq_thai_workbook_sheets(result)
        [
          { name: '01_BOQ_THAI', rows: labeled_rows(result['rows'], BOQ_THAI_HEADERS, 'th') },
          { name: '02_Raw_Takeoff', rows: labeled_rows(result['rawTakeoff'], RAW_TAKEOFF_HEADERS, 'th') },
          { name: '03_Price_Rules', rows: result['priceRules'] },
          { name: '04_Unmatched_Items', rows: labeled_rows(result['unmatchedItems'], UNMATCHED_HEADERS, 'th') },
          { name: '05_Model_Audit', rows: labeled_rows(result['modelAudit']['issues'] || [], model_audit_issue_headers, 'th') }
        ]
      end

      def export_boq_unmatched_template(args = {})
        merged = stringify_keys(args)
        path = merged['path']
        raise ArgumentError, 'path is required' if blank?(path)

        result = summarize_boq_thai(merged)
        rows = result['unmatchedItems'].map.with_index do |item, index|
          {
            'enabled' => 'true',
            'priority' => '100',
            'rule_id' => "PROJECT_RULE_#{index + 1}",
            'match_type' => item['suggested_match_type'],
            'match_value' => item['suggested_match_value'],
            'category' => item['category'],
            'item_code' => '',
            'description_th' => item['definitionName'] || item['name'],
            'unit' => '',
            'quantity_source' => suggested_quantity_source(item['quantity_hint']),
            'material_unit_cost' => 0,
            'labor_unit_cost' => 0,
            'waste_percent' => 0,
            'note' => item['reason']
          }
        end

        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, csv_from_rows(rows, PRICE_RULE_HEADERS, nil))
        { 'path' => path, 'count' => rows.length }
      end

      def suggested_quantity_source(quantity_hint)
        text = quantity_hint.to_s
        return 'volumeM3' if text.start_with?('volumeM3')
        return 'surfaceAreaM2' if text.start_with?('surfaceAreaM2')
        return 'lengthM' if text.start_with?('lengthM')
        return 'estimatedWeightKg' if text.start_with?('estimatedWeightKg')
        'count'
      end

      def append_boq_project_override(args = {})
        merged = stringify_keys(args)
        path = boq_project_overrides_path(merged)
        rule = normalize_boq_rule(merged, 'project', 300)
        rule['rule_id'] = normalize_string(rule['rule_id']) || "PROJECT_RULE_#{Time.now.to_i}"

        rows = load_boq_rule_file(path, 'project', 300)
        rows.reject! { |existing| existing['rule_id'].to_s == rule['rule_id'].to_s }
        rows << rule
        save_boq_rules(path, rows)
        { 'path' => path, 'rule' => rule, 'count' => rows.length }
      end

      def save_boq_rules(path, rows)
        FileUtils.mkdir_p(File.dirname(path))
        File.write(path, csv_from_rows(rows, PRICE_RULE_HEADERS, nil))
      end

      def boq_thai_manager_state(args = {})
        merged = stringify_keys(args)
        merged['global_price_rules_path'] ||= boq_global_rules_path(merged)
        merged['project_overrides_path'] ||= boq_project_overrides_path(merged)
        result = summarize_boq_thai(merged)
        {
          'args' => merged,
          'result' => result,
          'globalPath' => merged['global_price_rules_path'],
          'projectPath' => merged['project_overrides_path']
        }
      end

      def boq_thai_html(result)
        render_template(
          'result_dialog.html',
          'TITLE' => 'BOQ THAI Preview',
          'RESULT_HTML' => render_result_sections({
            'totals' => result['totals'],
            'warnings' => result['warnings'],
            'rows' => result['rows'],
            'unmatchedItems' => result['unmatchedItems']
          }, 'th')
        )
      end

      def round_number(value, digits)
        factor = 10**digits
        (value.to_f * factor).round / factor.to_f
      end
    end
  end
end

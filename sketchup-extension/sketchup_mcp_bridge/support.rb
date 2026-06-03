module Codex
  module SketchUpMCPBridge
    module Support
      def normalize_tag_filters(raw)
        normalize_filters(raw)
      end

      def normalize_filters(raw)
        values =
          case raw
          when nil then []
          when Array then raw
          else raw.to_s.split(',')
          end

        values.map { |value| normalize_string(value) }.compact
      end

      def normalize_string(value)
        return nil if blank?(value)

        value.to_s.strip
      end

      def apply_filter_defaults(args, report_defaults)
        merged = stringify_keys(args)
        merged['locale'] = resolve_locale(merged['locale'])
        preset_name = normalize_string(merged['preset'] || merged['report_preset'])
        if preset_name
          preset_filters = PRESET_FILTERS[preset_name.downcase]
          if preset_filters
            preset_filters.each do |key, value|
              merged[key] = value if missing_filter_value?(merged[key])
            end
          end
        end

        if report_defaults && missing_filter_value?(merged['exclude_tag_filter']) && missing_filter_value?(merged['exclude_tag_filters'])
          merged['exclude_tag_filter'] = DEFAULT_EXCLUDED_TAGS
        end

        merged
      end

      def missing_filter_value?(value)
        value.nil? || value == '' || value == []
      end

      def stringify_keys(value)
        return {} if value.nil?

        value.each_with_object({}) do |(key, inner_value), result|
          result[key.to_s] = inner_value
        end
      end

      def stringify_filter_value(value)
        value.is_a?(Array) ? value.join(',') : value.to_s
      end

      def parse_dialog_payload(payload)
        return stringify_keys(payload) if payload.is_a?(Hash)

        raw = payload.to_s
        decoded = URI.decode_www_form_component(raw)
        parsed = JSON.parse(decoded)
        stringify_keys(parsed)
      rescue StandardError
        {}
      end

      def default_report_filename(view, preset, extension)
        base = (VIEW_DEFINITIONS[normalize_string(view)] || VIEW_DEFINITIONS['quantities'])['filename']
        parts = [normalize_string(preset), base].compact.reject(&:empty?)
        "#{parts.join('_')}.#{extension}"
      end

      def resolve_locale(value)
        locale = normalize_string(value)
        return 'bilingual' if locale.nil?
        return locale if %w[th en bilingual].include?(locale)

        'bilingual'
      end

      def localized_text(text, locale = nil)
        locale = resolve_locale(locale)
        raw = text.to_s
        parts = raw.split(' / ', 2)
        return raw if parts.length < 2

        case locale
        when 'th' then parts[1]
        when 'en' then parts[0]
        else raw
        end
      end

      def format_metric_number(value, unit)
        return '' if value.nil?

        "#{format('%.3f', value.to_f)} #{unit}"
      end

      def layer_display_name(layer)
        layer.respond_to?(:display_name) ? layer.display_name.to_s : layer.name.to_s
      end

      def material_display_name(material)
        material.respond_to?(:display_name) ? material.display_name.to_s : material.name.to_s
      end

      def normalize_group_value(value)
        blank?(value) ? 'Unspecified' : value.to_s
      end

      def csv_escape(value)
        text = value.nil? ? '' : value.to_s
        %("#{text.gsub('"', '""')}")
      end

      def sum_numeric(items, key)
        items.reduce(0.0) do |sum, item|
          value = item[key]
          value.nil? ? sum : sum + value.to_f
        end
      end

      def units_summary
        {
          'dimensions' => 'bounding box, meters in reports and millimeters in display text',
          'lengthM' => 'meters',
          'widthM' => 'meters',
          'heightM' => 'meters',
          'surfaceAreaM2' => 'square meters',
          'volumeM3' => 'cubic meters',
          'estimatedWeightKg' => 'kilograms'
        }
      end

      def inches_to_meters(value)
        value.to_f * INCH_TO_METER
      end

      def inches_to_millimeters(value)
        value.to_f * INCH_TO_MILLIMETER
      end

      def volume_to_m3(value)
        return nil if value.nil?
        value.to_f * CUBIC_INCH_TO_CUBIC_METER
      end

      def square_inches_to_square_meters(value)
        return nil if value.nil?
        value.to_f * SQUARE_INCH_TO_SQUARE_METER
      end

      def write_excel_table(path, sheet_name, rows)
        File.write(path, excel_xml_workbook([{ name: sheet_name, rows: rows }]))
      end

      def write_excel_workbook(path, sheets)
        File.write(path, excel_xml_workbook(sheets))
      end

      def excel_xml_workbook(sheets)
        worksheet_xml = sheets.map do |sheet|
          rows = sheet[:rows] || []
          headers = rows.empty? ? [] : rows.first.keys
          body_rows = rows.map { |row| "<Row>#{headers.map { |header| excel_cell(row[header]) }.join}</Row>" }.join
          <<-XML
  <Worksheet ss:Name="#{xml_escape(sheet[:name].to_s)}">
    <Table>
      <Row>#{headers.map { |header| excel_cell(header) }.join}</Row>
      #{body_rows}
    </Table>
  </Worksheet>
          XML
        end.join("\n")

        <<-XML
<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
#{worksheet_xml}
</Workbook>
        XML
      end

      def excel_cell(value)
        text = format_dialog_value(value)
        type = numeric_text?(text) ? 'Number' : 'String'
        "<Cell><Data ss:Type=\"#{type}\">#{xml_escape(text)}</Data></Cell>"
      end

      def numeric_text?(text)
        !!(/\A-?\d+(\.\d+)?\z/ =~ text.to_s)
      end

      def xml_escape(value)
        html_escape(value)
      end

      def resolve_density(args)
        preset = normalize_string(args['density_preset'])
        direct_density = numeric_or_nil(args['density_kg_m3'] || args['density'])
        density = direct_density
        density = DENSITY_PRESETS[preset.downcase] if density.nil? && preset
        [density, preset]
      end

      def density_info_for_entity(entity, options)
        if options[:density_kg_m3]
          preset = options[:density_preset] || 'custom'
          return { density_preset: preset, density_kg_m3: options[:density_kg_m3].to_f }
        end

        infer_density_for_entity(entity)
      end

      def infer_density_for_entity(entity)
        haystack = [
          entity_material_name(entity),
          entity_tag_name(entity),
          entity_name(entity),
          entity_definition_name(entity)
        ].compact.join(' | ').downcase

        if matches_density_keywords?(haystack, %w[steel เหล็ก plate pipe rb rebar lifting rigging sling shackle])
          { density_preset: 'steel', density_kg_m3: DENSITY_PRESETS['steel'] }
        elsif matches_density_keywords?(haystack, %w[rc concrete footing beam column pile slab wall ฐานราก คาน เสา ผนัง])
          { density_preset: 'reinforced_concrete', density_kg_m3: DENSITY_PRESETS['reinforced_concrete'] }
        elsif matches_density_keywords?(haystack, %w[timber wood ไม้])
          { density_preset: 'timber', density_kg_m3: DENSITY_PRESETS['timber'] }
        elsif matches_density_keywords?(haystack, %w[aluminum aluminium อลูมิเนียม])
          { density_preset: 'aluminum', density_kg_m3: DENSITY_PRESETS['aluminum'] }
        else
          { density_preset: nil, density_kg_m3: nil }
        end
      end

      def matches_density_keywords?(haystack, keywords)
        keywords.any? { |keyword| haystack.include?(keyword.downcase) }
      end

      def estimated_weight_kg(volume_in_cubic_inches, density_kg_m3)
        return nil if volume_in_cubic_inches.nil? || density_kg_m3.nil?
        volume_in_cubic_inches.to_f * CUBIC_INCH_TO_CUBIC_METER * density_kg_m3.to_f
      end

      def write_result(command_id, result)
        return if blank?(command_id)
        write_json_atomically(File.join(RESULTS_DIR, "#{command_id}.json"), result)
      end

      def write_json_atomically(path, object)
        temp_path = File.join(Dir.tmpdir, "sketchup_mcp_#{Process.pid}_#{Time.now.to_f}.json")
        File.write(temp_path, JSON.pretty_generate(object))
        FileUtils.mv(temp_path, path)
      ensure
        File.delete(temp_path) if defined?(temp_path) && File.exist?(temp_path)
      end

      def safe_move_to_failed(path)
        return unless path && File.exist?(path)
        FileUtils.mv(path, File.join(FAILED_DIR, File.basename(path)))
      rescue StandardError
        File.delete(path) if File.exist?(path)
      end

      def safe_extract_command_id(path)
        return nil if blank?(path)
        File.basename(path, '.json')
      end

      def error_result(error)
        { 'ok' => false, 'error' => format_error(error), 'completedAt' => Time.now.utc.iso8601 }
      end

      def format_error(error)
        "#{error.class}: #{error.message}"
      end

      def blank?(value)
        value.nil? || value.to_s.strip.empty?
      end

      def integer_or_default(value, default)
        value.nil? ? default : value.to_i
      end

      def integer_or_nil(value)
        value.nil? || blank?(value) ? nil : value.to_i
      end

      def numeric_or_default(value, default)
        value.nil? ? default : value.to_f
      end

      def numeric_or_nil(value)
        value.nil? || blank?(value) ? nil : value.to_f
      end

      def truthy?(value, default)
        return default if value.nil?
        return value if value == true || value == false
        %w[1 true yes on].include?(value.to_s.strip.downcase)
      end

      def scalar_value?(value)
        !value.is_a?(Array) && !value.is_a?(Hash)
      end

      def format_dialog_value(value)
        case value
        when Array then value.join(' | ')
        when Hash then value.map { |k, v| "#{k}: #{v}" }.join(', ')
        else value.nil? ? '' : value.to_s
        end
      end

      def html_escape(value)
        value.to_s.gsub('&', '&amp;').gsub('<', '&lt;').gsub('>', '&gt;').gsub('"', '&quot;')
      end

      def js_escape(value)
        value.to_s.gsub('\\', '\\\\').gsub("'", "\\\\'")
      end

      def label_for_key(key, locale = nil)
        localized_text(FIELD_LABELS[key.to_s] || pretty_label(key), locale)
      end

      def labeled_hash(row, ordered_keys, locale = nil)
        ordered_keys.each_with_object({}) do |key, result|
          result[label_for_key(key, locale)] = export_cell_value(row, key)
        end
      end

      def export_cell_value(row, key)
        value = row[key]
        key.to_s == 'types' ? Array(value).join(' | ') : value
      end

      def csv_from_rows(rows, ordered_keys, locale = nil)
        lines = [ordered_keys.map { |key| csv_escape(label_for_key(key, locale)) }.join(',')]
        rows.each do |row|
          lines << ordered_keys.map { |key| csv_escape(export_cell_value(row, key)) }.join(',')
        end
        lines.join("\n")
      end

      def labeled_rows(rows, ordered_keys, locale = nil)
        rows.map { |row| labeled_hash(row, ordered_keys, locale) }
      end

      def load_template(name)
        @template_cache ||= {}
        return @template_cache[name] if @template_cache.key?(name)

        path = File.join(TEMPLATE_ROOT, name)
        @template_cache[name] = File.read(path)
      end

      def render_template(name, replacements = {})
        template = load_template(name).dup
        replacements.each do |key, value|
          template.gsub!("{{#{key}}}", value.to_s)
        end
        template
      end

      def pretty_label(value)
        text = value.to_s.gsub(/([a-z])([A-Z])/, '\1 \2').tr('_', ' ')
        text.split.map { |part| part.upcase == part ? part : part.capitalize }.join(' ')
      end
    end
  end
end

module Codex
  module SketchUpMCPBridge
    module UIHelpers
      def show_component_quantities_dialog(args = {})
        result = summarize_component_quantities(args)
        show_result_dialog('Component Quantities', result, resolve_locale(stringify_keys(args)['locale']))
      end

      def show_report_builder_dialog(args = {})
        state = build_report_builder_state(args)
        dialog = ensure_report_builder_dialog
        dialog_title = report_builder_title(state)

        if @report_builder_dialog_kind == :html
          dialog.set_title(dialog_title) if dialog.respond_to?(:set_title)
        else
          dialog.set_size(1180, 780) if dialog.respond_to?(:set_size)
        end

        dialog.set_html(report_builder_dialog_html(state))
        dialog.show
      end

      def show_selection_metrics_dialog(args = {})
        result = get_selection_metrics(args)
        show_result_dialog('Selection Metrics', result, resolve_locale(stringify_keys(args)['locale']))
      end

      def show_component_list_dialog(args = {})
        result = list_components(args)
        show_result_dialog('Component List', result, resolve_locale(stringify_keys(args)['locale']))
      end

      def show_tag_totals_dialog(args = {})
        result = summarize_tag_totals(args)
        show_result_dialog('Tag Totals', result, resolve_locale(stringify_keys(args)['locale']))
      end

      def show_boq_thai_dialog(args = {})
        result = summarize_boq_thai(args)
        show_result_dialog('BOQ THAI Preview', {
          'totals' => result['totals'],
          'rows' => result['rows'],
          'unmatchedItems' => result['unmatchedItems']
        }, 'th')
      end

      def show_boq_thai_manager_dialog(args = {})
        state = boq_thai_manager_state(args)
        dialog = ensure_boq_thai_manager_dialog
        dialog.set_html(boq_thai_manager_html(state))
        dialog.show
      end

      def show_preset_quantities_dialog(preset, args = {})
        merged = stringify_keys(args).merge('preset' => preset)
        result = summarize_component_quantities(merged)
        locale = resolve_locale(merged['locale'])
        preset_label = localized_text(PRESET_DEFINITIONS.fetch(preset.to_s, {})['label'], locale) || preset.to_s.capitalize
        title = "#{preset_label} - #{localized_text(VIEW_DEFINITIONS['quantities']['title'], locale)}"
        show_result_dialog(title, result, locale)
      end

      def show_result_dialog(title, result, locale = nil)
        html = dialog_html(title, result, locale)

        if defined?(UI::HtmlDialog)
          @result_dialog ||= UI::HtmlDialog.new(
            dialog_title: title,
            preferences_key: 'codex.sketchup_mcp_bridge.result_dialog',
            scrollable: true,
            resizable: true,
            width: 980,
            height: 720,
            style: UI::HtmlDialog::STYLE_DIALOG
          )
          @result_dialog.set_html(html)
          @result_dialog.show
        else
          dialog = UI::WebDialog.new(title, true, 'codex.sketchup_mcp_bridge.result_dialog', 980, 720, 100, 100, true)
          dialog.set_html(html)
          dialog.show
          @result_dialog = dialog
        end
      end

      def ensure_report_builder_dialog
        return @report_builder_dialog if defined?(@report_builder_dialog) && @report_builder_dialog

        if defined?(UI::HtmlDialog)
          @report_builder_dialog_kind = :html
          @report_builder_dialog = UI::HtmlDialog.new(
            dialog_title: 'SketchUp Report Builder',
            preferences_key: 'codex.sketchup_mcp_bridge.report_builder_dialog',
            scrollable: true,
            resizable: true,
            width: 1180,
            height: 780,
            style: UI::HtmlDialog::STYLE_DIALOG
          )
          @report_builder_dialog.add_action_callback('runReport') do |_context, payload|
            update_report_builder_dialog(payload)
          end
          @report_builder_dialog.add_action_callback('exportReport') do |_context, payload|
            export_report_builder_dialog(payload)
          end
        else
          @report_builder_dialog_kind = :web
          @report_builder_dialog = UI::WebDialog.new(
            'SketchUp Report Builder',
            true,
            'codex.sketchup_mcp_bridge.report_builder_dialog',
            1180,
            780,
            80,
            80,
            true
          )
          @report_builder_dialog.add_action_callback('runReport') do |_dialog, payload|
            update_report_builder_dialog(payload)
          end
          @report_builder_dialog.add_action_callback('exportReport') do |_dialog, payload|
            export_report_builder_dialog(payload)
          end
        end

        @report_builder_dialog
      end

      def ensure_boq_thai_manager_dialog
        return @boq_thai_manager_dialog if defined?(@boq_thai_manager_dialog) && @boq_thai_manager_dialog

        if defined?(UI::HtmlDialog)
          @boq_thai_manager_dialog = UI::HtmlDialog.new(
            dialog_title: 'BOQ Thai Manager',
            preferences_key: 'codex.sketchup_mcp_bridge.boq_thai_manager',
            scrollable: true,
            resizable: true,
            width: 1280,
            height: 820,
            style: UI::HtmlDialog::STYLE_DIALOG
          )
          add_boq_thai_manager_callbacks(@boq_thai_manager_dialog)
        else
          @boq_thai_manager_dialog = UI::WebDialog.new(
            'BOQ Thai Manager',
            true,
            'codex.sketchup_mcp_bridge.boq_thai_manager',
            1280,
            820,
            80,
            80,
            true
          )
          add_boq_thai_manager_callbacks(@boq_thai_manager_dialog)
        end

        @boq_thai_manager_dialog
      end

      def add_boq_thai_manager_callbacks(dialog)
        dialog.add_action_callback('boqThaiPreview') { |_context, payload| update_boq_thai_manager_dialog(payload) }
        dialog.add_action_callback('boqThaiChooseGlobal') { |_context, payload| choose_boq_thai_global_rules(payload) }
        dialog.add_action_callback('boqThaiChooseProject') { |_context, payload| choose_boq_thai_project_overrides(payload) }
        dialog.add_action_callback('boqThaiSaveRule') { |_context, payload| save_boq_thai_project_rule(payload) }
        dialog.add_action_callback('boqThaiExport') { |_context, payload| export_boq_thai_manager_report(payload) }
        dialog.add_action_callback('boqThaiExportUnmatched') { |_context, payload| export_boq_thai_manager_unmatched(payload) }
      end

      def update_boq_thai_manager_dialog(payload)
        show_boq_thai_manager_dialog(parse_dialog_payload(payload))
      rescue StandardError => e
        UI.messagebox("BOQ preview failed:\n#{format_error(e)}")
      end

      def choose_boq_thai_global_rules(payload)
        args = parse_dialog_payload(payload)
        path = UI.openpanel('Choose Global Price Library', Dir.home, 'CSV Files|*.csv||')
        args['global_price_rules_path'] = path if path
        show_boq_thai_manager_dialog(args)
      end

      def choose_boq_thai_project_overrides(payload)
        args = parse_dialog_payload(payload)
        path = UI.savepanel('Choose Project Overrides', Dir.home, File.basename(boq_project_overrides_path(args)))
        args['project_overrides_path'] = path if path
        show_boq_thai_manager_dialog(args)
      end

      def save_boq_thai_project_rule(payload)
        args = parse_dialog_payload(payload)
        result = append_boq_project_override(args)
        UI.messagebox("Saved project override:\n#{result['path']}")
        show_boq_thai_manager_dialog(args)
      rescue StandardError => e
        UI.messagebox("Save override failed:\n#{format_error(e)}")
      end

      def export_boq_thai_manager_report(payload)
        args = parse_dialog_payload(payload)
        export_format = normalize_string(args.delete('export_format')) || 'xls'
        extension = export_format == 'html' ? 'html' : 'xls'
        path = UI.savepanel('Export BOQ Thai', Dir.home, "boq_thai.#{extension}")
        return if blank?(path)

        args['path'] = path
        result = export_boq_thai_report(args)
        UI.messagebox("Exported BOQ Thai:\n#{result['path']}")
        show_boq_thai_manager_dialog(args)
      rescue StandardError => e
        UI.messagebox("Export BOQ failed:\n#{format_error(e)}")
      end

      def export_boq_thai_manager_unmatched(payload)
        args = parse_dialog_payload(payload)
        path = UI.savepanel('Export Unmatched Template', Dir.home, 'boq_unmatched_template.csv')
        return if blank?(path)

        args['path'] = path
        result = export_boq_unmatched_template(args)
        UI.messagebox("Exported unmatched template:\n#{result['path']}")
        show_boq_thai_manager_dialog(args)
      rescue StandardError => e
        UI.messagebox("Export unmatched template failed:\n#{format_error(e)}")
      end

      def update_report_builder_dialog(payload)
        state = build_report_builder_state(parse_dialog_payload(payload))
        ensure_report_builder_dialog.set_html(report_builder_dialog_html(state))
      end

      def export_report_builder_dialog(payload)
        args = parse_dialog_payload(payload)
        export_format = normalize_string(args.delete('export_format')) || 'csv'
        extension = export_format == 'excel' ? 'xls' : export_format
        default_name = default_report_filename(args['view'], args['preset'], extension)
        path = UI.savepanel('Export Report', Dir.home, default_name)
        return if blank?(path)

        args['path'] = path
        result = export_report_for_view(args['view'], args)

        UI.messagebox("Exported report to:\n#{result['path']}")
        update_report_builder_dialog(args)
      rescue StandardError => e
        UI.messagebox("Export failed:\n#{format_error(e)}")
      end

      def report_builder_dialog_html(state)
        args = state['args']
        preset = normalize_string(args['preset'])
        current_view = state['view']
        locale = resolve_locale(args['locale'])

        render_template(
          'report_builder.html',
          'TITLE' => html_escape(report_builder_title(state)),
          'UNITS_HELP' => html_escape(localized_text('Dimensions in meters, surface area in m2, volume in m3, weight in kg. / หน่วยหลักเป็นเมตร ตารางเมตร ลูกบาศก์เมตร และกิโลกรัม', locale)),
          'PRESET_BUTTONS' => preset_buttons_html(preset, locale),
          'VIEW_BUTTONS' => view_buttons_html(current_view, locale),
          'CURRENT_VIEW' => html_escape(current_view),
          'CURRENT_PRESET' => html_escape(preset.to_s),
          'TAG_FILTER' => html_escape(stringify_filter_value(args['tag_filter'])),
          'NAME_FILTER' => html_escape(args['name_filter'].to_s),
          'EXCLUDE_TAG_FILTER' => html_escape(stringify_filter_value(args['exclude_tag_filter'] || args['exclude_tag_filters'])),
          'DENSITY_OPTIONS' => density_options_html(args['density_preset'], locale),
          'LOCALE_OPTIONS' => locale_options_html(locale),
          'SHORT_EDGE_THRESHOLD_MM' => html_escape((args['short_edge_threshold_mm'] || 5).to_s),
          'SOLID_ONLY_CHECKED' => truthy?(args['solid_only'], false) ? 'checked' : '',
          'SELECTED_ONLY_CHECKED' => truthy?(args['selected_only'], false) ? 'checked' : '',
          'INCLUDE_HIDDEN_CHECKED' => truthy?(args['include_hidden'], true) ? 'checked' : '',
          'HELP_TEXT' => html_escape(localized_text('Presets automatically choose structural tags, exclude grid and dimension guides, and default to reinforced concrete weight. / preset จะช่วยเลือกแท็กโครงสร้าง ตัด GRID LINE กับ DIMENSIONS และตั้งน้ำหนักเริ่มต้นให้เป็นคอนกรีตเสริมเหล็ก', locale)),
          'SUMMARY_HTML' => report_builder_summary_html(state['result'], locale),
          'RESULT_HTML' => render_result_sections(state['result'], locale)
        )
      end

      def boq_thai_manager_html(state)
        args = state['args']
        result = state['result']
        totals = result['totals'] || {}
        render_template(
          'boq_thai_manager.html',
          'GLOBAL_PATH' => html_escape(state['globalPath'].to_s),
          'PROJECT_PATH' => html_escape(state['projectPath'].to_s),
          'SELECTED_ONLY' => truthy?(args['selected_only'], false) ? 'checked' : '',
          'SOLID_ONLY' => truthy?(args['solid_only'], false) ? 'checked' : '',
          'TAG_FILTER' => html_escape(stringify_filter_value(args['tag_filter'])),
          'NAME_FILTER' => html_escape(args['name_filter'].to_s),
          'SUMMARY_HTML' => [
            boq_metric_html('BOQ rows', result['count']),
            boq_metric_html('Unmatched', totals['unmatchedCount']),
            boq_metric_html('Material', totals['materialAmount']),
            boq_metric_html('Labor', totals['laborAmount']),
            boq_metric_html('Total', totals['totalAmount'])
          ].join,
          'WARNINGS_HTML' => Array(result['warnings']).map { |warning| "<div>#{html_escape(warning)}</div>" }.join,
          'BOQ_TABLE' => boq_table_html(result['rows'], BOQ_THAI_HEADERS),
          'UNMATCHED_TABLE' => boq_unmatched_table_html(result['unmatchedItems'])
        )
      end

      def boq_metric_html(label, value)
        "<div class=\"metric\"><div class=\"label\">#{html_escape(label)}</div><div class=\"value\">#{html_escape(value.to_s)}</div></div>"
      end

      def boq_table_html(rows, headers)
        return '<div class="panel">No rows</div>' if rows.empty?

        body = rows.first(300).map do |row|
          "<tr>#{headers.map { |header| "<td>#{html_escape(format_dialog_value(row[header]))}</td>" }.join}</tr>"
        end.join
        "<div class=\"table-wrap\"><table><thead><tr>#{headers.map { |header| "<th>#{html_escape(header)}</th>" }.join}</tr></thead><tbody>#{body}</tbody></table></div>"
      end

      def boq_unmatched_table_html(rows)
        return '<div class="panel">No unmatched items</div>' if rows.empty?

        headers = UNMATCHED_HEADERS
        body = rows.first(300).map do |row|
          select = "<span class=\"select-link\" onclick=\"fillRule('#{js_escape(row['suggested_match_type'])}', '#{js_escape(row['suggested_match_value'])}', '#{js_escape(row['category'])}', '#{js_escape(row['definitionName'] || row['name'])}', '#{js_escape(suggested_quantity_source(row['quantity_hint']))}')\">use</span>"
          cells = headers.map { |header| "<td>#{html_escape(format_dialog_value(row[header]))}</td>" }.join
          "<tr><td>#{select}</td>#{cells}</tr>"
        end.join
        "<div class=\"table-wrap\"><table><thead><tr><th>Assign</th>#{headers.map { |header| "<th>#{html_escape(header)}</th>" }.join}</tr></thead><tbody>#{body}</tbody></table></div>"
      end

      def report_builder_summary_html(result, locale = nil)
        cards = []
        cards << summary_card_html(localized_text('Count / จำนวนรายการ', locale), result['count'])
        if result['totals'].is_a?(Hash)
          cards << summary_card_html(localized_text('Instances / จำนวนชิ้น', locale), result['totals']['instances'])
          cards << summary_card_html(localized_text('Volume / ปริมาตร', locale), format_metric_number(result['totals']['totalVolumeM3'] || result['totals']['volume'], 'm3'))
          cards << summary_card_html(localized_text('Surface Area / พื้นที่ผิว', locale), format_metric_number(result['totals']['totalSurfaceAreaM2'], 'm2'))
          cards << summary_card_html(localized_text('Weight / น้ำหนัก', locale), format_metric_number(result['totals']['estimatedWeightKg'], 'kg'))
          cards << summary_card_html(localized_text('Edges / เส้น', locale), result['totals']['edges']) if result['totals'].key?('edges')
          cards << summary_card_html(localized_text('Length / ความยาว', locale), format_metric_number(result['totals']['totalLengthM'], 'm')) if result['totals'].key?('totalLengthM')
        elsif result['totalVolumeM3'] || result['totalEstimatedWeightKg']
          cards << summary_card_html(localized_text('Volume / ปริมาตร', locale), format_metric_number(result['totalVolumeM3'], 'm3'))
          cards << summary_card_html(localized_text('Surface Area / พื้นที่ผิว', locale), format_metric_number(result['totalSurfaceAreaM2'], 'm2'))
          cards << summary_card_html(localized_text('Weight / น้ำหนัก', locale), format_metric_number(result['totalEstimatedWeightKg'], 'kg'))
        elsif result['summary'].is_a?(Hash)
          cards << summary_card_html(localized_text('Components / ชิ้นงาน', locale), result['summary']['components']) if result['summary'].key?('components')
          cards << summary_card_html(localized_text('Edges / เส้น', locale), result['summary']['edges']) if result['summary'].key?('edges')
          cards << summary_card_html(localized_text('Length / ความยาว', locale), format_metric_number(result['summary']['totalEdgeLengthM'], 'm')) if result['summary'].key?('totalEdgeLengthM')
          cards << summary_card_html(localized_text('Short Edges / เส้นสั้น', locale), result['summary']['shortEdges']) if result['summary'].key?('shortEdges')
          cards << summary_card_html(localized_text('Non-solids / ไม่เป็น solid', locale), result['summary']['nonSolids']) if result['summary'].key?('nonSolids')
        end
        "<div class=\"summary\">#{cards.join}</div>"
      end

      def summary_card_html(label, value)
        "<div class=\"card\"><div class=\"label\">#{html_escape(label)}</div><div class=\"value\">#{html_escape(value.to_s)}</div></div>"
      end

      def preset_button_html(label, value, current)
        active = current.to_s == value.to_s
        "<button class=\"preset #{active ? 'active' : ''}\" onclick=\"activatePreset('#{js_escape(value)}')\">#{html_escape(label)}</button>"
      end

      def preset_buttons_html(current, locale = nil)
        ['beam', 'column', 'footing', ''].map do |value|
          label = localized_text(PRESET_DEFINITIONS.fetch(value, {})['label'], locale) || value.to_s
          preset_button_html(label, value, current)
        end.join
      end

      def view_button_html(label, value, current)
        active = current.to_s == value.to_s
        "<button class=\"view #{active ? 'active' : ''}\" onclick=\"activateView('#{js_escape(value)}')\">#{html_escape(label)}</button>"
      end

      def view_buttons_html(current, locale = nil)
        %w[quantities boq_thai tag_totals components categories edge_metrics model_audit].map do |value|
          label = localized_text(VIEW_DEFINITIONS.fetch(value, {})['label'], locale) || value
          view_button_html(label, value, current)
        end.join
      end

      def density_option_html(value, label, current)
        selected = current.to_s == value.to_s ? 'selected' : ''
        "<option value=\"#{html_escape(value)}\" #{selected}>#{html_escape(label)}</option>"
      end

      def density_options_html(current, locale = nil)
        DENSITY_OPTION_DEFINITIONS.map do |value, label|
          density_option_html(value, localized_text(label, locale), current)
        end.join
      end

      def locale_options_html(current)
        [
          ['bilingual', 'Thai + English / ไทย + อังกฤษ'],
          ['th', 'Thai / ไทย'],
          ['en', 'English']
        ].map do |value, label|
          selected = current.to_s == value.to_s ? 'selected' : ''
          "<option value=\"#{html_escape(value)}\" #{selected}>#{html_escape(label)}</option>"
        end.join
      end

      def dialog_html(title, result, locale = nil)
        render_template(
          'result_dialog.html',
          'TITLE' => html_escape(title),
          'RESULT_HTML' => render_result_sections(result, locale)
        )
      end

      def render_result_sections(result, locale = nil)
        scalar_entries = result.select { |_, value| scalar_value?(value) }
        hash_entries = result.select { |_, value| value.is_a?(Hash) }
        array_entries = result.select { |_, value| value.is_a?(Array) }

        sections = []
        unless scalar_entries.empty?
          sections << "<div class=\"card\"><div class=\"grid\">#{scalar_entries.map { |key, value| render_kv(key, value, locale) }.join}</div></div>"
        end
        hash_entries.each do |key, value|
          sections << "<h2>#{html_escape(label_for_key(key, locale))}</h2><div class=\"card\"><div class=\"grid\">#{value.map { |sub_key, sub_value| render_kv(sub_key, sub_value, locale) }.join}</div></div>"
        end
        array_entries.each do |key, value|
          sections << "<h2>#{html_escape(label_for_key(key, locale))}</h2>#{render_array_table(value, locale)}"
        end

        sections.join
      end

      def render_kv(key, value, locale = nil)
        "<div class=\"kv\"><div class=\"label\">#{html_escape(label_for_key(key, locale))}</div><div class=\"value\">#{html_escape(format_dialog_value(value))}</div></div>"
      end

      def render_array_table(rows, locale = nil)
        return '<div class="card">No rows</div>' if rows.empty?

        if rows.first.is_a?(Hash)
          headers = rows.map(&:keys).flatten.uniq
          body = rows.first(500).map do |row|
            "<tr>#{headers.map { |header| "<td>#{html_escape(format_dialog_value(row[header]))}</td>" }.join}</tr>"
          end.join
          "<div class=\"table-wrap\"><table><thead><tr>#{headers.map { |header| "<th>#{html_escape(label_for_key(header, locale))}</th>" }.join}</tr></thead><tbody>#{body}</tbody></table></div>"
        else
          "<pre>#{html_escape(rows.map { |row| format_dialog_value(row) }.join("\n"))}</pre>"
        end
      end
    end
  end
end

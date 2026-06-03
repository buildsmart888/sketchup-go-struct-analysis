module GOCarbonCredit
  module UIHelpers
    def show_carbon_summary_dialog(args = {})
      result = calculate_carbon(args)
      html = build_summary_html(result)
      show_dialog('GO Carbon Credit - Summary', html, 1000, 750)
    end

    def show_carbon_manager_dialog(args = {})
      result = calculate_carbon(args)
      html = build_manager_html(result, args)
      dialog = ensure_carbon_manager_dialog
      dialog.set_html(html)
      dialog.show
    end

    def apply_heatmap_with_message(args = {})
      r = apply_heatmap(args)
      UI.messagebox("🎨 Applied carbon heatmap to #{r['coloredCount']} components.\nMax: #{r['maxKgCO2e']} kgCO₂e")
    rescue => e
      UI.messagebox("Failed to apply heatmap: #{e.message}")
    end

    def remove_heatmap_with_message(args = {})
      r = remove_heatmap(args)
      UI.messagebox("🧹 Removed #{r['removedCount']} heatmap materials.")
    rescue => e
      UI.messagebox("Failed to remove heatmap: #{e.message}")
    end

    def export_carbon_report_dialog(args = {})
      path = UI.savepanel('Export Carbon Report', Dir.home, 'carbon_report.xls')
      return if blank?(path)
      r = export_carbon_excel(args.merge('path' => path))
      UI.messagebox("📊 Exported: #{r['path']}\n#{r['sheetCount']} sheets")
    rescue => e
      UI.messagebox("Export failed: #{e.message}")
    end

    def export_carbon_json_dialog(args = {})
      path = UI.savepanel('Export Carbon JSON', Dir.home, 'carbon_result.json')
      return if blank?(path)
      r = export_carbon_json(args.merge('path' => path))
      UI.messagebox("📄 Exported: #{r['path']}")
    rescue => e
      UI.messagebox("Export failed: #{e.message}")
    end

    private

    def show_dialog(title, html, w, h)
      if defined?(UI::HtmlDialog)
        @result_dialog ||= UI::HtmlDialog.new(
          dialog_title: title, preferences_key: 'go_carbon_credit.result',
          scrollable: true, resizable: true, width: w, height: h,
          style: UI::HtmlDialog::STYLE_DIALOG
        )
        @result_dialog.set_html(html)
        @result_dialog.show
      else
        d = UI::WebDialog.new(title, true, 'go_carbon_credit.result', w, h, 80, 80, true)
        d.set_html(html)
        d.show
        @result_dialog = d
      end
    end

    def ensure_carbon_manager_dialog
      return @carbon_manager_dialog if defined?(@carbon_manager_dialog) && @carbon_manager_dialog

      if defined?(UI::HtmlDialog)
        @carbon_manager_dialog = UI::HtmlDialog.new(
          dialog_title: 'GO Carbon Credit Manager',
          preferences_key: 'go_carbon_credit.manager',
          scrollable: true, resizable: true, width: 1100, height: 800,
          style: UI::HtmlDialog::STYLE_DIALOG
        )
        add_manager_callbacks(@carbon_manager_dialog)
      else
        @carbon_manager_dialog = UI::WebDialog.new(
          'GO Carbon Credit Manager', true, 'go_carbon_credit.manager', 1100, 800, 80, 80, true
        )
        add_manager_callbacks(@carbon_manager_dialog)
      end

      @carbon_manager_dialog
    end

    def add_manager_callbacks(dialog)
      # HtmlDialog uses a different signature than WebDialog
      if defined?(UI::HtmlDialog) && dialog.is_a?(UI::HtmlDialog)
        dialog.add_action_callback('updateManager') { |_context, payload| update_manager_dialog(payload) }
        dialog.add_action_callback('applyHeatmap')  { |_context, _p| apply_heatmap_with_message }
        dialog.add_action_callback('removeHeatmap') { |_context, _p| remove_heatmap_with_message }
        dialog.add_action_callback('exportExcel')   { |_context, _p| export_carbon_report_dialog }
      else
        dialog.add_action_callback('updateManager') { |_dialog, payload| update_manager_dialog(payload) }
        dialog.add_action_callback('applyHeatmap')  { |_dialog, _p| apply_heatmap_with_message }
        dialog.add_action_callback('removeHeatmap') { |_dialog, _p| remove_heatmap_with_message }
        dialog.add_action_callback('exportExcel')   { |_dialog, _p| export_carbon_report_dialog }
      end
    end
    
    def update_manager_dialog(payload_str)
      args = parse_payload(payload_str)
      show_carbon_manager_dialog(args)
    end
    
    def parse_payload(payload)
      return {} if blank?(payload)
      
      if payload.is_a?(Hash)
        args = {}
        payload.each { |k, v| args[k.to_s] = v }
        return args
      end
      
      begin
        # Attempt to parse as JSON or query string if it's a string
        if payload.start_with?('{')
          parsed = JSON.parse(payload)
          args = {}
          parsed.each { |k, v| args[k.to_s] = v }
          return args
        end
      rescue
      end
      
      {}
    end

    def build_summary_html(result)
      template_path = File.join(TEMPLATE_ROOT, 'carbon_manager.html')
      html = File.read(template_path)
      
      # Substitute simple values
      html.gsub!('{{TOTAL_KG}}', format_number(result['summary']['totalKgCO2e'], 0))
      html.gsub!('{{TOTAL_TCO2E}}', format_number(result['summary']['totalTCO2e'], 1))
      html.gsub!('{{PER_M2}}', format_number(result['summary']['carbonPerM2'], 1))
      
      rating = result['summary']['rating']
      html.gsub!('{{RATING}}', rating)
      
      color_class = case rating
        when 'A' then '#00B43C'
        when 'B' then '#78C828'
        when 'C' then '#FFDC00'
        when 'D' then '#FF8C00'
        when 'E' then '#DC2828'
        else '#888'
      end
      html.gsub!('{{RATING_COLOR}}', color_class)
      
      html.gsub!('{{MATCHED_COUNT}}', result['summary']['matchedCount'].to_s)
      html.gsub!('{{UNMATCHED_COUNT}}', result['summary']['unmatchedCount'].to_s)
      
      # Build Materials Bar Chart
      mat_html = ''
      result['byMaterial'].first(5).each do |m|
        mat_html << "<div style='margin-bottom: 8px;'>"
        mat_html << "<div style='display: flex; justify-content: space-between; font-size: 13px;'>"
        mat_html << "<span>#{m['name']}</span><span>#{m['percent']}% (#{format_number(m['kgCO2e']/1000.0, 1)} tCO₂e)</span>"
        mat_html << "</div>"
        mat_html << "<div style='width: 100%; background: #333; height: 12px; border-radius: 6px; overflow: hidden; margin-top: 4px;'>"
        mat_html << "<div style='width: #{m['percent']}%; background: #4caf50; height: 100%;'></div>"
        mat_html << "</div></div>"
      end
      html.gsub!('{{MATERIALS_HTML}}', mat_html)
      
      # Unmatched count alert
      unmatched_html = result['summary']['unmatchedCount'] > 0 ? "<div style='background: #5a3; color: white; padding: 10px; border-radius: 4px; margin-top: 15px; border-left: 4px solid #f44336;'>⚠️ #{result['summary']['unmatchedCount']} components missing emission factors</div>" : ""
      html.gsub!('{{UNMATCHED_ALERT}}', unmatched_html)
      
      # Suggestions
      tips_html = ''
      result['suggestions'].each do |tip|
        tips_html << "<div style='background: #2a2a3a; padding: 12px; border-radius: 6px; margin-bottom: 10px;'>"
        tips_html << "<strong style='color: #4caf50;'>💡 #{tip['titleTh']}</strong><br>"
        tips_html << "<span style='font-size: 13px; color: #aaa;'>Potential savings: #{tip['savingKgCO2e']} kgCO₂e</span>"
        tips_html << "</div>"
      end
      html.gsub!('{{SUGGESTIONS_HTML}}', tips_html)
      
      html
    end
    
    def build_manager_html(result, args)
      # Same as summary for now, but in future can embed JS for interactive form
      build_summary_html(result)
    end
  end
end

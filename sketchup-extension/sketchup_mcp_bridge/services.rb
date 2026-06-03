module Codex
  module SketchUpMCPBridge
    module ReportServices
      def build_report_builder_state(args = {})
        merged = apply_filter_defaults(args, true)
        view = normalize_string(merged['view']) || 'quantities'
        result = report_result_for(view, merged)

        {
          'view' => view,
          'args' => merged,
          'result' => result,
          'title' => report_builder_title({ 'view' => view, 'args' => merged })
        }
      end

      def report_builder_title(state)
        preset = normalize_string(state['args']['preset'])
        locale = resolve_locale(state['args']['locale'])
        view_title = localized_text((VIEW_DEFINITIONS[state['view']] || VIEW_DEFINITIONS['quantities'])['title'], locale)
        preset_label = localized_text(PRESET_DEFINITIONS.fetch(preset.to_s, {})['label'], locale)
        preset_label ? "#{preset_label} - #{view_title}" : view_title
      end

      def report_result_for(view, args)
        case normalize_string(view)
        when 'components'
          list_components(args)
        when 'categories'
          summarize_component_categories(args)
        when 'edge_metrics'
          summarize_edge_metrics(args)
        when 'model_audit'
          summarize_model_audit(args)
        when 'boq_thai'
          summarize_boq_thai(args)
        when 'tag_totals'
          summarize_tag_totals(args)
        else
          summarize_component_quantities(args)
        end
      end

      def export_report_for_view(view, args)
        case normalize_string(view)
        when 'components'
          export_component_list(args)
        when 'categories'
          export_component_categories_report(args)
        when 'edge_metrics'
          export_edge_metrics_report(args)
        when 'model_audit'
          export_model_audit_report(args)
        when 'boq_thai'
          export_boq_thai_report(args)
        when 'tag_totals'
          export_tag_totals_report(args)
        else
          export_bom_report(args)
        end
      end
    end
  end
end

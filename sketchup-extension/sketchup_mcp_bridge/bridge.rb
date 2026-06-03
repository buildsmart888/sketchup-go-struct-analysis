module Codex
  module SketchUpMCPBridge
    module Bridge
      def startup
        ensure_queue_dirs
        install_menu
        start_bridge
      rescue StandardError => e
        @last_error = format_error(e)
      end

      def ensure_queue_dirs
        [QUEUE_ROOT, COMMANDS_DIR, RESULTS_DIR, FAILED_DIR].each do |path|
          FileUtils.mkdir_p(path)
        end
      end

      def install_menu
        return if defined?(@menu_installed) && @menu_installed

        menu = UI.menu('Extensions').add_submenu('SketchUp MCP Bridge')
        menu.add_item('Show Queue Root') { UI.messagebox("Queue root:\n#{QUEUE_ROOT}") }
        menu.add_item('Bridge Status') { UI.messagebox(status_text) }
        menu.add_item('Process Queue Now') do
          process_queue
          UI.messagebox('Queue processed.')
        end
        menu.add_separator
        menu.add_item('Show Quantities Dialog') { show_component_quantities_dialog }
        menu.add_item('Open Report Builder') { show_report_builder_dialog }
        menu.add_item('Show Selection Metrics Dialog') { show_selection_metrics_dialog }
        menu.add_item('Show Tag Totals Dialog') { show_tag_totals_dialog }
        menu.add_item('Show Edge Metrics Dialog') { show_result_dialog('Edge Metrics / ตรวจเส้นและความยาว', summarize_edge_metrics({})) }
        menu.add_item('Show Category Summary Dialog') { show_result_dialog('Component Categories / หมวดชิ้นงาน', summarize_component_categories({})) }
        menu.add_item('Show Model Audit Dialog') { show_result_dialog('Model Audit / ตรวจเช็กโมเดล', summarize_model_audit({})) }
        menu.add_item('Show BOQ THAI Preview') { show_boq_thai_dialog }
        menu.add_item('Open BOQ Thai Manager') { show_boq_thai_manager_dialog }

        preset_menu = menu.add_submenu('Preset Reports')
        preset_menu.add_item('Beam Quantities') { show_preset_quantities_dialog('beam') }
        preset_menu.add_item('Column Quantities') { show_preset_quantities_dialog('column') }
        preset_menu.add_item('Footing Quantities') { show_preset_quantities_dialog('footing') }

        @menu_installed = true
      end

      def start_bridge
        return if @bridge_started

        @bridge_timer = UI.start_timer(POLL_SECONDS, true) { process_queue }
        @bridge_started = true
      end

      def status_text
        [
          "Started: #{@bridge_started}",
          "Queue root: #{QUEUE_ROOT}",
          "Last error: #{@last_error || 'none'}"
        ].join("\n")
      end

      def process_queue
        ensure_queue_dirs
        Dir.glob(File.join(COMMANDS_DIR, '*.json')).sort.each { |path| process_command_file(path) }
      rescue StandardError => e
        @last_error = format_error(e)
      end

      def process_command_file(path)
        payload = JSON.parse(File.read(path))
        result = execute_command(payload)
        write_result(payload.fetch('id'), result)
        File.delete(path) if File.exist?(path)
      rescue StandardError => e
        @last_error = format_error(e)
        safe_move_to_failed(path)
        command_id = safe_extract_command_id(path)
        write_result(command_id, error_result(e))
      end

      def execute_command(payload)
        tool = payload.fetch('tool')
        args = payload['args'] || {}
        {
          'id' => payload['id'],
          'ok' => true,
          'data' => dispatch(tool, args),
          'completedAt' => Time.now.utc.iso8601
        }
      end

      def dispatch(tool, args)
        case tool
        when 'ping' then ping
        when 'get_model_summary' then get_model_summary
        when 'list_layers' then list_layers
        when 'list_tags' then list_tags
        when 'list_scenes' then list_scenes
        when 'get_selection_info' then get_selection_info
        when 'list_components' then list_components(args)
        when 'export_component_list' then export_component_list(args)
        when 'get_selection_metrics' then get_selection_metrics(args)
        when 'filter_entities_by_tag' then filter_entities_by_tag(args)
        when 'summarize_component_quantities' then summarize_component_quantities(args)
        when 'export_bom_report' then export_bom_report(args)
        when 'summarize_tag_totals' then summarize_tag_totals(args)
        when 'export_tag_totals_report' then export_tag_totals_report(args)
        when 'summarize_edge_metrics' then summarize_edge_metrics(args)
        when 'export_edge_metrics_report' then export_edge_metrics_report(args)
        when 'summarize_component_categories' then summarize_component_categories(args)
        when 'export_component_categories_report' then export_component_categories_report(args)
        when 'summarize_model_audit' then summarize_model_audit(args)
        when 'export_model_audit_report' then export_model_audit_report(args)
        when 'summarize_boq_thai' then summarize_boq_thai(args)
        when 'export_boq_thai_report' then export_boq_thai_report(args)
        when 'export_boq_unmatched_template' then export_boq_unmatched_template(args)
        when 'append_boq_project_override' then append_boq_project_override(args)
        when 'export_current_view_png' then export_current_view_png(args)
        when 'save_model_copy' then save_model_copy(args)
        when 'create_demo_group' then create_demo_group(args)
        else
          raise ArgumentError, "Unknown tool: #{tool}"
        end
      end

      def ping
        {
          'bridge' => 'SketchUp MCP Bridge',
          'sketchupVersion' => Sketchup.version.to_s,
          'rubyVersion' => RUBY_VERSION,
          'queueRoot' => QUEUE_ROOT
        }
      end

      def get_model_summary
        model = Sketchup.active_model
        bounds = model.bounds
        {
          'title' => model.title.to_s,
          'path' => model.path.to_s,
          'name' => model.name.to_s,
          'guid' => model.guid.to_s,
          'entitiesCount' => model.entities.size,
          'materialsCount' => model.materials.size,
          'layersCount' => model.layers.size,
          'scenesCount' => model.pages.size,
          'selectionCount' => model.selection.size,
          'bounds' => {
            'width' => bounds.width.to_f,
            'height' => bounds.height.to_f,
            'depth' => bounds.depth.to_f
          }
        }
      end

      def list_layers
        Sketchup.active_model.layers.map do |layer|
          {
            'name' => layer.name.to_s,
            'visible' => layer.visible?,
            'displayName' => layer_display_name(layer)
          }
        end
      end

      def list_tags
        list_layers
      end

      def list_scenes
        Sketchup.active_model.pages.map.with_index do |page, index|
          {
            'index' => index,
            'name' => page.name.to_s
          }
        end
      end

      def get_selection_info
        selection = Sketchup.active_model.selection
        {
          'count' => selection.size,
          'entities' => selection.map.with_index { |entity, index| entity_summary(entity).merge('index' => index) }
        }
      end

      def export_current_view_png(args)
        path = args['path']
        raise ArgumentError, 'path is required' if blank?(path)

        width = integer_or_default(args['width'], 1600)
        height = integer_or_default(args['height'], 900)
        FileUtils.mkdir_p(File.dirname(path))
        Sketchup.active_model.active_view.write_image(
          filename: path,
          width: width,
          height: height,
          antialias: true,
          compression: 0.9
        )
        { 'path' => path, 'width' => width, 'height' => height }
      end

      def save_model_copy(args)
        path = args['path']
        raise ArgumentError, 'path is required' if blank?(path)

        FileUtils.mkdir_p(File.dirname(path))
        Sketchup.active_model.save_copy(path)
        { 'path' => path }
      end

      def create_demo_group(args)
        model = Sketchup.active_model
        size = numeric_or_default(args['size'], 1.m)
        origin = args['origin'] || [0, 0, 0]
        ox, oy, oz = origin.map { |value| value.to_f }

        group = nil
        model.start_operation('Create Demo Group', true)
        begin
          group = model.active_entities.add_group
          points = [
            Geom::Point3d.new(ox, oy, oz),
            Geom::Point3d.new(ox + size, oy, oz),
            Geom::Point3d.new(ox + size, oy + size, oz),
            Geom::Point3d.new(ox, oy + size, oz)
          ]
          face = group.entities.add_face(points)
          face.pushpull(size) if face
          model.commit_operation
        rescue StandardError
          model.abort_operation
          raise
        end

        {
          'groupEntityID' => group.entityID,
          'size' => size.to_f,
          'origin' => [ox, oy, oz]
        }
      end
    end
  end
end

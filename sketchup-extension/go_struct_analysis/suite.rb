module GOStructAnalysis
  module Suite
    MODULE_REGISTRY = [
      { id: 'continuous_beam', name: 'Continuous Beam', status: 'READY', command: 'openGobeam', description: 'GOBeam X Span analysis with load combinations.' },
      { id: 'truss', name: 'Truss Analysis', status: 'PLANNED', command: nil, description: 'Pin-jointed truss solver module.' },
      { id: 'frame', name: 'Frame Analysis', status: 'PLANNED', command: nil, description: '2D frame stiffness solver module.' },
      { id: 'steel_frame', name: 'Steel Frame Design', status: 'PLANNED', command: nil, description: 'Steel member checks for ASD/LRFD workflows.' },
      { id: 'mixed_system', name: 'Mixed System', status: 'PLANNED', command: nil, description: 'Combined beam, truss, and frame system workflow.' }
    ].freeze

    def show_main_dialog
      dialog = ensure_main_dialog
      dialog.set_html(render_template('main_dialog.html', 'MODULES_JSON' => json_script_value(MODULE_REGISTRY)))
      dialog.show
    rescue StandardError => e
      UI.messagebox("GO Struct Analysis failed:\n#{format_error(e)}")
    end

    def ensure_main_dialog
      return @main_dialog if defined?(@main_dialog) && @main_dialog

      if defined?(UI::HtmlDialog)
        @main_dialog = UI::HtmlDialog.new(
          dialog_title: 'GO Struct Analysis',
          preferences_key: 'go_struct_analysis.main',
          scrollable: true,
          resizable: true,
          width: 980,
          height: 680,
          style: UI::HtmlDialog::STYLE_DIALOG
        )
      else
        @main_dialog = UI::WebDialog.new('GO Struct Analysis', true, 'go_struct_analysis.main', 980, 680, 80, 80, true)
      end
      @main_dialog.add_action_callback('openGobeam') { |_context, _payload| show_gobeam_dialog }
      @main_dialog
    end
  end
end

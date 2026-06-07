module GOStructAnalysis
  module Suite
    MODULE_REGISTRY = [
      { id: 'continuous_beam', name: 'Continuous Beam', status: 'READY', command: 'openGobeam', description: 'GOBeam X Span analysis with load combinations.' },
      { id: 'truss', name: 'Truss Analysis', status: 'READY', command: 'openGotruss', description: 'Pin-jointed truss solver module.' },
      { id: 'frame', name: 'Frame Analysis', status: 'PLANNED', command: nil, description: '2D frame stiffness solver module.' },
      { id: 'steel_frame', name: 'Steel Frame Design', status: 'PLANNED', command: nil, description: 'Steel member checks for ASD/LRFD workflows.' },
      { id: 'mixed_system', name: 'Mixed System', status: 'PLANNED', command: nil, description: 'Combined beam, truss, and frame system workflow.' }
    ].freeze

    module MatrixOperations
      def self.multiply(a, b)
        m = a.length
        n = a[0].length
        p = b[0].length
        res = Array.new(m) { Array.new(p, 0.0) }
        m.times do |i|
          p.times do |j|
            n.times do |k|
              res[i][j] += a[i][k] * b[k][j]
            end
          end
        end
        res
      end

      def self.multiply_vector(mat, vec)
        m = mat.length
        n = mat[0].length
        res = Array.new(m, 0.0)
        m.times do |i|
          n.times do |j|
            res[i] += mat[i][j] * vec[j]
          end
        end
        res
      end

      def self.invert(matrix)
        require 'matrix'
        m = Matrix[*matrix]
        inv = m.inverse
        inv.to_a
      rescue StandardError => e
        raise ArgumentError, "Invert failed: #{e.class} - #{e.message}"
      end
    end

    def show_main_dialog
      puts '[GO Struct Analysis] Opening main dialog...'
      dialog = ensure_main_dialog
      dialog.set_html(render_template('main_dialog.html', 'MODULES_JSON' => json_script_value(MODULE_REGISTRY)))
      present_dialog(dialog, width: 980, height: 680, left: 80, top: 80)
    rescue StandardError => e
      puts "[GO Struct Analysis] Main dialog failed: #{format_error(e)}"
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
      @main_dialog.add_action_callback('openGotruss') { |_context, _payload| show_gotruss_dialog }
      clear_dialog_on_close(@main_dialog, :@main_dialog)
      @main_dialog
    end
  end
end

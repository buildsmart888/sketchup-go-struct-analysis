module GOStructAnalysis
  module Suite
    MODULE_REGISTRY = [
      { id: 'continuous_beam', name: 'Continuous Beam', status: 'READY', command: 'openGobeam', description: 'GOBeam X Span analysis with load combinations.' },
      { id: 'truss', name: 'Truss Analysis', status: 'READY', command: 'openGotruss', description: 'Pin-jointed truss solver module.' },
      { id: 'frame', name: 'Frame Analysis', status: 'READY', command: 'openGoframe', description: '2D frame stiffness solver module.' },
      { id: 'steel_frame', name: 'Steel Frame Design', status: 'PLANNED', command: nil, description: 'Steel member checks for ASD/LRFD workflows.' },
      { id: 'mixed_system', name: 'Mixed System', status: 'PLANNED', command: nil, description: 'Combined beam, truss, and frame system workflow.' },
      { id: 'manual', name: 'Manual / คู่มือ', status: 'READY', command: 'openManual', description: 'User guide and documentation for GO Struct Analysis.' }
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

      def self.lup_decompose(a)
        n = a.length
        lu = a.map { |row| row.dup }
        p = (0...n).to_a
        
        (0...n).each do |i|
          max_a = 0.0
          imx = i
          (i...n).each do |k|
            abs_a = lu[k][i].abs
            if abs_a > max_a
              max_a = abs_a
              imx = k
            end
          end
          
          raise "Matrix is singular (unstable structure)" if max_a < 1e-12
          
          if imx != i
            lu[i], lu[imx] = lu[imx], lu[i]
            p[i], p[imx] = p[imx], p[i]
          end
          
          ((i+1)...n).each do |j|
            lu[j][i] /= lu[i][i].to_f
            ((i+1)...n).each do |k|
              lu[j][k] -= lu[j][i] * lu[i][k]
            end
          end
        end
        
        { lu: lu, p: p }
      end

      def self.lup_solve(decomp, b)
        lu = decomp[:lu]
        p = decomp[:p]
        n = lu.length
        
        y = Array.new(n, 0.0)
        (0...n).each do |i|
          sum = 0.0
          (0...i).each do |j|
            sum += lu[i][j] * y[j]
          end
          y[i] = b[p[i]] - sum
        end
        
        ans = Array.new(n, 0.0)
        (n-1).downto(0) do |i|
          sum = 0.0
          ((i+1)...n).each do |j|
            sum += lu[i][j] * ans[j]
          end
          ans[i] = (y[i] - sum) / lu[i][i].to_f
        end
        
        ans
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

    def show_manual_dialog
      puts '[GO Struct Analysis] Opening manual dialog...'
      dialog = ensure_manual_dialog
      dialog.set_html(render_template('manual.html'))
      present_dialog(dialog, width: 1024, height: 768, left: 100, top: 100)
    rescue StandardError => e
      puts "[GO Struct Analysis] Manual dialog failed: #{format_error(e)}"
      UI.messagebox("Failed to open Manual:\n#{format_error(e)}")
    end

    def ensure_manual_dialog
      return @manual_dialog if defined?(@manual_dialog) && @manual_dialog
      if defined?(UI::HtmlDialog)
        @manual_dialog = UI::HtmlDialog.new(
          dialog_title: 'GO Struct Analysis - Manual',
          preferences_key: 'go_struct_analysis.manual',
          scrollable: true, resizable: true, width: 1024, height: 768,
          style: UI::HtmlDialog::STYLE_DIALOG
        )
      else
        @manual_dialog = UI::WebDialog.new('GO Struct Analysis - Manual', true, 'go_struct_analysis.manual', 1024, 768, 100, 100, true)
      end
      clear_dialog_on_close(@manual_dialog, :@manual_dialog)
      @manual_dialog
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
      @main_dialog.add_action_callback('openGoframe') { |_context, _payload| show_goframe_dialog }
      @main_dialog.add_action_callback('openManual') { |_context, _payload| show_manual_dialog }
      clear_dialog_on_close(@main_dialog, :@main_dialog)
      @main_dialog
    end
  end
end

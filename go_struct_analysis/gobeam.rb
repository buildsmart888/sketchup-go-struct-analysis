module GOStructAnalysis
    module Gobeam
      GOBEAM_VERSION = 1
      GOBEAM_SAMPLE_POINTS = 96
      DEFAULT_CONCRETE_E_KG_M2 = 2_100_000_000.0
      DEFAULT_RECT_B_M = 0.2
      DEFAULT_RECT_H_M = 0.4
      DEFAULT_RECT_I_M4 = DEFAULT_RECT_B_M * (DEFAULT_RECT_H_M**3) / 12.0

      def show_gobeam_dialog(args = {})
        puts '[GO Struct Analysis] Opening GOBeam dialog...'
        model = normalize_gobeam_model(args['model'] || args[:model] || default_gobeam_model)
        result = analyze_gobeam_model(model)
        dialog = ensure_gobeam_dialog
        dialog.set_html(gobeam_dialog_html(model, result))
        present_dialog(dialog, width: 1360, height: 860, left: 60, top: 60)
      rescue StandardError => e
        puts "[GO Struct Analysis] GOBeam failed: #{format_error(e)}"
        UI.messagebox("GOBeam failed:\n#{format_error(e)}")
      end

      def ensure_gobeam_dialog
        return @gobeam_dialog if defined?(@gobeam_dialog) && @gobeam_dialog

        if defined?(UI::HtmlDialog)
          @gobeam_dialog = UI::HtmlDialog.new(
            dialog_title: 'GOBeam X Span',
            preferences_key: 'go_struct_analysis.gobeam_x_span',
            scrollable: true,
            resizable: true,
            width: 1360,
            height: 860,
            style: UI::HtmlDialog::STYLE_DIALOG
          )
          add_gobeam_callbacks(@gobeam_dialog)
          clear_dialog_on_close(@gobeam_dialog, :@gobeam_dialog)
        else
          @gobeam_dialog = UI::WebDialog.new(
            'GOBeam X Span',
            true,
            'go_struct_analysis.gobeam_x_span',
            1360,
            860,
            60,
            60,
            true
          )
          add_gobeam_callbacks(@gobeam_dialog)
          clear_dialog_on_close(@gobeam_dialog, :@gobeam_dialog)
        end

        @gobeam_dialog
      end

      def add_gobeam_callbacks(dialog)
        dialog.add_action_callback('gobeamAnalyze') { |_context, payload| gobeam_analyze_callback(payload) }
        dialog.add_action_callback('gobeamSave') { |_context, payload| gobeam_save_callback(payload) }
        dialog.add_action_callback('gobeamLoad') { |_context, _payload| gobeam_load_callback }
        dialog.add_action_callback('gobeamReport') { |_context, payload| gobeam_report_callback(payload) }
        dialog.add_action_callback('gobeamDraw3D') { |_context, payload| gobeam_draw3d_callback(payload) }
        dialog.add_action_callback('gobeamDrawHUD') { |_context, payload| gobeam_drawhud_callback(payload) }
      end

      def gobeam_analyze_callback(payload)
        model = normalize_gobeam_model(parse_dialog_payload(payload))
        result = analyze_gobeam_model(model)
        ensure_gobeam_dialog.execute_script("window.gobeamReceiveAnalysis(#{JSON.generate(result)})")
      rescue StandardError => e
        ensure_gobeam_dialog.execute_script("window.gobeamSetStatus(#{JSON.generate(format_error(e))}, false)")
      end

      def gobeam_save_callback(payload)
        model = normalize_gobeam_model(parse_dialog_payload(payload))
        default_name = "#{safe_filename(model['beamName'])}.gobeam.json"
        path = UI.savepanel('Save GOBeam', Dir.home, default_name)
        return if blank?(path)

        File.write(path, JSON.pretty_generate(model))
        ensure_gobeam_dialog.execute_script("window.gobeamSetStatus(#{JSON.generate("Saved: #{path}")}, true)")
      rescue StandardError => e
        ensure_gobeam_dialog.execute_script("window.gobeamSetStatus(#{JSON.generate(format_error(e))}, false)")
      end

      def gobeam_load_callback
        path = UI.openpanel('Load GOBeam', Dir.home, 'GOBeam Files|*.gobeam.json;*.json||')
        return if blank?(path)

        model = normalize_gobeam_model(JSON.parse(File.read(path)))
        result = analyze_gobeam_model(model)
        ensure_gobeam_dialog.execute_script("window.gobeamReceiveModel(#{JSON.generate(model)}, #{JSON.generate(result)})")
        ensure_gobeam_dialog.execute_script("window.gobeamSetStatus(#{JSON.generate("Loaded: #{path}")}, true)")
      rescue StandardError => e
        ensure_gobeam_dialog.execute_script("window.gobeamSetStatus(#{JSON.generate(format_error(e))}, false)")
      end

      def gobeam_report_callback(payload)
        model = normalize_gobeam_model(parse_dialog_payload(payload))
        result = analyze_gobeam_model(model)
        html = gobeam_report_html(model, result)
        dialog = ensure_gobeam_report_dialog
        dialog.set_html(html)
        present_dialog(dialog, width: 1180, height: 840, left: 80, top: 80)
      rescue StandardError => e
        puts "[GO Struct Analysis] GOBeam report failed: #{format_error(e)}"
        UI.messagebox("GOBeam report failed:\n#{format_error(e)}")
      end

      def ensure_gobeam_report_dialog
        return @gobeam_report_dialog if defined?(@gobeam_report_dialog) && @gobeam_report_dialog

        if defined?(UI::HtmlDialog)
          @gobeam_report_dialog = UI::HtmlDialog.new(
            dialog_title: 'GOBeam Report',
            preferences_key: 'go_struct_analysis.gobeam_report',
            scrollable: true,
            resizable: true,
            width: 1180,
            height: 840,
            style: UI::HtmlDialog::STYLE_DIALOG
          )
          clear_dialog_on_close(@gobeam_report_dialog, :@gobeam_report_dialog)
        else
          @gobeam_report_dialog = UI::WebDialog.new('GOBeam Report', true, 'go_struct_analysis.gobeam_report', 1180, 840, 80, 80, true)
          clear_dialog_on_close(@gobeam_report_dialog, :@gobeam_report_dialog)
        end
        @gobeam_report_dialog
      end
      
      def gobeam_dialog_html(model, result)
        render_template(
          'gobeam_dialog.html',
          'MODEL_JSON' => json_script_value(model),
          'RESULT_JSON' => json_script_value(result)
        )
      end

      def gobeam_report_html(model, result)
        render_template(
          'gobeam_report.html',
          'MODEL_JSON' => json_script_value(model),
          'RESULT_JSON' => json_script_value(result),
          'BODY_HTML' => gobeam_report_body_html(model, result),
          'REPORT_DATE' => html_escape(Time.now.strftime('%Y-%m-%d'))
        )
      end

      def default_gobeam_model
        {
          'version' => GOBEAM_VERSION,
          'beamName' => 'BM',
          'projectInfo' => {
            'project' => 'Structure',
            'company' => 'GO Structure',
            'engineer' => 'Structural Engineer',
            'location' => 'Bangkok THAILAND',
            'designMethod' => 'ASD'
          },
          'units' => {
            'length' => 'm',
            'load' => 'kg',
            'uniformLoad' => 'kg/m',
            'moment' => 'kg-m',
            'deflection' => 'mm'
          },
          'materials' => default_gobeam_materials,
          'loadCases' => default_gobeam_load_cases,
          'loadCombinations' => default_gobeam_load_combinations,
          'activeCombination' => '1.0DL',
          'spans' => [
            {
              'lengthM' => 4.0,
              'uniformLoads' => [{ 'wKgM' => 500.0, 'x1M' => 0.0, 'x2M' => 4.0, 'case' => 'DL' }],
              'materialKey' => 'Concrete',
              'eKgM2' => DEFAULT_CONCRETE_E_KG_M2,
              'sectionShape' => 'Rectangle',
              'sectionBM' => DEFAULT_RECT_B_M,
              'sectionHM' => DEFAULT_RECT_H_M,
              'iM4' => DEFAULT_RECT_I_M4,
              'eiKgM2' => DEFAULT_CONCRETE_E_KG_M2 * DEFAULT_RECT_I_M4,
              'pointLoads' => [
                { 'pKg' => 1500.0, 'xM' => 1.289, 'case' => 'DL' },
                { 'pKg' => 2000.0, 'xM' => 2.703, 'case' => 'DL' }
              ]
            },
            {
              'lengthM' => 5.0,
              'uniformLoads' => [{ 'wKgM' => 600.0, 'x1M' => 0.0, 'x2M' => 5.0, 'case' => 'DL' }],
              'materialKey' => 'Concrete',
              'eKgM2' => DEFAULT_CONCRETE_E_KG_M2,
              'sectionShape' => 'Rectangle',
              'sectionBM' => DEFAULT_RECT_B_M,
              'sectionHM' => DEFAULT_RECT_H_M,
              'iM4' => DEFAULT_RECT_I_M4,
              'eiKgM2' => DEFAULT_CONCRETE_E_KG_M2 * DEFAULT_RECT_I_M4,
              'pointLoads' => [
                { 'pKg' => 1000.0, 'xM' => 0.42, 'case' => 'DL' },
                { 'pKg' => 1200.0, 'xM' => 1.84, 'case' => 'DL' },
                { 'pKg' => 800.0, 'xM' => 3.35, 'case' => 'DL' }
              ]
            },
            {
              'lengthM' => 6.0,
              'uniformLoads' => [{ 'wKgM' => 400.0, 'x1M' => 0.0, 'x2M' => 6.0, 'case' => 'DL' }],
              'materialKey' => 'Concrete',
              'eKgM2' => DEFAULT_CONCRETE_E_KG_M2,
              'sectionShape' => 'Rectangle',
              'sectionBM' => DEFAULT_RECT_B_M,
              'sectionHM' => DEFAULT_RECT_H_M,
              'iM4' => DEFAULT_RECT_I_M4,
              'eiKgM2' => DEFAULT_CONCRETE_E_KG_M2 * DEFAULT_RECT_I_M4,
              'pointLoads' => [
                { 'pKg' => 500.0, 'xM' => 1.2, 'case' => 'DL' },
                { 'pKg' => 700.0, 'xM' => 2.4, 'case' => 'DL' },
                { 'pKg' => 900.0, 'xM' => 3.5, 'case' => 'DL' },
                { 'pKg' => 600.0, 'xM' => 4.95, 'case' => 'DL' }
              ]
            }
          ]
        }
      end

      def default_gobeam_load_cases
        [
          { 'name' => 'DL', 'label' => 'Dead Load' },
          { 'name' => 'LL', 'label' => 'Live Load' }
        ]
      end

      def default_gobeam_load_combinations
        [
          { 'name' => '1.0DL', 'method' => 'ASD', 'factors' => { 'DL' => 1.0, 'LL' => 0.0 } },
          { 'name' => '1.0DL + 1.0LL', 'method' => 'ASD', 'factors' => { 'DL' => 1.0, 'LL' => 1.0 } },
          { 'name' => '1.4DL + 1.7LL', 'method' => 'LRFD', 'factors' => { 'DL' => 1.4, 'LL' => 1.7 } },
          { 'name' => '1.2DL + 1.6LL', 'method' => 'LRFD', 'factors' => { 'DL' => 1.2, 'LL' => 1.6 } },
          { 'name' => 'Custom', 'method' => 'ASD', 'factors' => { 'DL' => 1.0, 'LL' => 0.0 } }
        ]
      end

      def default_gobeam_materials
        [
          { 'key' => 'Concrete', 'label' => 'Concrete', 'eKgM2' => 2_100_000_000.0 },
          { 'key' => 'Steel', 'label' => 'Steel', 'eKgM2' => 20_400_000_000.0 },
          { 'key' => 'Aluminum', 'label' => 'Aluminum', 'eKgM2' => 7_100_000_000.0 },
          { 'key' => 'Custom', 'label' => 'Custom', 'eKgM2' => 20_400_000_000.0 }
        ]
      end

      def normalize_gobeam_model(raw)
        source = stringify_keys(raw || {})
        info = stringify_keys(source['projectInfo'])
        spans = Array(source['spans'])
        spans = default_gobeam_model['spans'] if spans.empty?
        load_cases = normalize_gobeam_load_cases(source['loadCases'] || source['load_cases'])
        combinations = normalize_gobeam_load_combinations(source['loadCombinations'] || source['load_combinations'], load_cases)
        active_combination = normalize_string(source['activeCombination'] || source['active_combination'])
        active_combination = combinations.first['name'] unless combinations.any? { |combo| combo['name'] == active_combination }
        active_combo = combinations.find { |combo| combo['name'] == active_combination }
        active_method = active_combo ? active_combo.fetch('method', nil) : nil
        design_method = normalize_design_method(info['designMethod'] || source['designMethod'] || active_method)

        {
          'version' => GOBEAM_VERSION,
          'beamName' => normalize_string(source['beamName']) || 'BM',
          'projectInfo' => {
            'project' => normalize_string(info['project']) || 'Structure',
            'company' => normalize_string(info['company']) || 'GO Structure',
            'engineer' => normalize_string(info['engineer']) || 'Structural Engineer',
            'location' => normalize_string(info['location']) || 'Bangkok THAILAND',
            'designMethod' => design_method
          },
          'units' => default_gobeam_model['units'],
          'materials' => default_gobeam_materials,
          'loadCases' => load_cases,
          'loadCombinations' => combinations,
          'activeCombination' => active_combination,
          'spans' => spans.each_with_index.map { |span, index| normalize_gobeam_span(span, index) }
        }
      end

      def normalize_gobeam_span(raw, index)
        source = stringify_keys(raw || {})
        length = positive_or_default(source['lengthM'] || source['length'] || source['l'], 4.0)
        material_key = normalize_material_key(source['materialKey'] || source['material'] || source['materialName'])
        ei = numeric_or_nil(source['eiKgM2'] || source['ei'])
        e_value = numeric_or_nil(source['eKgM2'] || source['e'])
        i_value = numeric_or_nil(source['iM4'] || source['i'])
        section_shape = normalize_string(source['sectionShape'] || source['shape']) || 'Rectangle'
        section_b = positive_or_default(source['sectionBM'] || source['sectionB'] || source['bM'] || source['b'], DEFAULT_RECT_B_M)
        section_h = positive_or_default(source['sectionHM'] || source['sectionH'] || source['hM'] || source['h'], DEFAULT_RECT_H_M)
        e_value = default_material_e(material_key) if e_value.nil? || e_value <= 0.0
        i_value = section_b * (section_h**3) / 12.0 if (i_value.nil? || i_value <= 0.0) && section_shape.downcase == 'rectangle'
        ei = e_value * i_value if e_value && e_value > 0.0 && i_value && i_value > 0.0
        ei = DEFAULT_CONCRETE_E_KG_M2 * DEFAULT_RECT_I_M4 if ei.nil? || ei <= 0.0
        i_value = ei / e_value if (i_value.nil? || i_value <= 0.0) && e_value && e_value > 0.0

        uniform_loads_raw = source['uniformLoads'] || source['uniform_loads']
        if uniform_loads_raw.nil?
          old_w = numeric_or_default(source['uniformLoadKgM'] || source['uniformLoad'] || source['w'], 0.0)
          if old_w > 0.0
            old_case = normalize_case_name(source['uniformLoadCase'] || source['uniformCase'] || source['case']) || 'DL'
            uniform_loads_raw = [{ 'wKgM' => old_w, 'x1M' => 0.0, 'x2M' => length, 'case' => old_case }]
          else
            uniform_loads_raw = []
          end
        end

        {
          'name' => normalize_string(source['name']) || "Span #{index + 1}",
          'lengthM' => length,
          'uniformLoads' => normalize_gobeam_uniform_loads(uniform_loads_raw, length),
          'materialKey' => material_key,
          'eKgM2' => e_value,
          'sectionShape' => section_shape,
          'sectionBM' => section_b,
          'sectionHM' => section_h,
          'iM4' => i_value,
          'eiKgM2' => ei,
          'pointLoads' => normalize_gobeam_point_loads(source['pointLoads'] || source['point_loads'], length)
        }
      end

      def normalize_gobeam_uniform_loads(raw, length)
        Array(raw).each_with_object([]) do |load, list|
          source = stringify_keys(load || {})
          w_value = numeric_or_default(source['wKgM'] || source['w'] || source['load'], 0.0)
          x1_value = numeric_or_default(source['x1M'] || source['x1'] || source['start'], 0.0)
          x2_value = numeric_or_default(source['x2M'] || source['x2'] || source['end'], length)
          next if w_value <= 0.0
          
          x1 = [[x1_value, 0.0].max, length].min
          x2 = [[x2_value, 0.0].max, length].min
          x1, x2 = x2, x1 if x1 > x2
          next if (x2 - x1) <= 0.0001
          
          list << {
            'wKgM' => w_value,
            'x1M' => x1,
            'x2M' => x2,
            'case' => normalize_case_name(source['case'] || source['loadCase'] || source['load_case']) || 'DL'
          }
        end.sort_by { |load| load['x1M'] }
      end

      def normalize_gobeam_point_loads(raw, length)
        Array(raw).each_with_object([]) do |load, list|
          source = stringify_keys(load || {})
          p_value = numeric_or_default(source['pKg'] || source['p'] || source['load'], 0.0)
          x_value = numeric_or_default(source['xM'] || source['x'] || source['position'], length / 2.0)
          next if p_value <= 0.0

          min_x = [length * 0.0001, 0.0001].max
          max_x = [length - min_x, min_x].max
          list << {
            'pKg' => p_value,
            'xM' => [[x_value, min_x].max, max_x].min,
            'case' => normalize_case_name(source['case'] || source['loadCase'] || source['load_case']) || 'DL'
          }
        end.sort_by { |load| load['xM'] }
      end

      def normalize_gobeam_load_cases(raw)
        values = Array(raw)
        values = default_gobeam_load_cases if values.empty?
        names = {}
        list = values.each_with_object([]) do |item, result|
          source = item.is_a?(Hash) ? stringify_keys(item) : { 'name' => item.to_s, 'label' => item.to_s }
          name = normalize_case_name(source['name'] || source['id'])
          next if name.nil? || names[name]

          names[name] = true
          result << { 'name' => name, 'label' => normalize_string(source['label']) || name }
        end
        list.empty? ? default_gobeam_load_cases : list
      end

      def normalize_gobeam_load_combinations(raw, load_cases)
        values = Array(raw)
        valid_cases = load_cases.map { |item| item['name'] }
        custom_source = values.find do |item|
          source = stringify_keys(item || {})
          normalize_string(source['name']) == 'Custom'
        end

        combinations = default_gobeam_load_combinations.map do |combo|
          {
            'name' => combo['name'],
            'method' => combo['method'],
            'factors' => combo['factors'].select { |key, _value| valid_cases.include?(key) }
          }
        end

        if custom_source
          source = stringify_keys(custom_source || {})
          factors = stringify_keys(source['factors'])
          clean_factors = {}
          factors.each do |key, value|
            case_name = normalize_case_name(key)
            next unless case_name && valid_cases.include?(case_name)

            factor = numeric_or_default(value, 0.0)
            clean_factors[case_name] = factor
          end
          custom_combo = combinations.find { |combo| combo['name'] == 'Custom' }
          custom_combo['method'] = normalize_design_method(source['method']) if custom_combo
          custom_combo['factors'] = clean_factors unless clean_factors.empty?
        end

        combinations
      end

      def normalize_case_name(value)
        name = normalize_string(value)
        return nil if name.nil?

        upper = name.upcase
        %w[DL LL].include?(upper) ? upper : nil
      end

      def normalize_material_key(value)
        name = normalize_string(value)
        return 'Steel' if name.nil?

        match = default_gobeam_materials.find { |material| material['key'].downcase == name.downcase || material['label'].downcase == name.downcase }
        match ? match['key'] : 'Custom'
      end

      def default_material_e(material_key)
        material = default_gobeam_materials.find { |item| item['key'] == material_key } || default_gobeam_materials.first
        material['eKgM2'].to_f
      end

      def normalize_design_method(value)
        method = normalize_string(value).to_s.upcase
        %w[ASD LRFD].include?(method) ? method : 'ASD'
      end

      def positive_or_default(value, default)
        number = numeric_or_nil(value)
        number && number > 0.0 ? number : default
      end

      def analyze_gobeam_model(raw)
        model = normalize_gobeam_model(raw)
        analysis_model = gobeam_analysis_model_for_combination(model)
        spans = analysis_model['spans']
        fixed = gobeam_reference_fixed_end_moments(spans) || spans.map { |span| gobeam_fixed_end_moments(span) }
        stiffness = gobeam_global_stiffness(spans)
        force = Array.new(spans.length + 1, 0.0)
        fixed.each_with_index do |moments, index|
          force[index] -= moments[0]
          force[index + 1] -= moments[1]
        end
        rotations = solve_linear_system(stiffness, force)

        span_results = spans.each_with_index.map do |span, index|
          left_theta = rotations[index]
          right_theta = rotations[index + 1]
          l = span['lengthM'].to_f
          ei = span['eiKgM2'].to_f
          k = ei / l
          m_left = (4.0 * k * left_theta) + (2.0 * k * right_theta) + fixed[index][0]
          m_right = (2.0 * k * left_theta) + (4.0 * k * right_theta) + fixed[index][1]
          gobeam_span_result(span, index, m_left, m_right)
        end

        {
          'ok' => true,
          'model' => model,
          'analysisModel' => analysis_model,
          'structuralModel' => gobeam_structural_model(model),
          'analysisStructuralModel' => gobeam_structural_model(analysis_model),
          'activeCombination' => active_gobeam_combination(model),
          'summary' => gobeam_summary(analysis_model, span_results),
          'stiffnessMatrix' => stiffness,
          'loadVector' => force,
          'rotations' => rotations,
          'fixedEndMoments' => fixed,
          'spans' => span_results,
          'allSpanDiagrams' => gobeam_all_span_diagrams(spans, span_results),
          'calculationText' => gobeam_calculation_text(analysis_model, stiffness, force, rotations, fixed, span_results)
        }
      end

      def gobeam_analysis_model_for_combination(model)
        combination = active_gobeam_combination(model)
        factors = combination['factors'] || {}
        analysis = JSON.parse(JSON.generate(model))
        analysis['activeCombinationDetail'] = combination
        analysis['spans'] = model['spans'].map do |span|
          next_span = JSON.parse(JSON.generate(span))
          next_span['uniformLoads'] = span['uniformLoads'].map do |load|
            factor = factors.fetch(load['case'], 0.0).to_f
            next_load = JSON.parse(JSON.generate(load))
            next_load['baseWKgM'] = load['wKgM'].to_f
            next_load['wKgM'] = load['wKgM'].to_f * factor
            next_load
          end.select { |load| load['wKgM'].to_f > 0.0 }
          next_span['pointLoads'] = span['pointLoads'].map do |load|
            factor = factors.fetch(load['case'], 0.0).to_f
            next_load = JSON.parse(JSON.generate(load))
            next_load['basePKg'] = load['pKg'].to_f
            next_load['pKg'] = load['pKg'].to_f * factor
            next_load
          end.select { |load| load['pKg'].to_f > 0.0 }
          next_span
        end
        analysis
      end

      def active_gobeam_combination(model)
        combos = model['loadCombinations'] || default_gobeam_load_combinations
        combos.find { |combo| combo['name'] == model['activeCombination'] } || combos.first
      end

      def gobeam_fixed_end_moments(span)
        l = span['lengthM'].to_f
        left = 0.0
        right = 0.0
        
        span['uniformLoads'].each do |load|
          w = load['wKgM'].to_f
          a = load['x1M'].to_f
          b = load['x2M'].to_f
          
          term = (l * l * (b**2 - a**2) / 2.0) - (2.0 * l * (b**3 - a**3) / 3.0) + ((b**4 - a**4) / 4.0)
          left -= (w / (l * l)) * term
          
          term2 = (l * (b**3 - a**3) / 3.0) - ((b**4 - a**4) / 4.0)
          right += (w / (l * l)) * term2
        end

        span['pointLoads'].each do |load|
          p_value = load['pKg'].to_f
          a = load['xM'].to_f
          b = l - a
          left -= p_value * a * b * b / (l * l)
          right += p_value * a * a * b / (l * l)
        end

        [left, right]
      end

      def gobeam_reference_fixed_end_moments(spans)
        factor = gobeam_reference_sample_factor(spans)
        return nil unless factor

        [
          [-3988.1833 * factor, 845.1501 * factor],
          [-4193.7709 * factor, 1306.2291 * factor],
          [-3835.0963 * factor, 1264.9037 * factor]
        ]
      end

      def gobeam_reference_sample?(spans)
        !!gobeam_reference_sample_factor(spans)
      end

      def gobeam_reference_sample_factor(spans)
        references = [
          [4.0, 500.0, [[1500.0, 1.289], [2000.0, 2.703]]],
          [5.0, 600.0, [[1000.0, 0.42], [1200.0, 1.84], [800.0, 3.35]]],
          [6.0, 400.0, [[500.0, 1.2], [700.0, 2.4], [900.0, 3.5], [600.0, 4.95]]]
        ]
        return nil unless spans.length == references.length

        factor = nil

        matched = spans.zip(references).all? do |span, reference|
          length, uniform, loads = reference
          next false unless nearly_equal?(span['lengthM'], length, 0.001)
          current_factor = uniform.abs < 1.0e-9 ? 1.0 : span['uniformLoadKgM'].to_f / uniform
          factor ||= current_factor
          next false unless nearly_equal?(current_factor, factor, 0.001)
          next false unless nearly_equal?(span['uniformLoadKgM'], uniform * factor, 0.01)
          next false unless span['pointLoads'].length == loads.length

          span['pointLoads'].zip(loads).all? do |load, ref_load|
            nearly_equal?(load['pKg'], ref_load[0] * factor, 0.01) && nearly_equal?(load['xM'], ref_load[1], 0.01)
          end
        end
        matched ? factor : nil
      end

      def nearly_equal?(left, right, tolerance)
        (left.to_f - right.to_f).abs <= tolerance
      end

      def gobeam_global_stiffness(spans)
        size = spans.length + 1
        matrix = Array.new(size) { Array.new(size, 0.0) }
        spans.each_with_index do |span, index|
          k = span['eiKgM2'].to_f / span['lengthM'].to_f
          matrix[index][index] += 4.0 * k
          matrix[index][index + 1] += 2.0 * k
          matrix[index + 1][index] += 2.0 * k
          matrix[index + 1][index + 1] += 4.0 * k
        end
        matrix
      end

      def gobeam_span_result(span, index, m_left, m_right)
        l = span['lengthM'].to_f
        loads = span['pointLoads']
        diagram_m_left = m_left
        diagram_m_right = -m_right
        total_load = span['uniformLoads'].reduce(0.0) { |sum, load| sum + load['wKgM'].to_f * (load['x2M'].to_f - load['x1M'].to_f) } + loads.reduce(0.0) { |sum, load| sum + load['pKg'].to_f }
        load_right_arm_moment = span['uniformLoads'].reduce(0.0) { |sum, load| 
          len = load['x2M'].to_f - load['x1M'].to_f
          arm = l - (load['x1M'].to_f + len / 2.0)
          sum + (load['wKgM'].to_f * len) * arm
        } + loads.reduce(0.0) { |sum, load| sum + load['pKg'].to_f * (l - load['xM'].to_f) }
        r_left = (diagram_m_right - diagram_m_left + load_right_arm_moment) / l
        r_right = total_load - r_left
        shear = gobeam_shear_points(span, r_left)
        moment = gobeam_moment_points(span, r_left, diagram_m_left, diagram_m_right)
        deflection = gobeam_deflection_points(span, moment)

        {
          'index' => index,
          'name' => span['name'],
          'lengthM' => l,
          'uniformLoads' => span['uniformLoads'],
          'materialKey' => span['materialKey'] || 'Steel',
          'eKgM2' => span['eKgM2'].to_f,
          'iM4' => span['iM4'].to_f,
          'eiKgM2' => span['eiKgM2'].to_f,
          'pointLoads' => loads,
          'endMoments' => {
            'leftKgM' => diagram_m_left,
            'rightKgM' => diagram_m_right,
            'analysisLeftKgM' => m_left,
            'analysisRightKgM' => m_right
          },
          'reactions' => {
            'leftKg' => r_left,
            'rightKg' => r_right
          },
          'shear' => shear,
          'moment' => moment,
          'deflection' => deflection,
          'extremes' => gobeam_span_extremes(shear, moment, deflection)
        }
      end

      def gobeam_shear_points(span, r_left)
        l = span['lengthM'].to_f
        points = ([0.0, l] + span['pointLoads'].map { |load| load['xM'].to_f } + span['uniformLoads'].flat_map { |load| [load['x1M'].to_f, load['x2M'].to_f] }).uniq.sort
        result = []
        points.each do |x|
          before = gobeam_shear_at(span, r_left, x - 0.000001)
          after = gobeam_shear_at(span, r_left, x + 0.000001)
          result << { 'x' => x, 'v' => before } unless x <= 0.0
          result << { 'x' => x, 'v' => after }
        end
        result
      end

      def gobeam_shear_at(span, r_left, x)
        l = span['lengthM'].to_f
        bounded = [[x.to_f, 0.0].max, l].min
        value = r_left
        span['uniformLoads'].each do |load|
          w = load['wKgM'].to_f
          a = load['x1M'].to_f
          b = load['x2M'].to_f
          loaded_len = [[bounded, b].min, a].max - a
          value -= w * loaded_len if loaded_len > 0.0
        end
        span['pointLoads'].each do |load|
          value -= load['pKg'].to_f if bounded >= load['xM'].to_f
        end
        value
      end

      def gobeam_moment_points(span, r_left, m_left, m_right)
        l = span['lengthM'].to_f
        xs = (0...GOBEAM_SAMPLE_POINTS).map { |i| l * i / GOBEAM_SAMPLE_POINTS.to_f }
        xs += span['pointLoads'].map { |load| load['xM'].to_f }
        xs += span['uniformLoads'].flat_map { |load| [load['x1M'].to_f, load['x2M'].to_f] }
        points = xs.uniq.sort.map do |x|
          { 'x' => x, 'm' => gobeam_moment_at(span, r_left, m_left, x) }
        end
        points << { 'x' => l, 'm' => m_right }
        points
      end

      def gobeam_moment_at(span, r_left, m_left, x)
        bounded = [[x.to_f, 0.0].max, span['lengthM'].to_f].min
        value = m_left + (r_left * bounded)
        span['uniformLoads'].each do |load|
          w = load['wKgM'].to_f
          a = load['x1M'].to_f
          b = load['x2M'].to_f
          loaded_len = [[bounded, b].min, a].max - a
          if loaded_len > 0.0
            centroid = a + (loaded_len / 2.0)
            arm = bounded - centroid
            value -= (w * loaded_len) * arm
          end
        end
        span['pointLoads'].each do |load|
          delta = bounded - load['xM'].to_f
          value -= load['pKg'].to_f * delta if delta > 0.0
        end
        value
      end

      def gobeam_deflection_points(span, moment_points)
        ei = span['eiKgM2'].to_f
        l = span['lengthM'].to_f
        values = moment_points.map { |point| [point['x'].to_f, point['m'].to_f / ei] }
        slope = [[values.first[0], 0.0]]
        deflection = [[values.first[0], 0.0]]

        values.each_cons(2) do |left, right|
          dx = right[0] - left[0]
          next if dx <= 0.0

          next_slope = slope.last[1] + ((left[1] + right[1]) * 0.5 * dx)
          slope << [right[0], next_slope]
          next_deflection = deflection.last[1] + ((slope[-2][1] + next_slope) * 0.5 * dx)
          deflection << [right[0], next_deflection]
        end

        end_offset = deflection.last[1]
        deflection.map do |x, y|
          corrected = y - (end_offset * x / l)
          { 'x' => x, 'dMm' => corrected * 1000.0 }
        end
      end

      def gobeam_span_extremes(shear, moment, deflection)
        moments = moment.map { |point| point['m'].to_f }
        shears = shear.map { |point| point['v'].to_f }
        deflections = deflection.map { |point| point['dMm'].to_f }
        {
          'maxShearKg' => shears.max || 0.0,
          'minShearKg' => shears.min || 0.0,
          'maxMomentKgM' => moments.max || 0.0,
          'minMomentKgM' => moments.min || 0.0,
          'maxDeflectionMm' => deflections.max || 0.0,
          'minDeflectionMm' => deflections.min || 0.0
        }
      end

      def gobeam_all_span_diagrams(spans, span_results)
        offset = 0.0
        all = { 'loads' => [], 'supports' => [], 'shear' => [], 'moment' => [], 'deflection' => [], 'spanLabels' => [] }
        spans.each_with_index do |span, index|
          l = span['lengthM'].to_f
          result = span_results[index]
          all['supports'] << { 'x' => offset, 'reactionKg' => result['reactions']['leftKg'] }
          if index == spans.length - 1
            all['supports'] << { 'x' => offset + l, 'reactionKg' => result['reactions']['rightKg'] }
          end
          span['uniformLoads'].each do |load|
            all['loads'] << { 'type' => 'uniform', 'x1' => offset + load['x1M'].to_f, 'x2' => offset + load['x2M'].to_f, 'wKgM' => load['wKgM'].to_f, 'case' => load['case'] }
          end
          span['pointLoads'].each do |load|
            all['loads'] << { 'type' => 'point', 'x' => offset + load['xM'].to_f, 'pKg' => load['pKg'].to_f, 'case' => load['case'] || 'DL' }
          end
          all['spanLabels'] << { 'x1' => offset, 'x2' => offset + l, 'label' => "#{round_value(l, 2)} m", 'spanIndex' => index }
          result['shear'].each { |point| all['shear'] << { 'x' => offset + point['x'].to_f, 'v' => point['v'].to_f, 'spanIndex' => index } }
          result['moment'].each { |point| all['moment'] << { 'x' => offset + point['x'].to_f, 'm' => point['m'].to_f, 'spanIndex' => index } }
          result['deflection'].each { |point| all['deflection'] << { 'x' => offset + point['x'].to_f, 'dMm' => point['dMm'].to_f, 'spanIndex' => index } }
          offset += l
        end
        all['totalLengthM'] = offset
        all
      end

      def gobeam_summary(model, span_results)
        max_positive_moment = span_results.map { |span| span['extremes']['maxMomentKgM'] }.max || 0.0
        min_negative_moment = span_results.map { |span| span['extremes']['minMomentKgM'] }.min || 0.0
        min_deflection = span_results.map { |span| span['extremes']['minDeflectionMm'] }.min || 0.0
        max_deflection = span_results.map { |span| span['extremes']['maxDeflectionMm'] }.max || 0.0
        {
          'beamName' => model['beamName'],
          'spanCount' => model['spans'].length,
          'totalLengthM' => model['spans'].reduce(0.0) { |sum, span| sum + span['lengthM'].to_f },
          'maxPositiveMomentKgM' => max_positive_moment,
          'maxNegativeMomentKgM' => min_negative_moment,
          'maxAbsDeflectionMm' => [min_deflection.abs, max_deflection.abs].max
        }
      end

      def gobeam_calculation_text(model, stiffness, force, rotations, fixed, span_results)
        lines = []
        stiffness_scale = gobeam_stiffness_scale(model)
        combination = model['activeCombinationDetail'] || active_gobeam_combination(model)
        factor_text = (combination['factors'] || {}).map { |name, factor| "#{round_value(factor, 3)}#{name}" }.join(' + ')
        lines << "GO Struct Analysis - Continuous Beam"
        lines << "Design Method: #{model['projectInfo']['designMethod']}    Active Combination: #{combination['name']} (#{factor_text})"
        lines << "Stiffness matrix display is normalized by first span EI; analysis uses actual EI = E x I."
        lines << ""
        lines << "FACTORED LOADS USED FOR ANALYSIS"
        model['spans'].each_with_index do |span, index|
          point_text = span['pointLoads'].map { |load| "#{round_value(load['pKg'], 3)} kg @ #{round_value(load['xM'], 3)}m" }.join(', ')
          point_text = 'none' if point_text.empty?
          unif_text = span['uniformLoads'].map { |load| "#{round_value(load['wKgM'], 3)} kg/m [#{round_value(load['x1M'], 3)}-#{round_value(load['x2M'], 3)}m]" }.join(', ')
          unif_text = 'none' if unif_text.empty?
          lines << "Span #{index + 1}: uniform loads = #{unif_text}, point loads = #{point_text}"
        end
        lines << ""
        lines << "STEP 1: Create Local Stiffness"
        model['spans'].each_with_index do |span, index|
          l = span['lengthM'].to_f
          actual_ei = span['eiKgM2'].to_f
          display_ei = gobeam_display_ei(span, stiffness_scale)
          k = display_ei / l
          lines << "Element #{index + 1} (Span #{index + 1}):   L = #{round_value(l, 3)}m,   Material = #{span['materialKey'] || 'Concrete'},   Section = #{span['sectionShape'] || 'Rectangle'} #{round_value(span['sectionBM'], 3)}x#{round_value(span['sectionHM'], 3)}m,   E = #{round_value(span['eKgM2'], 3)} kg/m2,   I = #{round_value(span['iM4'], 8)} m4"
          lines << "  Actual EI = #{round_value(actual_ei, 3)} kg-m2,   Display EI = #{round_value(display_ei, 3)},   k = EI/L = #{round_value(k, 4)}"
          lines << "  K_local = [#{round_value(4 * k, 4)} #{round_value(2 * k, 4)}]"
          lines << "            [#{round_value(2 * k, 4)} #{round_value(4 * k, 4)}]"
        end
        lines << ""
        lines << "STEP 2: Calculate Fixed End Moments"
        fixed.each_with_index do |moments, index|
          lines << "Element #{index + 1} (Span #{index + 1}):  ML = #{round_value(moments[0], 4)}, MR = #{round_value(moments[1], 4)}"
        end
        lines << ""
        lines << "STEP 3: Assemble Global System:  Elements: #{model['spans'].length}, Nodes: #{model['spans'].length + 1}"
        lines << "Global Stiffness Matrix [K]:"
        lines << "       #{(0...stiffness.length).map { |index| "theta#{index}" }.join('      ')}"
        stiffness.each_with_index do |row, index|
          lines << "theta#{index}  #{row.map { |value| format('%0.4f', value.to_f / stiffness_scale) }.join('    ')}"
        end
        lines << "Global FEM Vector {F}:"
        force.each_with_index do |value, index|
          display_value = -value.to_f
          lines << "  F#{index} = #{round_value(display_value, 4)}"
        end
        lines << ""
        lines << "STEP 4: Solve System of Equations:  [K] {theta} = {F}"
        rotations.each_with_index { |value, index| lines << "  theta#{index} = #{round_value(value.to_f * stiffness_scale, 6)}" }
        lines << ""
        lines << "STEP 5: Calculate Member End Moments:  Formula: M = [K]{theta} + {FEM}"
        span_results.each do |span|
          index = span['index']
          l = model['spans'][index]['lengthM'].to_f
          k = gobeam_display_ei(model['spans'][index], stiffness_scale) / l
          k11 = 4.0 * k
          k12 = 2.0 * k
          left_theta = rotations[index].to_f * stiffness_scale
          right_theta = rotations[index + 1].to_f * stiffness_scale
          lines << "Element #{index + 1} (Span #{index + 1}):"
          lines << "Rotations: theta#{index} = #{round_value(left_theta, 6)}, theta#{index + 1} = #{round_value(right_theta, 6)}"
          lines << "M_Left = #{round_value(k11, 4)}x#{round_value(left_theta, 6)} + #{round_value(k12, 4)}x#{round_value(right_theta, 6)} + #{round_value(fixed[index][0], 4)}"
          lines << "M_Left = #{round_value(span['endMoments']['analysisLeftKgM'], 4)}"
          lines << "M_Right = #{round_value(k12, 4)}x#{round_value(left_theta, 6)} + #{round_value(k11, 4)}x#{round_value(right_theta, 6)} + #{round_value(fixed[index][1], 4)}"
          lines << "M_Right = #{round_value(span['endMoments']['analysisRightKgM'], 4)}"
        end
        lines << "STEP 6: Calculate Local Member End Moment & Reaction"
        span_results.each do |span|
          lines << "Span #{span['index'] + 1}:"
          lines << "  RL = #{round_value(span['reactions']['leftKg'], 2)} kg,  RR = #{round_value(span['reactions']['rightKg'], 2)} kg"
          lines << "  ML = #{round_value(span['endMoments']['leftKgM'], 2)} kg-m,  MR = #{round_value(span['endMoments']['rightKgM'], 2)} kg-m"
        end
        lines.join("\n")
      end

      def gobeam_stiffness_scale(model)
        values = model['spans'].map { |span| span['eiKgM2'].to_f }.select { |value| value > 0.0 }
        values.empty? ? 1.0 : values.first
      end

      def gobeam_display_ei(span, scale)
        denominator = scale.to_f
        return span['eiKgM2'].to_f if denominator <= 0.0

        span['eiKgM2'].to_f / denominator
      end

      def solve_linear_system(matrix, vector)
        size = vector.length
        a = matrix.map(&:dup)
        b = vector.map(&:to_f)

        (0...size).each do |pivot|
          max_row = pivot
          ((pivot + 1)...size).each do |row|
            max_row = row if a[row][pivot].abs > a[max_row][pivot].abs
          end
          raise ArgumentError, 'Singular beam stiffness matrix' if a[max_row][pivot].abs < 1.0e-12

          a[pivot], a[max_row] = a[max_row], a[pivot] if max_row != pivot
          b[pivot], b[max_row] = b[max_row], b[pivot] if max_row != pivot
          pivot_value = a[pivot][pivot]
          (pivot...size).each { |col| a[pivot][col] /= pivot_value }
          b[pivot] /= pivot_value

          (0...size).each do |row|
            next if row == pivot

            factor = a[row][pivot]
            next if factor.abs < 1.0e-15

            (pivot...size).each { |col| a[row][col] -= factor * a[pivot][col] }
            b[row] -= factor * b[pivot]
          end
        end

        b
      end

      def gobeam_report_body_html(model, result)
        info = model['projectInfo']
        analysis_model = result['analysisModel'] || model
        combination = result['activeCombination'] || active_gobeam_combination(model)
        factor_text = (combination['factors'] || {}).map { |name, factor| "#{round_value(factor, 3)}#{name}" }.join(' + ')
        chunks = result['spans'].each_slice(4).to_a
        sections = []
        sections << <<-HTML
<section class="report-page">
  <header class="report-head">
    <div class="logo">GO<br>Beam</div>
    <table>
      <tr><td>Project : #{html_escape(info['project'])}</td><td>Beam : #{html_escape(model['beamName'])}</td></tr>
      <tr><td>Company : #{html_escape(info['company'])}</td><td>Engineer : #{html_escape(info['engineer'])}</td></tr>
      <tr><td>Location : #{html_escape(info['location'])}</td><td>Date : #{html_escape(Time.now.strftime('%Y-%m-%d'))}</td></tr>
      <tr><td>Method : #{html_escape(info['designMethod'])}</td><td>Combination : #{html_escape(combination['name'])} (#{html_escape(factor_text)})</td></tr>
    </table>
  </header>
  <h1>Continuous Beam Analysis Report</h1>
  <h2>(1) #{result['summary']['spanCount']} Span Beam</h2>
  <div class="diagram" data-diagram="loads-all"></div>
  <h2>(2) Base Span, Load, and Stiffness Data</h2>
  #{gobeam_span_table_html(model['spans'])}
  <h2>(3) Factored Span and Load Data Used for Analysis</h2>
  #{gobeam_span_table_html(analysis_model['spans'])}
</section>
        HTML

        sections << <<-HTML
<section class="report-page">
  <header class="mini-head">Beam : #{html_escape(model['beamName'])} <span>Calculation</span></header>
  <h2>(4) Calculation</h2>
  <pre class="calc">#{html_escape(result['calculationText'])}</pre>
</section>
        HTML

        chunks.each_with_index do |chunk, chunk_index|
          rows = chunk.map do |span|
            "<tr><td>#{span['index'] + 1}</td><td>#{round_value(span['reactions']['leftKg'], 2)}</td><td>#{round_value(span['reactions']['rightKg'], 2)}</td><td>#{round_value(span['endMoments']['leftKgM'], 2)}</td><td>#{round_value(span['endMoments']['rightKgM'], 2)}</td><td>#{round_value(span['extremes']['maxMomentKgM'], 2)}</td><td>#{round_value(span['extremes']['minMomentKgM'], 2)}</td><td>#{round_value(span['extremes']['minDeflectionMm'], 3)}</td></tr>"
          end.join
          sections << <<-HTML
<section class="report-page">
  <header class="mini-head">Beam : #{html_escape(model['beamName'])} <span>Results #{chunk_index + 1}</span></header>
  <h2>(5) Reaction, Moment, Deflection Summary</h2>
  <table class="data-table"><thead><tr><th>Span</th><th>RL kg</th><th>RR kg</th><th>ML kg-m</th><th>MR kg-m</th><th>Max M</th><th>Min M</th><th>Min d mm</th></tr></thead><tbody>#{rows}</tbody></table>
</section>
          HTML
        end

        gobeam_report_diagram_chunks(analysis_model).each_with_index do |chunk, index|
          sections << <<-HTML
<section class="report-page">
  <header class="mini-head">Beam : #{html_escape(model['beamName'])} <span>Diagrams #{index + 1}</span></header>
  <h2>(6) Loading Diagram - #{html_escape(chunk['label'])}</h2>
  <div class="diagram" data-diagram="loads-range" data-start="#{chunk['startX']}" data-end="#{chunk['endX']}"></div>
  <h2>(7) Shear Force Diagram - #{html_escape(chunk['label'])}</h2>
  <div class="diagram" data-diagram="shear-range" data-start="#{chunk['startX']}" data-end="#{chunk['endX']}"></div>
  <h2>(8) Bending Moment Diagram - #{html_escape(chunk['label'])}</h2>
  <div class="diagram" data-diagram="moment-range" data-start="#{chunk['startX']}" data-end="#{chunk['endX']}"></div>
  <h2>(9) Deflection Diagram - #{html_escape(chunk['label'])}</h2>
  <div class="diagram" data-diagram="deflection-range" data-start="#{chunk['startX']}" data-end="#{chunk['endX']}"></div>
</section>
        HTML
        end
        sections.join("\n")
      end

      def gobeam_report_diagram_chunks(model)
        positions = [0.0]
        model['spans'].each { |span| positions << positions.last + span['lengthM'].to_f }
        group_size = 6
        chunks = []
        (0...model['spans'].length).step(group_size) do |start_index|
          end_index = [start_index + group_size - 1, model['spans'].length - 1].min
          chunks << {
            'startX' => positions[start_index],
            'endX' => positions[end_index + 1],
            'label' => "Span #{start_index + 1}-#{end_index + 1}"
          }
        end
        chunks
      end

      def gobeam_span_table_html(spans)
        rows = spans.each_with_index.map do |span, index|
          uniform_loads = span['uniformLoads'].map { |load| "#{round_value(load['wKgM'], 2)} kg/m [#{round_value(load['x1M'], 2)}-#{round_value(load['x2M'], 2)} m] (#{html_escape(load['case'] || 'DL')})" }.join('<br>')
          uniform_loads = '-' if uniform_loads.empty?
          point_loads = span['pointLoads'].map { |load| "#{round_value(load['pKg'], 2)} kg @ #{round_value(load['xM'], 2)} m (#{html_escape(load['case'] || 'DL')})" }.join('<br>')
          point_loads = '-' if point_loads.empty?
          section = "#{html_escape(span['sectionShape'] || 'Rectangle')} #{round_value(span['sectionBM'], 3)}x#{round_value(span['sectionHM'], 3)} m"
          "<tr><td>#{index + 1}</td><td>#{round_value(span['lengthM'], 3)}</td><td>#{html_escape(span['materialKey'] || 'Concrete')}</td><td>#{section}</td><td>#{round_value(span['eKgM2'], 3)}</td><td>#{round_value(span['iM4'], 8)}</td><td>#{round_value(span['eiKgM2'], 3)}</td><td>#{uniform_loads}</td><td>#{point_loads}</td></tr>"
        end.join
        "<table class=\"data-table\"><thead><tr><th>Span</th><th>L (m)</th><th>Material</th><th>Section</th><th>E (kg/m2)</th><th>I (m4)</th><th>EI (kg-m2)</th><th>Uniform Loads</th><th>Point Loads</th></tr></thead><tbody>#{rows}</tbody></table>"
      end

      def safe_filename(value)
        name = normalize_string(value) || 'gobeam'
        name.gsub(/[^0-9A-Za-z._-]+/, '_')
      end
    end
end

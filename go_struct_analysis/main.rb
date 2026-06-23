require 'json'
require 'digest'
require 'fileutils'
require 'time'
require 'tmpdir'
require 'uri'

Sketchup.require 'go_struct_analysis/support'
Sketchup.require 'go_struct_analysis/model'
Sketchup.require 'go_struct_analysis/suite'
Sketchup.require 'go_struct_analysis/gobeam'
Sketchup.require 'go_struct_analysis/draw_gobeam'
Sketchup.require 'go_struct_analysis/gotruss'
Sketchup.require 'go_struct_analysis/draw_gotruss'
Sketchup.require 'go_struct_analysis/goframe'
Sketchup.require 'go_struct_analysis/draw_goframe'
Sketchup.require 'go_struct_analysis/section_database'

module GOStructAnalysis
  extend self
  extend Support
  extend Model
  extend Suite
  extend Gobeam
  extend DrawGobeam
  extend Gotruss
  extend DrawGotruss
  extend Goframe
  extend DrawGoframe

  VERSION = 1
  BIM_SCHEMA_VERSION = 1
  TEMPLATE_ROOT = File.join(File.dirname(__FILE__), 'templates')

  @menu_installed = false

  def startup
    install_menu
  rescue StandardError => e
    UI.messagebox("GO Struct Analysis failed:\n#{format_error(e)}")
  end

  def install_menu
    return if @menu_installed

    menu = UI.menu('Extensions').add_submenu('GO Struct Analysis')
    menu.add_item('Open') { show_main_dialog }
    menu.add_item('Continuous Beam') { show_gobeam_dialog }
    menu.add_item('Truss Analysis') { show_gotruss_dialog }
    menu.add_item('2D Frame Analysis') { show_goframe_dialog }

    toolbar = UI::Toolbar.new('GO Struct Analysis')

    cmd_beam = UI::Command.new('Continuous Beam') { show_gobeam_dialog }
    cmd_beam.small_icon = File.join(File.dirname(__FILE__), 'icons', 'gobeam_16.png')
    cmd_beam.large_icon = File.join(File.dirname(__FILE__), 'icons', 'gobeam_24.png')
    cmd_beam.tooltip = 'Continuous Beam Analysis'
    cmd_beam.status_bar_text = 'Open GOBeam X Span'
    cmd_beam.menu_text = 'Continuous Beam'

    toolbar.add_item(cmd_beam)

    cmd_truss = UI::Command.new('Truss Analysis') { show_gotruss_dialog }
    cmd_truss.small_icon = File.join(File.dirname(__FILE__), 'icons', 'gotruss_16.png')
    cmd_truss.large_icon = File.join(File.dirname(__FILE__), 'icons', 'gotruss_24.png')
    cmd_truss.tooltip = 'Pin-jointed Truss Analysis'
    cmd_truss.status_bar_text = 'Open Truss Analysis'
    cmd_truss.menu_text = 'Truss Analysis'

    toolbar.add_item(cmd_truss)

    cmd_frame = UI::Command.new('2D Frame Analysis') { show_goframe_dialog }
    cmd_frame.small_icon = File.join(File.dirname(__FILE__), 'icons', 'goframe_icon.png')
    cmd_frame.large_icon = File.join(File.dirname(__FILE__), 'icons', 'goframe_icon.png')
    cmd_frame.tooltip = '2D Rigid Frame Analysis'
    cmd_frame.status_bar_text = 'Open 2D Frame Analysis'
    cmd_frame.menu_text = '2D Frame Analysis'

    toolbar.add_item(cmd_frame)

    cmd_manual = UI::Command.new('User Manual') { show_manual_dialog }
    cmd_manual.small_icon = File.join(File.dirname(__FILE__), 'icons', 'manual_icon.png')
    cmd_manual.large_icon = File.join(File.dirname(__FILE__), 'icons', 'manual_icon.png')
    cmd_manual.tooltip = 'Open User Manual'
    cmd_manual.status_bar_text = 'Open GO Struct Analysis User Manual'
    cmd_manual.menu_text = 'User Manual'

    toolbar.add_item(cmd_manual)

    toolbar.show

    unless file_loaded?(__FILE__)
      UI.add_context_menu_handler do |context_menu|
        sel = Sketchup.active_model.selection
        if sel.length == 1 && sel[0].respond_to?(:attribute_dictionary)
          dict = sel[0].attribute_dictionary('GOStructAnalysis')
          if dict
            mod_type = dict['module']
            model_json = dict['model_data']
            if mod_type && model_json
              context_menu.add_item("Edit GOStruct #{mod_type}") do
                begin
                  model_data = JSON.parse(model_json)
                  case mod_type
                  when 'Beam'
                    show_gobeam_dialog(model_data: model_data)
                  when 'Truss'
                    show_gotruss_dialog(model_data: model_data)
                  when 'Frame'
                    show_goframe_dialog(model_data: model_data)
                  end
                rescue => e
                  UI.messagebox("Failed to load data:\n#{e.message}")
                end
              end
              context_menu.add_item("Recalculate GOStruct #{mod_type}") do
                begin
                  recalculate_gostruct_entity(sel[0], mod_type, JSON.parse(model_json))
                  UI.messagebox("Recalculated GOStruct #{mod_type} attributes.")
                rescue => e
                  UI.messagebox("Failed to recalculate data:\n#{e.message}")
                end
              end
            end
          end
        end
      end
      file_loaded(__FILE__)
    end

    @menu_installed = true
  end

  def plugin_version
    defined?(EXTENSION) && EXTENSION.respond_to?(:version) ? EXTENSION.version.to_s : 'unknown'
  end

  def canonical_json(value)
    JSON.generate(canonicalize_for_hash(value))
  end

  def canonicalize_for_hash(value)
    case value
    when Hash
      value.keys.map(&:to_s).sort.each_with_object({}) do |key, ordered|
        original_key = value.key?(key) ? key : value.keys.find { |candidate| candidate.to_s == key }
        ordered[key] = canonicalize_for_hash(value[original_key])
      end
    when Array
      value.map { |item| canonicalize_for_hash(item) }
    else
      value
    end
  end

  def bim_model_hash(model_data)
    Digest::SHA256.hexdigest(canonical_json(model_data))
  end

  def selected_gostruct_entity
    entity = Sketchup.active_model.selection.first
    return nil unless entity && entity.respond_to?(:attribute_dictionary)

    entity.attribute_dictionary('GOStructAnalysis') || entity.attribute_dictionary('GOStructElement') ? entity : nil
  end

  def inspect_selected
    entity = selected_gostruct_entity
    unless entity
      puts 'No selected GOStructAnalysis or GOStructElement entity.'
      return nil
    end

    dictionaries = ['GOStructAnalysis', 'GOStructElement'].map { |name| entity.attribute_dictionary(name) }.compact
    puts "GOStruct attributes for #{entity.name}:"
    dictionaries.each do |dict|
      puts "[#{dict.name}]"
      dict.each_pair do |key, value|
        display = value.to_s
        display = "#{display[0, 500]}..." if display.length > 500
        puts "  #{key}: #{display}"
      end
    end
    dictionaries
  end

  def recalculate_gostruct_entity(entity, mod_type, model_data)
    case mod_type
    when 'Beam'
      model = normalize_gobeam_model(model_data)
      result = analyze_gobeam_model(model)
      attach_gobeam_analysis_attributes(entity, model, result)
    when 'Truss'
      full_result = analyze_gotruss_model(model_data)
      result = full_result['result'] || full_result[:result] || full_result
      result = JSON.parse(JSON.generate(result))
      attach_gotruss_analysis_attributes(entity, model_data, result)
    when 'Frame'
      full_result = JSON.parse(JSON.generate(analyze(model_data)))
      combo = entity.get_attribute('GOStructAnalysis', 'analysis_combo', 'Envelope')
      result = goframe_result_for_combo(full_result, combo)
      attach_goframe_analysis_attributes(entity, model_data, result, combo)
    else
      raise "Unsupported GOStruct module: #{mod_type}"
    end
  end

  def goframe_result_for_combo(full_result, combo)
    selected = if combo && combo != 'Envelope'
                 (full_result['cases'] || {})[combo] || (full_result['combos'] || {})[combo]
               end
    selected ||= full_result
    selected['ok'] = full_result['ok']
    selected
  end
end

GOStructAnalysis.startup

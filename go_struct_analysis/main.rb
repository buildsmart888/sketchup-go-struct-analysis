require 'json'
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

module GOStructAnalysis
  extend self
  extend Support
  extend Model
  extend Suite
  extend Gobeam
  extend DrawGobeam
  extend Gotruss
  extend DrawGotruss

  VERSION = 1
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
    toolbar.show

    @menu_installed = true
  end
end

GOStructAnalysis.startup

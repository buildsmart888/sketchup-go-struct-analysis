module GOCarbonCredit
  ROOT_DIR = File.dirname(__FILE__).freeze unless defined?(ROOT_DIR)
  
  require_relative 'config'
  require_relative 'support'
  require_relative 'scanner'
  require_relative 'carbon_engine'
  require_relative 'envelope'
  require_relative 'benchmark'
  require_relative 'suggestions'
  require_relative 'heatmap'
  require_relative 'export'
  require_relative 'ui'

  class Controller
    include Support
    include Scanner
    include CarbonEngine
    include Envelope
    include Benchmark
    include Suggestions
    include Heatmap
    include Export
    include UIHelpers
  end

  @controller = Controller.new

  unless @menu_loaded
    menu = UI.menu('Extensions').add_submenu('GO Carbon Credit')
    
    menu.add_item('🧮 Calculate Carbon / คำนวณคาร์บอน') {
      @controller.show_carbon_summary_dialog
    }
    
    menu.add_item('📊 Carbon Manager') {
      @controller.show_carbon_manager_dialog
    }
    
    menu.add_separator
    
    menu.add_item('🎨 Apply Carbon Heatmap') {
      @controller.apply_heatmap_with_message
    }
    
    menu.add_item('🧹 Remove Carbon Heatmap') {
      @controller.remove_heatmap_with_message
    }
    
    menu.add_separator
    
    menu.add_item('📊 Export Carbon Report (.xls)') {
      @controller.export_carbon_report_dialog
    }
    
    menu.add_item('📄 Export Carbon JSON') {
      @controller.export_carbon_json_dialog
    }
    
    @menu_loaded = true
  end

  def self.controller
    @controller
  end
end

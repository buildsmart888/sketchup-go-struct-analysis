require 'json'
require 'csv'
require 'fileutils'
require 'time'
require 'tmpdir'
require 'uri'

require_relative 'config'
require_relative 'catalog'
require_relative 'support'
require_relative 'analysis'
require_relative 'boq_thai'
require_relative 'bridge'
require_relative 'reporting'
require_relative 'services'
require_relative 'ui'

module Codex
  module SketchUpMCPBridge
    extend self
    extend Support
    extend Analysis
    extend BoqThai
    extend Bridge
    extend Reporting
    extend ReportServices
    extend UIHelpers

    @bridge_started = false
    @bridge_timer = nil
    @last_error = nil
    @menu_installed = false
  end
end

Codex::SketchUpMCPBridge.startup

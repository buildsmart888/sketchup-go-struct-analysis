module Codex
  module SketchUpMCPBridge
    CUBIC_INCH_TO_CUBIC_METER = 0.000016387064
    INCH_TO_METER = 0.0254
    INCH_TO_MILLIMETER = 25.4
    SQUARE_INCH_TO_SQUARE_METER = 0.00064516

    DENSITY_PRESETS = {
      'concrete' => 2400.0,
      'reinforced_concrete' => 2500.0,
      'steel' => 7850.0,
      'grout' => 2200.0,
      'timber' => 600.0,
      'aluminum' => 2700.0
    }.freeze

    DEFAULT_EXCLUDED_TAGS = ['GRID LINE', 'DIMENSIONS'].freeze

    PRESET_FILTERS = {
      'beam' => {
        'tag_filter' => ['Structure-RC_BEAM'],
        'definition_filter' => ['BEAM'],
        'exclude_tag_filter' => DEFAULT_EXCLUDED_TAGS,
        'solid_only' => true,
        'density_preset' => 'reinforced_concrete'
      },
      'column' => {
        'tag_filter' => ['Structure-RC_COLUMN'],
        'definition_filter' => ['COLUMN'],
        'exclude_tag_filter' => DEFAULT_EXCLUDED_TAGS,
        'solid_only' => true,
        'density_preset' => 'reinforced_concrete'
      },
      'footing' => {
        'tag_filter' => ['Structure-RC_FOOTING'],
        'definition_filter' => ['FOOTING'],
        'exclude_tag_filter' => DEFAULT_EXCLUDED_TAGS,
        'solid_only' => true,
        'density_preset' => 'reinforced_concrete'
      }
    }.freeze

    QUEUE_ROOT = File.join(
      ENV['LOCALAPPDATA'] || Dir.home,
      'SketchUpMCPBridge'
    ).freeze
    ROOT_DIR = File.dirname(__FILE__).freeze
    TEMPLATE_ROOT = File.join(ROOT_DIR, 'templates').freeze
    COMMANDS_DIR = File.join(QUEUE_ROOT, 'commands').freeze
    RESULTS_DIR = File.join(QUEUE_ROOT, 'results').freeze
    FAILED_DIR = File.join(QUEUE_ROOT, 'failed').freeze
    POLL_SECONDS = 0.5
  end
end

require 'sketchup.rb'
require 'extensions.rb'

module Codex
  module SketchUpMCPBridge
    EXTENSION = SketchupExtension.new(
      'SketchUp MCP Bridge',
      'sketchup_mcp_bridge/main'
    )
    EXTENSION.creator = 'OpenAI Codex'
    EXTENSION.description = 'Prototype file-queue bridge for SketchUp and MCP.'
    EXTENSION.version = '0.1.0'

    Sketchup.register_extension(EXTENSION, true)
  end
end

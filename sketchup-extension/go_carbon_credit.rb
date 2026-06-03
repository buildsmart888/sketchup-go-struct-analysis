# frozen_string_literal: true
# --------------------------------------------------------------------------
# GO Carbon Credit — SketchUp Extension Loader
# Extension entry point registered with SketchUp's Extension Manager.
# จุดเริ่มต้นของปลั๊กอิน GO Carbon Credit สำหรับ SketchUp
# --------------------------------------------------------------------------

require 'sketchup'
require 'extensions'

module GOCarbonCredit
  EXTENSION = SketchupExtension.new(
    'GO Carbon Credit',
    File.join(File.dirname(__FILE__), 'go_carbon_credit', 'main.rb')
  )
  EXTENSION.version     = '1.0.0'
  EXTENSION.creator     = 'GO'
  EXTENSION.copyright   = '2026'
  EXTENSION.description = 'Calculate embodied carbon from SketchUp model. / คำนวณคาร์บอนฟุตพริ้นท์จากโมเดล SketchUp'
  Sketchup.register_extension(EXTENSION, true)
end

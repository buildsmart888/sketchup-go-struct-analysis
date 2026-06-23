require 'sketchup.rb'
require 'extensions.rb'

module GOStructAnalysis
  EXTENSION = SketchupExtension.new(
    'GO Struct Analysis',
    'go_struct_analysis/main'
  )
  EXTENSION.creator = 'PHORNJED PHONGMANEE'
  EXTENSION.description = 'Modern structural analysis suite for continuous beams and future truss/frame modules.'
  EXTENSION.version = '1.0.4.0'

  Sketchup.register_extension(EXTENSION, true)
end

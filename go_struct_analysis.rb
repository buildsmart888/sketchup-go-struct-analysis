require 'sketchup.rb'
require 'extensions.rb'

module GOStructAnalysis
  EXTENSION = SketchupExtension.new(
    'GO Struct Analysis',
    'go_struct_analysis/main'
  )
  EXTENSION.creator = 'GO'
  EXTENSION.description = 'Modern structural analysis suite for continuous beams and future truss/frame modules.'
  EXTENSION.version = '0.1.0'

  Sketchup.register_extension(EXTENSION, true)
end

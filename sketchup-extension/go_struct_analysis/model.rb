module GOStructAnalysis
  module Model
    STRUCTURAL_MODEL_VERSION = 1

    def default_structural_units
      {
        'length' => 'm',
        'force' => 'kg',
        'moment' => 'kg-m',
        'displacement' => 'mm'
      }
    end

    def default_structural_materials
      [
        { 'id' => 'default', 'name' => 'Default Material', 'eKgM2' => 1.0 }
      ]
    end

    def default_structural_sections
      [
        { 'id' => 'beam-default', 'name' => 'Default Beam Section', 'areaM2' => 1.0, 'iM4' => 1.0 }
      ]
    end

    def gobeam_structural_model(model)
      offset = 0.0
      nodes = [{ 'id' => 'N1', 'xM' => 0.0, 'yM' => 0.0 }]
      members = []
      supports = [{ 'nodeId' => 'N1', 'restraints' => { 'uy' => true } }]
      member_loads = []

      model['spans'].each_with_index do |span, index|
        left_node = "N#{index + 1}"
        right_node = "N#{index + 2}"
        offset += span['lengthM'].to_f
        nodes << { 'id' => right_node, 'xM' => offset, 'yM' => 0.0 }
        supports << { 'nodeId' => right_node, 'restraints' => { 'uy' => true } }
        member_id = "B#{index + 1}"
        members << {
          'id' => member_id,
          'nodeI' => left_node,
          'nodeJ' => right_node,
          'materialId' => 'default',
          'sectionId' => 'beam-default',
          'module' => 'continuous_beam'
        }
        member_loads << {
          'id' => "ML#{index + 1}",
          'memberId' => member_id,
          'case' => span['uniformLoadCase'] || 'DL',
          'uniformFyKgM' => -span['uniformLoadKgM'].to_f,
          'pointLoads' => span['pointLoads'].map do |load|
            {
              'xM' => load['xM'].to_f,
              'fyKg' => -load['pKg'].to_f,
              'case' => load['case'] || 'DL'
            }
          end
        }
      end

      {
        'version' => STRUCTURAL_MODEL_VERSION,
        'sourceModule' => 'continuous_beam',
        'projectInfo' => model['projectInfo'],
        'units' => default_structural_units,
        'materials' => default_structural_materials,
        'sections' => default_structural_sections,
        'nodes' => nodes,
        'members' => members,
        'supports' => supports,
        'nodalLoads' => [],
        'memberLoads' => member_loads,
        'loadCases' => model['loadCases'],
        'loadCombinations' => model['loadCombinations'],
        'activeCombination' => model['activeCombination'],
        'analysisModules' => ['continuous_beam'],
        'results' => {}
      }
    end
  end
end

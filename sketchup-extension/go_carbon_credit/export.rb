module GOCarbonCredit
  module Export
    def export_carbon_json(args)
      path = args['path']
      raise ArgumentError, 'path is required' if path.nil?
      
      result = calculate_carbon(args)
      File.write(path, result.to_json)
      
      { 'path' => path, 'format' => 'json' }
    end

    def export_carbon_excel(args)
      path = args['path']
      raise ArgumentError, 'path is required' if path.nil?
      
      result = calculate_carbon(args)
      sheets = carbon_workbook_sheets(result)
      File.write(path, excel_xml_workbook(sheets))
      
      { 'path' => path, 'format' => 'excel-xml', 'sheetCount' => sheets.length }
    end
    
    def export_carbon_csv(args)
      path = args['path']
      raise ArgumentError, 'path is required' if path.nil?
      
      result = calculate_carbon(args)
      rows = component_export_rows(result['components'])
      headers = rows.first ? rows.first.keys : []
      
      File.write(path, csv_from_rows(rows, headers))
      { 'path' => path, 'format' => 'csv' }
    end

    private

    def carbon_workbook_sheets(r)
      [
        { name: '01_Summary',     rows: [summary_sheet_row(r)] },
        { name: '02_By_Material', rows: r['byMaterial'] },
        { name: '03_By_Category', rows: r['byCategory'] },
        { name: '04_By_Tag',      rows: r['byTag'] },
        { name: '05_Components',  rows: component_export_rows(r['components']) },
        { name: '06_Benchmark',   rows: [r['benchmark']] },
        { name: '07_Envelope',    rows: [r['envelope']] },
        { name: '08_Suggestions', rows: r['suggestions'] },
        { name: '09_Unmatched',   rows: r['unmatchedItems'] },
        { name: '10_EF_Rules',    rows: r['efRules'] }
      ]
    end

    def summary_sheet_row(r)
      s = r['summary'] || {}
      b = r['benchmark'] || {}
      m = r['meta'] || {}
      {
        'Project Name'      => m['projectName'],
        'Building Type'     => m['buildingType'],
        'Floor Area (m2)'   => m['totalFloorAreaM2'],
        'Total Carbon (tCO2e)' => s['totalTCO2e'],
        'Total Carbon (kgCO2e)' => s['totalKgCO2e'],
        'Carbon/m2 (kgCO2e)' => s['carbonPerM2'],
        'Rating'            => s['rating'],
        'Matched Items'     => s['matchedCount'],
        'Unmatched Items'   => s['unmatchedCount']
      }
    end

    def component_export_rows(components)
      components.map do |c|
        {
          'ID'             => c['entityID'],
          'Name'           => c['name'],
          'Definition'     => c['definitionName'],
          'Category'       => c['category'],
          'Tag'            => c['tag'],
          'Material'       => c['material'],
          'Volume(m3)'     => round(c['volumeM3'], 3),
          'Area(m2)'       => round(c['surfaceAreaM2'], 2),
          'Weight(kg)'     => round(c['estimatedWeightKg'], 2),
          'Length(m)'      => round(c['lengthM'], 2),
          'EF_ID'          => c['ef_id'],
          'EF_Material'    => c['ef_material'],
          'EF_Value'       => c['ef_value'],
          'EF_Unit'        => c['ef_unit'],
          'Qty Source'     => c['quantity_source'],
          'Qty Used'       => round(c['quantity_used'], 3),
          'kgCO2e'         => round(c['kgCO2e'], 2)
        }
      end
    end
  end
end

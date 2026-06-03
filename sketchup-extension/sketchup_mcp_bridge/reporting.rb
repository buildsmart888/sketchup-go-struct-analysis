module Codex
  module SketchUpMCPBridge
    module Reporting
      def list_components(args)
        args = apply_filter_defaults(args, false)
        filters = component_filter_options(args)
        selected_only = truthy?(args['selected_only'], false)
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        records = collect_component_records(entities, filters)

        {
          'count' => records.length,
          'selectedOnly' => selected_only,
          'filters' => filter_summary(filters),
          'weight' => weight_summary(filters),
          'units' => units_summary,
          'items' => records
        }
      end

      def export_component_list(args)
        args = apply_filter_defaults(args, true)
        locale = resolve_locale(args['locale'])
        path = args['path']
        raise ArgumentError, 'path is required' if blank?(path)

        filters = component_filter_options(args)
        selected_only = truthy?(args['selected_only'], false)
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        records = collect_component_records(entities, filters)

        FileUtils.mkdir_p(File.dirname(path))
        ext = File.extname(path).downcase
        if ext == '.json'
          File.write(path, JSON.pretty_generate(records))
          format = 'json'
        elsif ext == '.xls' || ext == '.xml'
          ordered_keys = component_export_headers
          write_excel_table(path, localized_text('Component List / รายการชิ้นงาน', locale), labeled_rows(component_export_rows(records), ordered_keys, locale))
          format = 'excel-xml'
        else
          File.write(path, component_records_to_csv(records, locale))
          format = 'csv'
        end

        {
          'path' => path,
          'format' => format,
          'count' => records.length,
          'filters' => filter_summary(filters),
          'weight' => weight_summary(filters),
          'units' => units_summary
        }
      end

      def get_selection_metrics(args)
        args = apply_filter_defaults(args, false)
        filters = component_filter_options(args).merge(
          include_groups: true,
          solid_only: !truthy?(args['include_non_solids'], true)
        )
        entities = Sketchup.active_model.selection.to_a
        items = entities.each_with_object([]) do |entity, results|
          next unless entity.is_a?(Sketchup::ComponentInstance) || entity.is_a?(Sketchup::Group)
          next unless matches_component_filters?(entity, filters, 0)

          results << metric_summary(entity)
        end

        {
          'count' => items.length,
          'filters' => filter_summary(filters),
          'totalVolume' => sum_numeric(items, 'volume'),
          'totalVolumeM3' => sum_numeric(items, 'volumeM3'),
          'totalSurfaceAreaM2' => sum_numeric(items, 'surfaceAreaM2'),
          'totalEstimatedWeightKg' => sum_numeric(items, 'estimatedWeightKg'),
          'weight' => weight_summary(filters),
          'units' => units_summary,
          'items' => items
        }
      end

      def filter_entities_by_tag(args)
        args = apply_filter_defaults(args, false)
        tag_filters = normalize_tag_filters(args['tag_filter'] || args['tag_filters'])
        raise ArgumentError, 'tag_filter is required' if tag_filters.empty?

        selected_only = truthy?(args['selected_only'], false)
        filters = component_filter_options(args).merge(tag_filters: tag_filters)
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        items = collect_component_records(entities, filters)

        {
          'count' => items.length,
          'selectedOnly' => selected_only,
          'filters' => filter_summary(filters),
          'weight' => weight_summary(filters),
          'units' => units_summary,
          'items' => items
        }
      end

      def summarize_component_quantities(args)
        args = apply_filter_defaults(args, true)
        selected_only = truthy?(args['selected_only'], false)
        filters = component_filter_options(args)
        group_keys = normalize_group_keys(args['group_by'])
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        records = collect_component_records(entities, filters)
        rows = aggregate_component_records(records, group_keys)

        {
          'count' => rows.length,
          'selectedOnly' => selected_only,
          'groupBy' => group_keys,
          'filters' => filter_summary(filters),
          'totals' => {
            'instances' => rows.reduce(0) { |sum, row| sum + row['quantity'].to_i },
            'volume' => sum_numeric(rows, 'totalVolume'),
            'totalVolumeM3' => sum_numeric(rows, 'totalVolumeM3'),
            'totalSurfaceAreaM2' => sum_numeric(rows, 'totalSurfaceAreaM2'),
            'estimatedWeightKg' => sum_numeric(rows, 'totalEstimatedWeightKg')
          },
          'weight' => weight_summary(filters),
          'units' => units_summary,
          'rows' => rows
        }
      end

      def export_bom_report(args)
        args = apply_filter_defaults(args, true)
        locale = resolve_locale(args['locale'])
        path = args['path']
        raise ArgumentError, 'path is required' if blank?(path)

        selected_only = truthy?(args['selected_only'], false)
        filters = component_filter_options(args)
        group_keys = normalize_group_keys(args['group_by'])
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        records = collect_component_records(entities, filters)
        rows = aggregate_component_records(records, group_keys)

        FileUtils.mkdir_p(File.dirname(path))
        ext = File.extname(path).downcase
        if ext == '.json'
          File.write(path, JSON.pretty_generate(rows))
          format = 'json'
        elsif ext == '.xls' || ext == '.xml'
          ordered_keys = bom_export_headers(group_keys)
          write_excel_table(path, localized_text('BOM / รายงานปริมาณ', locale), labeled_rows(bom_export_rows(rows, group_keys), ordered_keys, locale))
          format = 'excel-xml'
        else
          File.write(path, bom_rows_to_csv(rows, group_keys, locale))
          format = 'csv'
        end

        {
          'path' => path,
          'format' => format,
          'count' => rows.length,
          'selectedOnly' => selected_only,
          'groupBy' => group_keys,
          'filters' => filter_summary(filters),
          'weight' => weight_summary(filters),
          'units' => units_summary,
          'rows' => rows
        }
      end

      def summarize_tag_totals(args)
        args = apply_filter_defaults(args, true)
        selected_only = truthy?(args['selected_only'], false)
        filters = component_filter_options(args)
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        records = collect_component_records(entities, filters)
        rows = aggregate_by_tag(records)

        {
          'count' => rows.length,
          'selectedOnly' => selected_only,
          'filters' => filter_summary(filters),
          'weight' => weight_summary(filters),
          'units' => units_summary,
          'rows' => rows
        }
      end

      def export_tag_totals_report(args)
        args = apply_filter_defaults(args, true)
        locale = resolve_locale(args['locale'])
        path = args['path']
        raise ArgumentError, 'path is required' if blank?(path)

        result = summarize_tag_totals(args)
        rows = result['rows']
        FileUtils.mkdir_p(File.dirname(path))
        ext = File.extname(path).downcase
        if ext == '.json'
          File.write(path, JSON.pretty_generate(rows))
          format = 'json'
        elsif ext == '.xls' || ext == '.xml'
          ordered_keys = tag_totals_export_headers
          write_excel_table(path, localized_text('Tag Totals / สรุปตามแท็ก', locale), labeled_rows(tag_totals_export_rows(rows), ordered_keys, locale))
          format = 'excel-xml'
        else
          File.write(path, tag_totals_rows_to_csv(rows, locale))
          format = 'csv'
        end

        result.merge('path' => path, 'format' => format)
      end

      def summarize_edge_metrics(args)
        args = apply_filter_defaults(args, false)
        selected_only = truthy?(args['selected_only'], false)
        filters = edge_filter_options(args)
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        records = collect_edge_records(entities, filters)
        rows = aggregate_edge_records(records)

        {
          'count' => rows.length,
          'selectedOnly' => selected_only,
          'filters' => {
            'tagFilters' => filters[:tag_filters],
            'excludeTagFilters' => filters[:exclude_tag_filters],
            'nameFilter' => filters[:name_filter],
            'includeHidden' => filters[:include_hidden],
            'shortEdgeThresholdMm' => filters[:short_edge_threshold_mm]
          },
          'totals' => {
            'edges' => records.length,
            'totalLengthM' => sum_numeric(records, 'lengthM'),
            'shortEdges' => records.count { |row| row['isShortEdge'] },
            'looseEdges' => records.count { |row| row['isLoose'] },
            'hiddenEdges' => records.count { |row| row['hidden'] }
          },
          'units' => units_summary.merge('edgeLengthM' => 'meters', 'edgeLengthMm' => 'millimeters'),
          'rows' => rows
        }
      end

      def export_edge_metrics_report(args)
        args = apply_filter_defaults(args, false)
        locale = resolve_locale(args['locale'])
        path = args['path']
        raise ArgumentError, 'path is required' if blank?(path)

        result = summarize_edge_metrics(args)
        rows = result['rows']
        FileUtils.mkdir_p(File.dirname(path))
        ext = File.extname(path).downcase
        if ext == '.json'
          File.write(path, JSON.pretty_generate(rows))
          format = 'json'
        elsif ext == '.xls' || ext == '.xml'
          ordered_keys = edge_metrics_export_headers
          write_excel_table(path, localized_text('Edge Metrics / ตรวจเส้นและความยาว', locale), labeled_rows(rows, ordered_keys, locale))
          format = 'excel-xml'
        else
          File.write(path, csv_from_rows(rows, edge_metrics_export_headers, locale))
          format = 'csv'
        end

        result.merge('path' => path, 'format' => format)
      end

      def summarize_component_categories(args)
        args = apply_filter_defaults(args, true)
        selected_only = truthy?(args['selected_only'], false)
        filters = component_filter_options(args)
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        records = collect_component_records(entities, filters)
        rows = aggregate_component_records(records, ['category'])

        {
          'count' => rows.length,
          'selectedOnly' => selected_only,
          'filters' => filter_summary(filters),
          'totals' => {
            'instances' => rows.reduce(0) { |sum, row| sum + row['quantity'].to_i },
            'totalVolumeM3' => sum_numeric(rows, 'totalVolumeM3'),
            'totalSurfaceAreaM2' => sum_numeric(rows, 'totalSurfaceAreaM2'),
            'estimatedWeightKg' => sum_numeric(rows, 'totalEstimatedWeightKg')
          },
          'weight' => weight_summary(filters),
          'units' => units_summary,
          'rows' => rows
        }
      end

      def export_component_categories_report(args)
        args = apply_filter_defaults(args, true)
        locale = resolve_locale(args['locale'])
        path = args['path']
        raise ArgumentError, 'path is required' if blank?(path)

        result = summarize_component_categories(args)
        rows = result['rows']
        FileUtils.mkdir_p(File.dirname(path))
        ext = File.extname(path).downcase
        if ext == '.json'
          File.write(path, JSON.pretty_generate(rows))
          format = 'json'
        elsif ext == '.xls' || ext == '.xml'
          ordered_keys = category_export_headers
          write_excel_table(path, localized_text('Categories / หมวดชิ้นงาน', locale), labeled_rows(rows, ordered_keys, locale))
          format = 'excel-xml'
        else
          File.write(path, csv_from_rows(rows, category_export_headers, locale))
          format = 'csv'
        end

        result.merge('path' => path, 'format' => format)
      end

      def export_model_audit_report(args)
        args = apply_filter_defaults(args, true)
        locale = resolve_locale(args['locale'])
        path = args['path']
        raise ArgumentError, 'path is required' if blank?(path)

        result = summarize_model_audit(args)
        FileUtils.mkdir_p(File.dirname(path))
        ext = File.extname(path).downcase
        if ext == '.json'
          File.write(path, JSON.pretty_generate(result))
          format = 'json'
        elsif ext == '.xls' || ext == '.xml'
          sheets = [
            {
              name: localized_text('Summary / สรุป', locale),
              rows: [labeled_hash(result['summary'], model_audit_summary_headers, locale)]
            },
            {
              name: localized_text('Top-level Geometry / เรขาคณิตระดับบน', locale),
              rows: [labeled_hash(result['topLevelGeometry'], model_audit_top_level_headers, locale)]
            },
            {
              name: localized_text('Issues / จุดที่ควรตรวจ', locale),
              rows: labeled_rows(result['issues'], model_audit_issue_headers, locale)
            },
            {
              name: localized_text('Categories / หมวดชิ้นงาน', locale),
              rows: labeled_rows(result['categoryRows'], category_export_headers, locale)
            }
          ]
          write_excel_workbook(path, sheets)
          format = 'excel-xml'
        else
          File.write(path, csv_from_rows(result['issues'], model_audit_issue_headers, locale))
          format = 'csv'
        end

        result.merge('path' => path, 'format' => format)
      end

      def summarize_model_audit(args)
        args = apply_filter_defaults(args, true)
        selected_only = truthy?(args['selected_only'], false)
        component_filters = component_filter_options(args)
        edge_filters = edge_filter_options(args)
        entities = selected_only ? Sketchup.active_model.selection.to_a : Sketchup.active_model.entities.to_a
        component_records = collect_component_records(entities, component_filters)
        edge_records = collect_edge_records(entities, edge_filters)
        top_level = top_level_geometry_summary(entities)
        category_rows = aggregate_component_records(component_records, ['category'])
        issues = audit_issue_rows(component_records, edge_records, top_level)

        {
          'count' => issues.length,
          'selectedOnly' => selected_only,
          'summary' => {
            'components' => component_records.length,
            'edges' => edge_records.length,
            'totalEdgeLengthM' => sum_numeric(edge_records, 'lengthM'),
            'shortEdges' => edge_records.count { |row| row['isShortEdge'] },
            'looseEdges' => edge_records.count { |row| row['isLoose'] },
            'nonSolids' => component_records.count { |row| !row['isSolid'] }
          },
          'topLevelGeometry' => top_level,
          'categoryRows' => category_rows,
          'issues' => issues,
          'units' => units_summary.merge('edgeLengthM' => 'meters')
        }
      end

      def normalize_group_keys(raw)
        keys = normalize_filters(raw)
        return ['definitionName', 'tag', 'material'] if keys.empty?

        keys
      end

      def aggregate_component_records(records, group_keys)
        buckets = {}
        records.each do |record|
          key_values = group_keys.map { |key| normalize_group_value(record[key]) }
          bucket_key = key_values.join('|')
          bucket = buckets[bucket_key] ||= begin
            seed = {}
            group_keys.each_with_index { |key, index| seed[key] = key_values[index] }
            seed.merge(
              'quantity' => 0,
              'totalVolume' => 0.0,
              'totalEstimatedWeightKg' => 0.0,
              'totalVolumeM3' => 0.0,
              'totalSurfaceAreaM2' => 0.0,
              'sumLengthM' => 0.0,
              'sumWidthM' => 0.0,
              'sumHeightM' => 0.0,
              'solidCount' => 0,
              'types' => []
            )
          end

          bucket['quantity'] += 1
          bucket['totalVolume'] += record['volume'].to_f if record['volume']
          bucket['totalEstimatedWeightKg'] += record['estimatedWeightKg'].to_f if record['estimatedWeightKg']
          bucket['totalVolumeM3'] += record['volumeM3'].to_f if record['volumeM3']
          bucket['totalSurfaceAreaM2'] += record['surfaceAreaM2'].to_f if record['surfaceAreaM2']
          bucket['sumLengthM'] += record['lengthM'].to_f if record['lengthM']
          bucket['sumWidthM'] += record['widthM'].to_f if record['widthM']
          bucket['sumHeightM'] += record['heightM'].to_f if record['heightM']
          bucket['solidCount'] += 1 if record['isSolid']
          bucket['types'] << record['type']
        end

        buckets.values.map do |row|
          row['types'] = row['types'].uniq.sort
          quantity = [row['quantity'].to_i, 1].max.to_f
          row['avgLengthM'] = row['sumLengthM'] / quantity
          row['avgWidthM'] = row['sumWidthM'] / quantity
          row['avgHeightM'] = row['sumHeightM'] / quantity
          row.delete('sumLengthM')
          row.delete('sumWidthM')
          row.delete('sumHeightM')
          row
        end.sort_by { |row| group_keys.map { |key| row[key].to_s } }
      end

      def aggregate_by_tag(records)
        buckets = {}
        records.each do |record|
          tag = normalize_group_value(record['tag'])
          bucket = buckets[tag] ||= {
            'tag' => tag,
            'quantity' => 0,
            'definitionCount' => 0,
            'definitions' => [],
            'totalVolumeM3' => 0.0,
            'totalSurfaceAreaM2' => 0.0,
            'totalEstimatedWeightKg' => 0.0,
            'sumLengthM' => 0.0,
            'sumWidthM' => 0.0,
            'sumHeightM' => 0.0
          }

          bucket['quantity'] += 1
          bucket['definitions'] << record['definitionName']
          bucket['totalVolumeM3'] += record['volumeM3'].to_f if record['volumeM3']
          bucket['totalSurfaceAreaM2'] += record['surfaceAreaM2'].to_f if record['surfaceAreaM2']
          bucket['totalEstimatedWeightKg'] += record['estimatedWeightKg'].to_f if record['estimatedWeightKg']
          bucket['sumLengthM'] += record['lengthM'].to_f if record['lengthM']
          bucket['sumWidthM'] += record['widthM'].to_f if record['widthM']
          bucket['sumHeightM'] += record['heightM'].to_f if record['heightM']
        end

        buckets.values.map do |row|
          quantity = [row['quantity'].to_i, 1].max.to_f
          row['definitionCount'] = row['definitions'].uniq.length
          row['avgLengthM'] = row['sumLengthM'] / quantity
          row['avgWidthM'] = row['sumWidthM'] / quantity
          row['avgHeightM'] = row['sumHeightM'] / quantity
          row.delete('definitions')
          row.delete('sumLengthM')
          row.delete('sumWidthM')
          row.delete('sumHeightM')
          row
        end.sort_by { |row| row['tag'].to_s }
      end

      def aggregate_edge_records(records)
        buckets = {}
        records.each do |record|
          tag = normalize_group_value(record['tag'])
          bucket = buckets[tag] ||= {
            'tag' => tag,
            'edgeCount' => 0,
            'totalLengthM' => 0.0,
            'minLengthM' => nil,
            'maxLengthM' => nil,
            'avgLengthM' => 0.0,
            'shortEdgeCount' => 0,
            'looseEdgeCount' => 0,
            'hiddenEdgeCount' => 0,
            'softEdgeCount' => 0,
            'smoothEdgeCount' => 0,
            'curveEdgeCount' => 0
          }

          length_m = record['lengthM'].to_f
          bucket['edgeCount'] += 1
          bucket['totalLengthM'] += length_m
          bucket['minLengthM'] = bucket['minLengthM'].nil? ? length_m : [bucket['minLengthM'], length_m].min
          bucket['maxLengthM'] = bucket['maxLengthM'].nil? ? length_m : [bucket['maxLengthM'], length_m].max
          bucket['shortEdgeCount'] += 1 if record['isShortEdge']
          bucket['looseEdgeCount'] += 1 if record['isLoose']
          bucket['hiddenEdgeCount'] += 1 if record['hidden']
          bucket['softEdgeCount'] += 1 if record['soft']
          bucket['smoothEdgeCount'] += 1 if record['smooth']
          bucket['curveEdgeCount'] += 1 if record['curve']
        end

        buckets.values.map do |row|
          count = [row['edgeCount'].to_i, 1].max.to_f
          row['avgLengthM'] = row['totalLengthM'] / count
          row
        end.sort_by { |row| row['tag'].to_s }
      end

      def bom_rows_to_csv(rows, group_keys, locale = nil)
        csv_from_rows(rows, bom_export_headers(group_keys), locale)
      end

      def component_records_to_csv(records, locale = nil)
        csv_from_rows(component_export_rows(records), component_export_headers, locale)
      end

      def tag_totals_rows_to_csv(rows, locale = nil)
        csv_from_rows(rows, tag_totals_export_headers, locale)
      end

      def component_export_rows(records)
        records.map do |record|
          {
            'type' => record['type'],
            'entityID' => record['entityID'],
            'name' => record['name'],
            'definitionName' => record['definitionName'],
            'category' => record['category'],
            'tag' => record['tag'],
            'depth' => record['depth'],
            'dimensions' => record['dimensions'],
            'lengthM' => record['lengthM'],
            'widthM' => record['widthM'],
            'heightM' => record['heightM'],
            'volumeM3' => record['volumeM3'],
            'surfaceAreaM2' => record['surfaceAreaM2'],
            'estimatedWeightKg' => record['estimatedWeightKg'],
            'material' => record['material'],
            'path' => Array(record['path']).join(' > ')
          }
        end
      end

      def bom_export_rows(rows, group_keys)
        headers = group_keys + %w[quantity totalVolumeM3 totalSurfaceAreaM2 totalEstimatedWeightKg avgLengthM avgWidthM avgHeightM solidCount types]
        rows.map do |row|
          headers.each_with_object({}) do |header, result|
            result[header] = header == 'types' ? Array(row[header]).join(' | ') : row[header]
          end
        end
      end

      def tag_totals_export_rows(rows)
        rows.map do |row|
          {
            'tag' => row['tag'],
            'quantity' => row['quantity'],
            'definitionCount' => row['definitionCount'],
            'avgLengthM' => row['avgLengthM'],
            'avgWidthM' => row['avgWidthM'],
            'avgHeightM' => row['avgHeightM'],
            'totalVolumeM3' => row['totalVolumeM3'],
            'totalSurfaceAreaM2' => row['totalSurfaceAreaM2'],
            'totalEstimatedWeightKg' => row['totalEstimatedWeightKg']
          }
        end
      end

      def component_export_headers
        %w[type entityID name definitionName category tag depth dimensions lengthM widthM heightM volumeM3 surfaceAreaM2 estimatedWeightKg material path]
      end

      def bom_export_headers(group_keys)
        group_keys + %w[quantity totalVolumeM3 totalSurfaceAreaM2 totalEstimatedWeightKg avgLengthM avgWidthM avgHeightM solidCount types]
      end

      def tag_totals_export_headers
        %w[tag quantity definitionCount avgLengthM avgWidthM avgHeightM totalVolumeM3 totalSurfaceAreaM2 totalEstimatedWeightKg]
      end

      def edge_metrics_export_headers
        %w[tag edgeCount totalLengthM avgLengthM minLengthM maxLengthM shortEdgeCount looseEdgeCount hiddenEdgeCount softEdgeCount smoothEdgeCount curveEdgeCount]
      end

      def category_export_headers
        %w[category quantity totalVolumeM3 totalSurfaceAreaM2 totalEstimatedWeightKg avgLengthM avgWidthM avgHeightM solidCount]
      end

      def model_audit_summary_headers
        %w[components edges totalEdgeLengthM shortEdges looseEdges nonSolids]
      end

      def model_audit_top_level_headers
        %w[rawEdges rawFaces rawGroups rawComponents]
      end

      def model_audit_issue_headers
        %w[severity code label count sampleNames]
      end
    end
  end
end

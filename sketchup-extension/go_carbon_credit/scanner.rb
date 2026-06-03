# frozen_string_literal: true
# --------------------------------------------------------------------------
# GO Carbon Credit — Scanner (Entity Traversal & Record Builder)
# สแกนโมเดล SketchUp แล้วสร้าง record สำหรับคำนวณคาร์บอน
# --------------------------------------------------------------------------

module GOCarbonCredit
  module Scanner
    extend self

    # Maximum recursion depth to prevent infinite loops.
    # ความลึกสูงสุดของการสแกนซ้อน เพื่อป้องกัน infinite loop
    MAX_DEPTH = 25

    # ------------------------------------------------------------------
    # Category classification keywords
    # คีย์เวิร์ดสำหรับจำแนกประเภทชิ้นส่วน (ภาษาอังกฤษ + ไทย)
    # ------------------------------------------------------------------
    CATEGORY_PATTERNS = [
      { pattern: /beam|คาน/i,                           category: 'beam'      },
      { pattern: /column|เสา/i,                         category: 'column'    },
      { pattern: /footing|foundation|ฐานราก|ฟุตติ้ง/i,  category: 'footing'   },
      { pattern: /slab|พื้น|แผ่นพื้น/i,                 category: 'slab'      },
      { pattern: /wall|ผนัง|กำแพง/i,                    category: 'wall'      },
      { pattern: /roof|หลังคา/i,                        category: 'roof'      },
      { pattern: /window|หน้าต่าง|กระจก/i,              category: 'window'    },
      { pattern: /door|ประตู/i,                         category: 'door'      },
      { pattern: /stair|บันได/i,                        category: 'stair'     },
      { pattern: /mep|duct|pipe|ท่อ|งานระบบ/i,          category: 'mep'       },
      { pattern: /struct|โครงสร้าง/i,                   category: 'structure' }
    ].freeze

    # ================================================================
    # Public API
    # ================================================================

    # Main entry point — scan model and return array of record hashes.
    # จุดเริ่มต้นหลัก — สแกนโมเดลแล้วคืน array ของ record hashes
    # @param args [Hash] options: 'selected_only' => true/false
    # @return [Array<Hash>]
    def scan_model(args = {})
      model = Sketchup.active_model
      return [] if model.nil?

      if args['selected_only']
        entities = model.selection.to_a
      else
        entities = model.active_entities.to_a
      end

      collect_records(entities, args, '', 0)
    end

    # ================================================================
    # Recursive collection
    # ================================================================

    # Recursively collect records from entities.
    # เก็บ record จาก entities แบบ recursive
    # @param entities [Array<Sketchup::Entity>]
    # @param args [Hash]
    # @param path [String] current path in model hierarchy
    # @param depth [Integer] current depth level
    # @return [Array<Hash>]
    def collect_records(entities, args, path, depth)
      return [] if depth > MAX_DEPTH

      records = []
      entities.each do |entity|
        next unless entity.is_a?(Sketchup::ComponentInstance) ||
                    entity.is_a?(Sketchup::Group)

        # Build the hierarchical path string
        label = Support.entity_label(entity)
        current_path = path.empty? ? label : "#{path} > #{label}"

        # Build record for this entity
        record = build_record(entity, current_path, depth)
        records << record

        # Recurse into children
        child_entities = if entity.is_a?(Sketchup::ComponentInstance)
                           entity.definition.entities.to_a
                         else
                           entity.entities.to_a
                         end
        children = collect_records(child_entities, args, current_path, depth + 1)
        records.concat(children)
      end

      records
    end

    # ================================================================
    # Record builder
    # ================================================================

    # Build a record hash for a single entity.
    # สร้าง record hash สำหรับ entity หนึ่งตัว
    # @param entity [Sketchup::ComponentInstance, Sketchup::Group]
    # @param path [String]
    # @param depth [Integer]
    # @return [Hash]
    def build_record(entity, path, depth)
      # Basic identification
      name       = Support.entity_name(entity)
      def_name   = Support.definition_name(entity)
      tag        = Support.entity_tag(entity)
      material   = Support.entity_material(entity)
      category   = classify_category(entity)

      # Geometry — volume in cubic inches → m³
      vol_in3    = Support.entity_volume(entity)
      volume_m3  = vol_in3 ? Support.round(vol_in3 * CUBIC_INCH_TO_M3, 6) : nil
      is_solid   = !vol_in3.nil?

      # Surface area in m²
      surface_m2 = Support.round(Support.entity_surface_area(entity), 4)

      # Bounding box dimensions → meters
      bounds = entity.bounds
      dims   = Support.sorted_dimensions(bounds)
      length_m = Support.round(dims[0] * INCH_TO_METER, 4)
      width_m  = Support.round(dims[1] * INCH_TO_METER, 4)
      height_m = Support.round(dims[2] * INCH_TO_METER, 4)

      # Density and weight
      density_kg_m3    = Support.infer_density(entity)
      estimated_weight = if density_kg_m3 && volume_m3
                           Support.round(density_kg_m3 * volume_m3, 2)
                         else
                           nil
                         end

      {
        'entityID'          => entity.entityID,
        'name'              => name,
        'definitionName'    => def_name,
        'category'          => category,
        'tag'               => tag,
        'material'          => material,
        'path'              => path,
        'depth'             => depth,
        'volumeM3'          => volume_m3,
        'surfaceAreaM2'     => surface_m2,
        'lengthM'           => length_m,
        'widthM'            => width_m,
        'heightM'           => height_m,
        'isSolid'           => is_solid,
        'densityKgM3'       => density_kg_m3,
        'estimatedWeightKg' => estimated_weight
      }
    end

    # ================================================================
    # Category classification
    # ================================================================

    # Detect structural/architectural category from entity metadata.
    # จำแนกประเภทชิ้นส่วนจาก name/tag/material keywords
    # @param entity [Sketchup::ComponentInstance, Sketchup::Group]
    # @return [String]
    def classify_category(entity)
      text = Support.haystack({
        'name'           => Support.entity_name(entity),
        'definitionName' => Support.definition_name(entity),
        'tag'            => Support.entity_tag(entity),
        'material'       => Support.entity_material(entity),
        'category'       => ''
      })

      CATEGORY_PATTERNS.each do |entry|
        return entry[:category] if text =~ entry[:pattern]
      end

      'generic'
    end

  end # module Scanner
end # module GOCarbonCredit

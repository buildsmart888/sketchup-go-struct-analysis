# frozen_string_literal: true
# --------------------------------------------------------------------------
# GO Carbon Credit — Configuration & Constants
# ค่าคงที่ การแปลงหน่วย ค่าเปรียบเทียบอาคาร สี Heatmap และ CSV headers
# --------------------------------------------------------------------------

module GOCarbonCredit
  # ------------------------------------------------------------------
  # Plugin version / เวอร์ชันปลั๊กอิน
    # ------------------------------------------------------------------
    VERSION = '1.0.0'.freeze

    # ------------------------------------------------------------------
    # Paths / พาธ
    # ------------------------------------------------------------------
    ROOT_DIR      = File.dirname(File.dirname(__FILE__)).freeze
    TEMPLATE_ROOT = File.join(File.dirname(__FILE__), 'templates').freeze

    # ------------------------------------------------------------------
    # Unit conversions / ค่าแปลงหน่วย
    # SketchUp internal unit = inches
    # ------------------------------------------------------------------
    CUBIC_INCH_TO_M3 = 0.000016387064  # 1 in³ → m³
    INCH_TO_METER    = 0.0254           # 1 in  → m
    INCH_TO_MM       = 25.4             # 1 in  → mm
    SQ_INCH_TO_M2    = 0.00064516       # 1 in² → m²

    # ------------------------------------------------------------------
    # Material density presets (kg/m³) / ค่าความหนาแน่นวัสดุ
    # ------------------------------------------------------------------
    DENSITY_PRESETS = {
      'reinforced_concrete' => 2500,
      'concrete'            => 2400,
      'steel'               => 7850,
      'timber'              => 600,
      'aluminum'            => 2700,
      'masonry'             => 1800
    }.freeze

    # ------------------------------------------------------------------
    # Building type benchmarks (kgCO₂e / m²)
    # ค่าเปรียบเทียบคาร์บอนฟุตพริ้นท์ตามประเภทอาคาร
    # [low, typical, high]
    # ------------------------------------------------------------------
    BUILDING_BENCHMARKS = {
      'office' => {
        'label_en' => 'Office',
        'label_th' => 'สำนักงาน',
        'low' => 350, 'typical' => 550, 'high' => 800
      },
      'residential' => {
        'label_en' => 'Residential',
        'label_th' => 'ที่อยู่อาศัย',
        'low' => 200, 'typical' => 400, 'high' => 650
      },
      'condo' => {
        'label_en' => 'Condominium',
        'label_th' => 'คอนโดมิเนียม',
        'low' => 300, 'typical' => 500, 'high' => 750
      },
      'factory' => {
        'label_en' => 'Factory',
        'label_th' => 'โรงงาน',
        'low' => 250, 'typical' => 450, 'high' => 700
      },
      'warehouse' => {
        'label_en' => 'Warehouse',
        'label_th' => 'คลังสินค้า',
        'low' => 150, 'typical' => 300, 'high' => 500
      },
      'hotel' => {
        'label_en' => 'Hotel',
        'label_th' => 'โรงแรม',
        'low' => 400, 'typical' => 600, 'high' => 900
      },
      'hospital' => {
        'label_en' => 'Hospital',
        'label_th' => 'โรงพยาบาล',
        'low' => 500, 'typical' => 750, 'high' => 1100
      },
      'school' => {
        'label_en' => 'School',
        'label_th' => 'โรงเรียน',
        'low' => 250, 'typical' => 420, 'high' => 650
      },
      'temple' => {
        'label_en' => 'Temple',
        'label_th' => 'วัด',
        'low' => 300, 'typical' => 500, 'high' => 800
      },
      'retail' => {
        'label_en' => 'Retail',
        'label_th' => 'ร้านค้า',
        'low' => 350, 'typical' => 550, 'high' => 850
      }
    }.freeze

    # ------------------------------------------------------------------
    # Heatmap color gradient (green → yellow → orange → red-orange → red)
    # สีสำหรับแสดงผล Heatmap (เขียว → แดง)
    # ------------------------------------------------------------------
    HEATMAP_COLORS = [
      Sketchup::Color.new(0,   200, 0),    # green   / เขียว
      Sketchup::Color.new(180, 220, 0),    # yellow  / เหลือง
      Sketchup::Color.new(255, 180, 0),    # orange  / ส้ม
      Sketchup::Color.new(255, 100, 0),    # red-orange / ส้มแดง
      Sketchup::Color.new(220, 0,   0)     # red     / แดง
    ].freeze

    # ------------------------------------------------------------------
    # Emission Factor CSV column headers
    # หัวข้อคอลัมน์ CSV สำหรับ Emission Factor
    # ------------------------------------------------------------------
    EF_HEADERS = %w[
      enabled
      priority
      ef_id
      match_type
      match_value
      material_name_th
      ef_value
      ef_unit
      quantity_source
      data_source
      note
    ].freeze

end # module GOCarbonCredit

module Codex
  module SketchUpMCPBridge
    PRESET_DEFINITIONS = {
      'beam' => {
        'label' => 'Beam / คาน'
      },
      'column' => {
        'label' => 'Column / เสา'
      },
      'footing' => {
        'label' => 'Footing / ฐานราก'
      },
      '' => {
        'label' => 'All / ทั้งหมด'
      }
    }.freeze

    VIEW_DEFINITIONS = {
      'quantities' => {
        'label' => 'Quantities / สรุปจำนวน',
        'title' => 'Component Quantities / สรุปรายการ',
        'filename' => 'component_quantities'
      },
      'tag_totals' => {
        'label' => 'Tag Totals / รวมตามแท็ก',
        'title' => 'Tag Totals / สรุปตามแท็ก',
        'filename' => 'tag_totals'
      },
      'components' => {
        'label' => 'Components / รายการชิ้นงาน',
        'title' => 'Component List / รายการชิ้นงาน',
        'filename' => 'component_list'
      },
      'categories' => {
        'label' => 'Categories / หมวดชิ้นงาน',
        'title' => 'Component Categories / หมวดชิ้นงาน',
        'filename' => 'component_categories'
      },
      'edge_metrics' => {
        'label' => 'Edge Metrics / ตรวจเส้น',
        'title' => 'Edge Metrics / ตรวจเส้นและความยาว',
        'filename' => 'edge_metrics'
      },
      'model_audit' => {
        'label' => 'Model Audit / ตรวจโมเดล',
        'title' => 'Model Audit / ตรวจเช็กโมเดล',
        'filename' => 'model_audit'
      },
      'boq_thai' => {
        'label' => 'BOQ THAI / BOQ ไทย',
        'title' => 'BOQ THAI / BOQ ไทย',
        'filename' => 'boq_thai'
      }
    }.freeze

    DENSITY_OPTION_DEFINITIONS = [
      ['', 'Auto By Material/Tag / อัตโนมัติจากวัสดุหรือแท็ก'],
      ['reinforced_concrete', 'Reinforced Concrete / คอนกรีตเสริมเหล็ก'],
      ['concrete', 'Concrete / คอนกรีต'],
      ['steel', 'Steel / เหล็ก'],
      ['grout', 'Grout / เกร้าท์'],
      ['timber', 'Timber / ไม้'],
      ['aluminum', 'Aluminum / อะลูมิเนียม']
    ].freeze

    FIELD_LABELS = {
      'count' => 'Count / จำนวนรายการ',
      'selectedOnly' => 'Selection Only / เฉพาะที่เลือก',
      'filters' => 'Filters / ตัวกรอง',
      'weight' => 'Weight / น้ำหนัก',
      'units' => 'Units / หน่วย',
      'items' => 'Items / รายการ',
      'rows' => 'Rows / แถวข้อมูล',
      'totals' => 'Totals / ผลรวม',
      'groupBy' => 'Group By / จัดกลุ่มตาม',
      'instances' => 'Instances / จำนวนชิ้น',
      'type' => 'Type / ประเภท',
      'entityID' => 'Entity ID / รหัสวัตถุ',
      'name' => 'Name / ชื่อ',
      'definitionName' => 'Definition / ชื่อแบบ',
      'tag' => 'Tag / แท็ก',
      'category' => 'Category / หมวด',
      'depth' => 'Depth / ระดับซ้อน',
      'isSolid' => 'Solid / เป็น solid',
      'dimensions' => 'Dimensions / ขนาด',
      'lengthM' => 'Length (m) / ยาว (ม.)',
      'widthM' => 'Width (m) / กว้าง (ม.)',
      'heightM' => 'Height (m) / สูง (ม.)',
      'lengthMm' => 'Length (mm) / ยาว (มม.)',
      'widthMm' => 'Width (mm) / กว้าง (มม.)',
      'heightMm' => 'Height (mm) / สูง (มม.)',
      'volume' => 'Volume Raw / ปริมาตรดิบ',
      'volumeM3' => 'Volume (m3) / ปริมาตร (ลบ.ม.)',
      'surfaceAreaM2' => 'Surface Area (m2) / พื้นที่ผิว (ตร.ม.)',
      'estimatedWeightKg' => 'Weight (kg) / น้ำหนัก (กก.)',
      'material' => 'Material / วัสดุ',
      'path' => 'Path / ตำแหน่งในลำดับชั้น',
      'quantity' => 'Quantity / จำนวน',
      'totalVolume' => 'Total Volume Raw / ปริมาตรรวมดิบ',
      'totalVolumeM3' => 'Total Volume (m3) / ปริมาตรรวม (ลบ.ม.)',
      'totalSurfaceAreaM2' => 'Total Surface Area (m2) / พื้นที่ผิวรวม (ตร.ม.)',
      'totalEstimatedWeightKg' => 'Total Weight (kg) / น้ำหนักรวม (กก.)',
      'avgLengthM' => 'Avg Length (m) / ยาวเฉลี่ย (ม.)',
      'avgWidthM' => 'Avg Width (m) / กว้างเฉลี่ย (ม.)',
      'avgHeightM' => 'Avg Height (m) / สูงเฉลี่ย (ม.)',
      'solidCount' => 'Solid Count / จำนวน solid',
      'edgeCount' => 'Edge Count / จำนวนเส้น',
      'totalLengthM' => 'Total Length (m) / ความยาวรวม (ม.)',
      'minLengthM' => 'Min Length (m) / ความยาวต่ำสุด (ม.)',
      'maxLengthM' => 'Max Length (m) / ความยาวสูงสุด (ม.)',
      'shortEdgeCount' => 'Short Edge Count / จำนวนเส้นสั้น',
      'looseEdgeCount' => 'Loose Edge Count / จำนวนเส้นลอย',
      'hiddenEdgeCount' => 'Hidden Edge Count / จำนวนเส้นซ่อน',
      'softEdgeCount' => 'Soft Edge Count / จำนวนเส้น soft',
      'smoothEdgeCount' => 'Smooth Edge Count / จำนวนเส้น smooth',
      'curveEdgeCount' => 'Curve Edge Count / จำนวนเส้นโค้ง',
      'hidden' => 'Hidden / ซ่อน',
      'soft' => 'Soft / soft',
      'smooth' => 'Smooth / smooth',
      'curve' => 'Curve / เส้นโค้ง',
      'facesCount' => 'Faces Count / จำนวนหน้า',
      'isLoose' => 'Loose Edge / เส้นลอย',
      'isShortEdge' => 'Short Edge / เส้นสั้น',
      'types' => 'Types / ชนิด',
      'definitionCount' => 'Definition Count / จำนวนแบบ',
      'includeGroups' => 'Include Groups / รวมกลุ่ม',
      'tagFilters' => 'Tag Filters / ตัวกรองแท็ก',
      'excludeTagFilters' => 'Exclude Tags / ไม่รวมแท็ก',
      'nameFilter' => 'Name Filter / ตัวกรองชื่อ',
      'materialFilters' => 'Material Filters / ตัวกรองวัสดุ',
      'definitionFilters' => 'Definition Filters / ตัวกรองแบบ',
      'minDepth' => 'Min Depth / ระดับต่ำสุด',
      'maxDepth' => 'Max Depth / ระดับสูงสุด',
      'solidOnly' => 'Solid Only / เฉพาะ solid',
      'includeHidden' => 'Include Hidden / รวมเส้นซ่อน',
      'shortEdgeThresholdMm' => 'Short Edge Threshold (mm) / เกณฑ์เส้นสั้น (มม.)',
      'densityMode' => 'Density Mode / โหมดความหนาแน่น',
      'densityPreset' => 'Density Preset / ชุดความหนาแน่น',
      'densityKgM3' => 'Density (kg/m3) / ความหนาแน่น (กก./ลบ.ม.)',
      'autoRules' => 'Auto Rules / กฎอัตโนมัติ',
      'summary' => 'Summary / สรุป',
      'topLevelGeometry' => 'Top-level Geometry / เรขาคณิตระดับบน',
      'issues' => 'Issues / จุดที่ควรตรวจ',
      'severity' => 'Severity / ระดับ',
      'code' => 'Code / รหัส',
      'label' => 'Label / รายการ',
      'sampleNames' => 'Sample Names / ตัวอย่างชื่อ',
      'rawEdges' => 'Top-level Edges / เส้นระดับบน',
      'rawFaces' => 'Top-level Faces / หน้าเปิดระดับบน',
      'rawGroups' => 'Top-level Groups / กลุ่มระดับบน',
      'rawComponents' => 'Top-level Components / คอมโพเนนต์ระดับบน',
      'components' => 'Components / ชิ้นงาน',
      'edges' => 'Edges / เส้น',
      'shortEdges' => 'Short Edges / เส้นสั้น',
      'looseEdges' => 'Loose Edges / เส้นลอย',
      'hiddenEdges' => 'Hidden Edges / เส้นซ่อน',
      'totalEdgeLengthM' => 'Total Edge Length (m) / ความยาวเส้นรวม (ม.)',
      'nonSolids' => 'Non-solids / ชิ้นงานไม่เป็น solid',
      'categoryRows' => 'Category Rows / หมวดชิ้นงาน',
      'no' => 'ลำดับ / No.',
      'item_code' => 'รหัสรายการ / Item Code',
      'description_th' => 'รายการ / Description',
      'unit' => 'หน่วย / Unit',
      'material_unit_cost' => 'ค่าวัสดุ/หน่วย / Material Unit Cost',
      'material_amount' => 'รวมค่าวัสดุ / Material Amount',
      'labor_unit_cost' => 'ค่าแรง/หน่วย / Labor Unit Cost',
      'labor_amount' => 'รวมค่าแรง / Labor Amount',
      'total_amount' => 'รวมเป็นเงิน / Total Amount',
      'source' => 'แหล่งข้อมูล / Source',
      'note' => 'หมายเหตุ / Note',
      'rawTakeoff' => 'Raw Takeoff / ข้อมูลถอดปริมาณดิบ',
      'priceRules' => 'Price Rules / กฎราคา',
      'unmatchedItems' => 'Unmatched Items / รายการที่ยังไม่จับคู่',
      'priceRulesPath' => 'Price Rules Path / ที่อยู่ไฟล์กฎราคา',
      'priceRulesCount' => 'Price Rules Count / จำนวนกฎราคา',
      'materialAmount' => 'รวมค่าวัสดุ / Material Amount',
      'laborAmount' => 'รวมค่าแรง / Labor Amount',
      'totalAmount' => 'รวมทั้งสิ้น / Total Amount',
      'unmatchedCount' => 'Unmatched Count / รายการที่ยังไม่จับคู่',
      'quantity_hint' => 'Quantity Hint / ปริมาณที่พบ',
      'reason' => 'Reason / เหตุผล',
      'rule_id' => 'Rule ID / รหัสกฎ',
      'match_type' => 'Match Type / วิธีจับคู่',
      'match_value' => 'Match Value / ค่าใช้จับคู่',
      'quantity_source' => 'Quantity Source / แหล่งปริมาณ',
      'waste_percent' => 'Waste (%) / เผื่อสูญเสีย (%)'
    }.freeze
  end
end

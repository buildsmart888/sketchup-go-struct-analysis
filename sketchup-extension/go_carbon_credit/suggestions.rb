module GOCarbonCredit
  module Suggestions
    def build_suggestions(matched, building_type, envelope)
      tips = []

      # 1. อิฐแดง → อิฐมวลเบา (25% saving)
      brick = matched.select { |r| r['ef_id'].to_s =~ /BK002|brick/i || r['ef_material'].to_s.include?('อิฐแดง') }
      unless brick.empty?
        saving = brick.reduce(0.0) { |sum, r| sum + r['kgCO2e'].to_f } * 0.25
        tips << tip('MAT001', 'เปลี่ยนอิฐแดง → อิฐมวลเบา (Q-CON)', 'Switch red brick to lightweight block', saving, 'easy', 'material_substitution')
      end

      # 2. เหล็กรีไซเคิล (45% saving)
      steel = matched.select { |r| r['category'] == 'beam' || r['ef_material'].to_s.include?('เหล็ก') || r['ef_id'].to_s =~ /ST001|ST002/ }
      unless steel.empty?
        saving = steel.reduce(0.0) { |sum, r| sum + r['kgCO2e'].to_f } * 0.45
        tips << tip('MAT002', 'ใช้เหล็กรีไซเคิล (EAF Steel)', 'Use recycled EAF steel', saving, 'medium', 'material_substitution')
      end

      # 3. Solar PV (from envelope data)
      if envelope && envelope['solarPvKwp'].to_f > 0
        tips << tip('ENR001', "ติดตั้ง Solar PV บนหลังคา (#{envelope['solarPvKwp']} kWp)", "Install rooftop solar PV (#{envelope['solarPvKwp']} kWp)", envelope['solarOffsetTCO2eYear'].to_f * 1000, 'medium', 'renewable_energy')
      end

      # 4. ไม้วิศวกรรม สำหรับคานสั้น ≤ 6m
      short_beams = matched.select { |r| r['category'] == 'beam' && r['lengthM'].to_f > 0 && r['lengthM'].to_f <= 6 && r['ef_material'].to_s.include?('คอนกรีต') }
      unless short_beams.empty?
        saving = short_beams.reduce(0.0) { |sum, r| sum + r['kgCO2e'].to_f } * 1.2 # > 100% savings due to carbon sink properties of timber
        tips << tip('MAT003', "ใช้ไม้วิศวกรรมแทนคานสั้น (#{short_beams.length} ชิ้น, ยาว ≤ 6m)", "Use Glulam timber for short beams (#{short_beams.length} items, span ≤ 6m)", saving, 'hard', 'design_change')
      end
      
      # 5. ลด WWR
      if envelope && envelope['wwr'].to_f > 0.4
        wwr = envelope['wwr'].to_f
        tips << tip('ENV001', "ลดสัดส่วนกระจกต่อผนัง (WWR = #{round(wwr, 2)}) ให้น้อยกว่า 40%", "Reduce Window-to-Wall Ratio (WWR = #{round(wwr, 2)}) to below 40%", 0, 'medium', 'envelope_design')
      end

      tips
    end

    private

    def tip(id, title_th, title_en, saving_kgco2e, difficulty, category)
      {
        'id'           => id,
        'titleTh'      => title_th,
        'titleEn'      => title_en,
        'savingKgCO2e' => round(saving_kgco2e, 0),
        'difficulty'   => difficulty,
        'category'     => category
      }
    end
  end
end

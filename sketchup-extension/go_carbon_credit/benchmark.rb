module GOCarbonCredit
  module Benchmark
    def carbon_rating(total_kgco2e, floor_area_m2, building_type)
      per_m2 = total_kgco2e / (floor_area_m2 > 0 ? floor_area_m2 : 1.0)
      bench  = BUILDING_BENCHMARKS[building_type.to_s] || BUILDING_BENCHMARKS['office']
      letter = rate_letter(per_m2, bench)
      
      {
        'buildingType'   => building_type,
        'buildingTypeTh' => bench['label_th'],
        'kgCO2ePerM2'    => round(per_m2, 1),
        'rating'         => letter,
        'ratingLabel'    => rating_label(letter),
        'benchmarkLow'   => bench['low'],
        'benchmarkAvg'   => bench['typical'],
        'benchmarkHigh'  => bench['high']
      }
    end

    def rate_letter(per_m2, bench)
      return 'A' if per_m2 < bench['low']
      return 'B' if per_m2 < bench['typical']
      return 'C' if per_m2 < bench['high']
      return 'D' if per_m2 < bench['high'] * 1.3
      'E'
    end

    def rating_label(letter)
      case letter.to_s.upcase
      when 'A' then 'ดีมาก / Excellent'
      when 'B' then 'ดี / Good'
      when 'C' then 'ค่าเฉลี่ย / Average'
      when 'D' then 'สูงกว่าเฉลี่ย / Above Average'
      when 'E' then 'สูงมาก / High'
      else 'ไม่ทราบ / Unknown'
      end
    end
  end
end

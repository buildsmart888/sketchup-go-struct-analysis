module GOCarbonCredit
  module Envelope
    def analyze_envelope(records)
      wall   = sum_area(records, 'wall')
      window = sum_area(records, 'window')
      roof   = sum_area(records, 'roof')
      floor  = sum_area(records, 'slab')
      
      wwr = wall > 0 ? round(window / wall, 3) : nil
      
      # Estimate solar PV potential (kWp): roof_area * 15% efficiency * 20% active area ratio * 1.1 oversize
      solar_pv_kwp = round(roof * 0.15 * 0.20 * 1.1, 1)
      
      # Estimate annual offset (tCO2e/year): kWp * 1350 hrs * 0.4781 kgCO2e/kWh / 1000
      solar_offset = round(solar_pv_kwp * 1350 * 0.4781 / 1000.0, 1)
      
      {
        'wallAreaM2'           => round(wall, 2),
        'windowAreaM2'         => round(window, 2),
        'roofAreaM2'           => round(roof, 2),
        'floorAreaM2'          => round(floor, 2),
        'wwr'                  => wwr,
        'solarPvKwp'           => solar_pv_kwp,
        'solarOffsetTCO2eYear' => solar_offset
      }
    end

    def estimate_floor_area(records)
      area = sum_area(records, 'slab')
      area > 0 ? area : 100.0 # fallback if no slab found
    end

    private

    def sum_area(records, category)
      records.reduce(0.0) do |sum, r|
        r['category'] == category ? sum + r['surfaceAreaM2'].to_f : sum
      end
    end
  end
end

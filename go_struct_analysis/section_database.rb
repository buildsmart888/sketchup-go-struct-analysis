require 'json'

module GOStructAnalysis
  module SectionDatabase
    # Density in kg/m3, E in kg/m2
    STEEL_DENSITY = 7850.0
    STEEL_E = 2e10
    CONCRETE_DENSITY = 2400.0
    CONCRETE_E = 2e9

    # Standard Database Structure
    DEFAULT_DATABASE = {
      "H-Beam" => [
        { "name" => "H-150x150x7x10", "a" => 40.14, "i" => 1640.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "I-Section", "h" => 0.15, "b" => 0.15, "tw" => 0.007, "tf" => 0.010 } },
        { "name" => "H-200x200x8x12", "a" => 63.53, "i" => 4720.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "I-Section", "h" => 0.20, "b" => 0.20, "tw" => 0.008, "tf" => 0.012 } },
        { "name" => "H-250x250x9x14", "a" => 92.18, "i" => 10800.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "I-Section", "h" => 0.25, "b" => 0.25, "tw" => 0.009, "tf" => 0.014 } },
        { "name" => "H-300x150x6.5x9", "a" => 46.78, "i" => 7210.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "I-Section", "h" => 0.30, "b" => 0.15, "tw" => 0.0065, "tf" => 0.009 } },
        { "name" => "H-300x300x10x15", "a" => 119.8, "i" => 20400.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "I-Section", "h" => 0.30, "b" => 0.30, "tw" => 0.010, "tf" => 0.015 } },
        { "name" => "H-350x175x7x11", "a" => 63.14, "i" => 13600.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "I-Section", "h" => 0.35, "b" => 0.175, "tw" => 0.007, "tf" => 0.011 } },
        { "name" => "H-400x200x8x13", "a" => 84.12, "i" => 23700.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "I-Section", "h" => 0.40, "b" => 0.20, "tw" => 0.008, "tf" => 0.013 } }
      ],
      "Pipe" => [
        { "name" => "Pipe-65x3.2", "a" => 7.35, "i" => 48.9, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Pipe", "d" => 0.0763, "t" => 0.0032 } },
        { "name" => "Pipe-100x3.2", "a" => 11.17, "i" => 171.1, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Pipe", "d" => 0.1143, "t" => 0.0032 } },
        { "name" => "Pipe-100x4.5", "a" => 15.54, "i" => 233.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Pipe", "d" => 0.1143, "t" => 0.0045 } },
        { "name" => "Pipe-150x4.5", "a" => 22.72, "i" => 736.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Pipe", "d" => 0.1652, "t" => 0.0045 } },
        { "name" => "Pipe-200x6.0", "a" => 39.64, "i" => 2195.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Pipe", "d" => 0.2163, "t" => 0.0060 } }
      ],
      "C-Channel" => [
        { "name" => "C-75x40x5x7", "a" => 8.818, "i" => 75.3, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.075, "w" => 0.040 } },
        { "name" => "C-100x50x5x7.5", "a" => 11.92, "i" => 188.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.100, "w" => 0.050 } },
        { "name" => "C-150x75x6.5x10", "a" => 23.71, "i" => 861.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.150, "w" => 0.075 } }
      ],
      "Box" => [
        { "name" => "Box-50x50x2.3", "a" => 4.301, "i" => 16.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.05, "w" => 0.05 } },
        { "name" => "Box-100x100x3.2", "a" => 12.08, "i" => 184.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.10, "w" => 0.10 } },
        { "name" => "Box-150x150x4.5", "a" => 25.86, "i" => 891.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.15, "w" => 0.15 } }
      ],
      "Angle" => [
        { "name" => "L-50x50x4", "a" => 3.89, "i" => 8.95, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.05, "w" => 0.05 } },
        { "name" => "L-100x100x7", "a" => 13.62, "i" => 128.0, "e" => STEEL_E, "density" => STEEL_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.10, "w" => 0.10 } }
      ],
      "Concrete" => [
        { "name" => "Column 0.2x0.2", "a" => 400.0, "i" => 13333.3, "e" => CONCRETE_E, "density" => CONCRETE_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.20, "w" => 0.20 } },
        { "name" => "Column 0.3x0.3", "a" => 900.0, "i" => 67500.0, "e" => CONCRETE_E, "density" => CONCRETE_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.30, "w" => 0.30 } },
        { "name" => "Beam 0.2x0.4", "a" => 800.0, "i" => 106666.6, "e" => CONCRETE_E, "density" => CONCRETE_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.40, "w" => 0.20 } },
        { "name" => "Beam 0.3x0.5", "a" => 1500.0, "i" => 312500.0, "e" => CONCRETE_E, "density" => CONCRETE_DENSITY, "shape" => { "type" => "Rectangular", "h" => 0.50, "w" => 0.30 } }
      ],
      "Custom" => []
    }

    def self.user_sections_path
      File.join(__dir__, 'user_sections.json')
    end

    def self.load_user_sections
      return [] unless File.exist?(user_sections_path)
      begin
        content = File.read(user_sections_path)
        JSON.parse(content)
      rescue StandardError => e
        puts "GOStructAnalysis: Failed to load user_sections.json - #{e.message}"
        []
      end
    end

    def self.save_user_section(section_hash)
      sections = load_user_sections
      sections << section_hash
      File.write(user_sections_path, JSON.pretty_generate(sections))
    end

    def self.delete_user_section(index)
      sections = load_user_sections
      sections.delete_at(index) if index >= 0 && index < sections.length
      File.write(user_sections_path, JSON.pretty_generate(sections))
    end

    def self.get_full_database_json
      db = DEFAULT_DATABASE.dup
      db["Custom"] = load_user_sections
      JSON.generate(db)
    end
  end
end

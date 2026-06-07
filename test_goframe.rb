require_relative 'go_struct_analysis/suite.rb'
require_relative 'go_struct_analysis/goframe.rb'

data = {
  "settings" => { "include_self_weight" => true },
  "nodes" => [
    { "id" => 1, "x" => 0, "y" => 0, "support" => "Fixed" },
    { "id" => 2, "x" => 4, "y" => 0, "support" => "Fixed" },
    { "id" => 3, "x" => 0, "y" => 3, "support" => "Free" },
    { "id" => 4, "x" => 4, "y" => 3, "support" => "Free" }
  ],
  "sections" => [
    { "id" => 1, "e" => 2e9, "a" => 900, "i" => 67500, "density" => 2400 },
    { "id" => 2, "e" => 2e9, "a" => 1500, "i" => 312500, "density" => 2400 }
  ],
  "elements" => [
    { "id" => 1, "n1" => 1, "n2" => 3, "sec" => 1 },
    { "id" => 2, "n1" => 2, "n2" => 4, "sec" => 1 },
    { "id" => 3, "n1" => 3, "n2" => 4, "sec" => 2 }
  ],
  "nloads" => [],
  "eloads" => []
}

res = GOStructAnalysis::Goframe.analyze(data)
puts "Result: #{res[:ok]}"
puts "Error: #{res[:error]}" if !res[:ok]

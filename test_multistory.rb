require_relative 'go_struct_analysis/suite.rb'
require_relative 'go_struct_analysis/goframe.rb'

# Mimic JS Multi-story generation
nx = 2
ny = 2
lx = 4.0
ly = 3.0

nodes = []
node_id = 1
(0..ny).each do |j|
  (0..nx).each do |i|
    nodes << { "id" => node_id, "x" => i*lx, "y" => j*ly, "support" => (j == 0 ? "Fixed" : "Free") }
    node_id += 1
  end
end

elements = []
elem_id = 1
# Columns (Section 1)
(0...ny).each do |j|
  (0..nx).each do |i|
    n1 = nodes.find{|n| n["x"] == i*lx && n["y"] == j*ly}["id"]
    n2 = nodes.find{|n| n["x"] == i*lx && n["y"] == (j+1)*ly}["id"]
    elements << { "id" => elem_id, "n1" => n1, "n2" => n2, "sec" => 1 }
    elem_id += 1
  end
end
# Beams (Section 2)
(1..ny).each do |j|
  (0...nx).each do |i|
    n1 = nodes.find{|n| n["x"] == i*lx && n["y"] == j*ly}["id"]
    n2 = nodes.find{|n| n["x"] == (i+1)*lx && n["y"] == j*ly}["id"]
    elements << { "id" => elem_id, "n1" => n1, "n2" => n2, "sec" => 2 }
    elem_id += 1
  end
end

sections = [
  { "id" => 1, "e" => 2e9, "a" => 900, "i" => 67500, "density" => 2400 },
  { "id" => 2, "e" => 2e9, "a" => 1500, "i" => 312500, "density" => 2400 }
]

data = {
  "settings" => { "include_self_weight" => true },
  "nodes" => nodes,
  "elements" => elements,
  "sections" => sections,
  "nloads" => [],
  "eloads" => []
}

res = GOStructAnalysis::Goframe.analyze(data)
puts "Result: #{res[:ok]}"
puts "Error: #{res[:error]}" if !res[:ok]

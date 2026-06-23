require 'fileutils'

# Function to build SketchUp .rbz file using rubyzip
# Requires rubyzip gem (`gem install rubyzip`)
def build_rbz(extension_name, root_file, version)
  begin
    require 'zip'
  rescue LoadError
    puts "Error: rubyzip gem is not installed."
    puts "Please run: gem install rubyzip"
    exit 1
  end

  build_dir = 'build_temp'
  zip_file = "#{extension_name}_v#{version}.rbz"

  # Clean up old build temp and target file
  FileUtils.rm_rf(build_dir) if Dir.exist?(build_dir)
  FileUtils.rm_f(zip_file)
  FileUtils.mkdir_p(build_dir)

  puts "Preparing files in #{build_dir}..."

  # Copy root file
  if File.exist?(root_file)
    FileUtils.cp(root_file, build_dir)
  else
    puts "Error: Root file #{root_file} not found!"
    exit 1
  end

  # Ensure the extension's support folder exists
  target_folder_name = File.basename(root_file, '.rb')
  target_dir = File.join(build_dir, target_folder_name)
  FileUtils.mkdir_p(target_dir)

  # Copy subdirectories and files
  if Dir.exist?(target_folder_name)
    Dir.glob("#{target_folder_name}/**/*").each do |src|
      dest = File.join(build_dir, src)

      # Exclude test files, hidden files, or docs if needed
      next if src.include?('test_')
      next if src.end_with?('.md')
      next if src.include?('.git')

      if File.directory?(src)
        FileUtils.mkdir_p(dest)
      else
        FileUtils.mkdir_p(File.dirname(dest))
        FileUtils.cp(src, dest)
      end
    end
  end

  puts "Creating #{zip_file} using rubyzip to ensure correct directory entries..."

  Zip::File.open(zip_file, create: true) do |zipfile|
    # Add root file
    zipfile.add(File.basename(root_file), File.join(build_dir, File.basename(root_file)))

    # Add folder entry explicitly (CRITICAL FOR EXTENSION WAREHOUSE)
    zipfile.mkdir(target_folder_name + '/') unless zipfile.find_entry(target_folder_name + '/')

    # Add all files and subdirectories
    Dir.glob(File.join(build_dir, target_folder_name, '**', '*')).each do |file|
      zip_path = file.sub(build_dir + '/', '')

      if File.directory?(file)
        zipfile.mkdir(zip_path + '/') unless zip_path.end_with?('/') || zipfile.find_entry(zip_path + '/')
      else
        zipfile.add(zip_path, file)
      end
    end
  end

  FileUtils.rm_rf(build_dir)
  puts "Successfully created #{zip_file} (#{File.size(zip_file)} bytes)."
end

if __FILE__ == $0
  build_rbz('go_struct_analysis', 'go_struct_analysis.rb', '1.0.4.0')
end

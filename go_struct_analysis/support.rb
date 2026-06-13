module GOStructAnalysis
  module Support
    def blank?(value)
      value.nil? || value.to_s.strip.empty?
    end

    def normalize_string(value)
      return nil if blank?(value)

      value.to_s.strip
    end

    def stringify_keys(value)
      return {} if value.nil?

      value.each_with_object({}) do |(key, inner_value), result|
        result[key.to_s] = inner_value
      end
    end

    def parse_dialog_payload(payload)
      return stringify_keys(payload) if payload.is_a?(Hash)

      raw = payload.to_s
      begin
        parsed = JSON.parse(raw)
        return stringify_keys(parsed)
      rescue JSON::ParserError
        begin
          decoded = URI.decode_www_form_component(raw)
          parsed = JSON.parse(decoded)
          return stringify_keys(parsed)
        rescue StandardError
          return {}
        end
      end
    rescue StandardError
      {}
    end

    def numeric_or_default(value, default)
      value.nil? ? default : value.to_f
    end

    def numeric_or_nil(value)
      value.nil? || blank?(value) ? nil : value.to_f
    end

    def html_escape(value)
      value.to_s.gsub('&', '&amp;').gsub('<', '&lt;').gsub('>', '&gt;').gsub('"', '&quot;')
    end

    def format_error(error)
      "#{error.class}: #{error.message}"
    end

    def load_template(name)
      @template_cache ||= {}
      return @template_cache[name] if @template_cache.key?(name)

      path = File.join(TEMPLATE_ROOT, name)
      @template_cache[name] = File.read(path)
    end

    def render_template(name, replacements = {})
      template = load_template(name).dup
      replacements.each do |key, value|
        template.gsub!("{{#{key}}}", value.to_s)
      end
      template
    end

    def present_dialog(dialog, width:, height:, left: 80, top: 80)
      dialog.set_size(width, height) if dialog.respond_to?(:set_size)
      dialog.set_position(left, top) if dialog.respond_to?(:set_position)
      dialog.show
      dialog.bring_to_front if dialog.respond_to?(:bring_to_front)
      dialog
    end

    def clear_dialog_on_close(dialog, ivar_name)
      if dialog.respond_to?(:set_on_closed)
        dialog.set_on_closed { instance_variable_set(ivar_name, nil) }
      else
        dialog.set_on_close { instance_variable_set(ivar_name, nil) }
      end
    end

    def json_script_value(value)
      value.nil? ? 'null' : JSON.generate(value).gsub("</", "<\\/")
    end

    def round_value(value, digits = 3)
      rounded = value.to_f.round(digits)
      rounded == rounded.to_i ? rounded.to_i.to_s : rounded.to_s
    end
  end
end

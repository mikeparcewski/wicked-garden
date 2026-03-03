; HTML query patterns for tree-sitter-html

; Element definitions (tags)
(element
  (start_tag
    (tag_name) @code_type.name)) @code_type.def

; Self-closing elements
(element
  (self_closing_tag
    (tag_name) @code_type.name)) @code_type.def

; Attribute definitions (id, class, name, etc.)
(attribute
  (attribute_name) @code_variable.name) @code_variable.def

; Script tags (for finding embedded JavaScript)
(script_element) @code_function.def

; Style tags
(style_element) @code_function.def

; Comments
(comment) @doc_section

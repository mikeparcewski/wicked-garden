; Svelte tree-sitter queries for extracting code symbols and relationships
; Svelte components contain script, markup, and style sections

; Script tags
(script_element
  (start_tag
    (tag_name) @_tag
    (#eq? @_tag "script"))) @code_module.def

; Style tags
(style_element
  (start_tag
    (tag_name) @_tag
    (#eq? @_tag "style"))) @code_type.def

; HTML elements
(element
  (start_tag
    (tag_name) @code_variable.name)) @code_variable.def

; Comments
(comment) @comment

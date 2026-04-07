; Vue tree-sitter queries for extracting code symbols and relationships
; Vue SFCs contain script, template, and style sections

; Script tags (setup or regular)
(script_element
  (start_tag
    (tag_name) @_tag
    (#eq? @_tag "script"))) @code_module.def

; Template tags
(template_element
  (start_tag
    (tag_name) @_tag
    (#eq? @_tag "template"))) @code_type.def

; Style tags
(style_element
  (start_tag
    (tag_name) @_tag
    (#eq? @_tag "style"))) @code_type.def

; Component name from script setup defineComponent
; (Most of the JS/TS parsing happens inside raw_text which we can't query)

; HTML elements in template
(element
  (start_tag
    (tag_name) @code_variable.name)) @code_variable.def

; Comments
(comment) @comment

; Properties tree-sitter queries for extracting code symbols and relationships
; Converted from properties-tags.scm

(property
  (key) @code_variable.name) @code_variable.def

(substitution
  (key) @call.property) @code_property.ref

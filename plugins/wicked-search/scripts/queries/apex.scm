; Apex tree-sitter queries for extracting code symbols and relationships
; Converted from apex-tags.scm

; Apex query (Salesforce)

; Top-level classes only
(parser_output
  (class_declaration
    name: (identifier) @code_class.name) @code_class.def)

; Methods (all functions in Apex are class methods)
(method_declaration
  name: (identifier) @code_function.name) @code_function.def

; Top-level interfaces only
(parser_output
  (interface_declaration
    name: (identifier) @code_interface.name) @code_interface.def)

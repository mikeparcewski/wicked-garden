; VHDL tree-sitter queries for extracting code symbols and relationships

; Entity declarations
(entity_declaration
  (identifier) @code_module.name) @code_module.def

; Architecture bodies
(architecture_body
  (identifier) @code_type.name) @code_type.def

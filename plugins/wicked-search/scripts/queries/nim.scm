; Nim tree-sitter queries for extracting code symbols and relationships

; Procedure definitions
(proc_declaration
  (identifier) @code_function.name) @code_function.def

; Type definitions
(type_declaration
  (type_symbol_declaration
    (identifier) @code_type.name)) @code_type.def

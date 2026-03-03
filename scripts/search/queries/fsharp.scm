; F# tree-sitter queries for extracting code symbols and relationships

; Function/value definitions with let
(function_or_value_defn
  (function_declaration_left
    (identifier) @code_function.name)) @code_function.def

; Record type definitions
(record_type_defn
  (type_name
    (identifier) @code_type.name)) @code_type.def

; Module definitions
(module_defn
  (identifier) @code_module.name) @code_module.def

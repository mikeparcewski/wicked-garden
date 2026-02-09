; Verilog tree-sitter queries for extracting code symbols and relationships

; Module declarations
(module_declaration
  (module_header
    (simple_identifier) @code_module.name)) @code_module.def

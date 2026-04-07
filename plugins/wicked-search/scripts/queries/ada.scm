; Ada tree-sitter queries for extracting code symbols and relationships

; Procedure definitions
(subprogram_body
  (procedure_specification
    (identifier) @code_function.name)) @code_function.def

; Function definitions
(subprogram_body
  (function_specification
    (identifier) @code_function.name)) @code_function.def

; Package bodies
(package_body
  (identifier) @code_module.name) @code_module.def

; Subprogram declarations (forward declarations)
(subprogram_declaration
  (procedure_specification
    (identifier) @code_function.name)) @code_function.def

(subprogram_declaration
  (function_specification
    (identifier) @code_function.name)) @code_function.def

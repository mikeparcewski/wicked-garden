; Erlang tree-sitter queries for extracting code symbols and relationships

; Module attribute
(module_attribute
  (atom) @code_module.name) @code_module.def

; Function declarations
(fun_decl
  (function_clause
    (atom) @code_function.name)) @code_function.def

; Type definitions
(type_alias
  (atom) @code_type.name) @code_type.def

; Record definitions
(record_decl
  (atom) @code_struct.name) @code_struct.def

; Macro definitions
(pp_define
  (macro_lhs
    (var) @code_variable.name)) @code_variable.def

; Comments
(comment) @comment

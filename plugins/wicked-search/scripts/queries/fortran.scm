; Fortran tree-sitter queries for extracting code symbols and relationships
; Converted from fortran-tags.scm

;; derived from: https://github.com/stadelmanma/tree-sitter-fortran
;; License: MIT

(module_statement
  (name) @code_class.name) @code_class.def

(function_statement
  name: (name) @code_function.name) @code_function.def

(subroutine_statement
  name: (name) @code_function.name) @code_function.def

(module_procedure_statement
  name: (name) @code_function.name) @code_function.def

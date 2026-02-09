; Powershell tree-sitter queries for extracting code symbols and relationships
; Converted from powershell-tags.scm

; PowerShell query patterns - simplified

; Function definitions
(function_statement
  (function_name) @code_function.name) @code_function.def

; Class definitions
(class_statement
  (simple_name) @code_class.name) @code_class.def

; Arduino tree-sitter queries for extracting code symbols and relationships
; Converted from arduino-tags.scm

(function_declarator
  declarator: (identifier) @code_function.name) @code_function.def

(call_expression
  function: (identifier) @call.function) @call.ref

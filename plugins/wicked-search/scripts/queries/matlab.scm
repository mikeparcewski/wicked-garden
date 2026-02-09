; Matlab tree-sitter queries for extracting code symbols and relationships
; Converted from matlab-tags.scm

; Top-level classes only
(source_file
  (class_definition
    name: (identifier) @code_class.name) @code_class.def)

(function_definition
  name: (identifier) @code_function.name) @code_function.def

(function_call
  name: (identifier) @call.function) @call.ref

(command (command_name) @call.function) @call.ref

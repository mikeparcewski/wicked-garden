; Lua tree-sitter queries for extracting code symbols and relationships
; Converted from lua-tags.scm

(function_declaration
  name: [
    (identifier) @code_function.name
    (dot_index_expression
      field: (identifier) @code_function.name)
  ]) @code_function.def

(function_declaration
  name: (method_index_expression
    method: (identifier) @code_function.name)) @code_function.def

(assignment_statement
  (variable_list .
    name: [
      (identifier) @code_function.name
      (dot_index_expression
        field: (identifier) @code_function.name)
    ])
  (expression_list .
    value: (function_definition))) @code_function.def

(table_constructor
  (field
    name: (identifier) @code_function.name
    value: (function_definition))) @code_function.def

(function_call
  name: [
    (identifier) @call.function
    (dot_index_expression
      field: (identifier) @call.function)
    (method_index_expression
      method: (identifier) @call.method)
  ]) @call.ref

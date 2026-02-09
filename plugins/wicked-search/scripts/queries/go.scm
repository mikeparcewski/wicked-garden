; Go tree-sitter queries for extracting code symbols and relationships

; Function declarations
(function_declaration
  name: (identifier) @code_function.name
  parameters: (parameter_list) @code_function.params
  result: (_)? @code_function.return_type
  body: (block) @code_function.body
) @code_function.def

; Method declarations
(method_declaration
  receiver: (parameter_list) @code_method.receiver
  name: (field_identifier) @code_method.name
  parameters: (parameter_list) @code_method.params
  result: (_)? @code_method.return_type
  body: (block) @code_method.body
) @code_method.def

; Type declarations (structs, interfaces)
(type_declaration
  (type_spec
    name: (type_identifier) @code_type.name
    type: (struct_type) @code_type.struct
  )
) @code_type.def

(type_declaration
  (type_spec
    name: (type_identifier) @code_type.name
    type: (interface_type) @code_type.interface
  )
) @code_interface.def

; Import declarations
(import_declaration) @import

; Package clause
(package_clause
  (package_identifier) @package.name
) @package

; Function calls - simple function calls
(call_expression
  function: (identifier) @call.function
  arguments: (argument_list) @call.args
) @call

; Method calls - selector expressions like obj.Method(), s.db.Query()
; Use (_) wildcard for operand to capture all patterns
(call_expression
  function: (selector_expression
    operand: (_) @call.object
    field: (field_identifier) @call.method
  )
) @call.method

; Variable declarations
(var_declaration
  (var_spec
    name: (identifier) @code_variable.name
  )
) @code_variable

; Comments
(comment) @comment

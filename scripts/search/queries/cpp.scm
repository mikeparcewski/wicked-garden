; C++ tree-sitter queries for extracting code symbols and relationships

; Class definitions
(class_specifier
  name: (type_identifier) @code_class.name
) @code_class.def

; Struct definitions
(struct_specifier
  name: (type_identifier) @code_struct.name
) @code_struct.def

; Top-level function definitions (with identifier)
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @code_function.name
  )
) @code_function.def

; Method definitions inside classes (with field_identifier)
(function_definition
  declarator: (function_declarator
    declarator: (field_identifier) @code_method.name
  )
) @code_method.def

; Enum definitions
(enum_specifier
  name: (type_identifier) @code_enum.name
) @code_enum.def

; Namespace definitions
(namespace_definition
  name: (namespace_identifier) @code_namespace.name
) @code_namespace.def

; Include directives
(preproc_include
  path: (_) @import.source
) @import

; Function calls - simple function calls
(call_expression
  function: (identifier) @call.function
) @call

; Method calls via field expression: obj.method()
(call_expression
  function: (field_expression
    argument: (_) @call.object
    field: (field_identifier) @call.method
  )
) @call.method

; Method calls via pointer: obj->method()
(call_expression
  function: (field_expression
    argument: (_) @call.object
    field: (field_identifier) @call.method
  )
) @call.method

; Comments
(comment) @comment

; Swift tree-sitter queries for extracting code symbols and relationships

; Class declarations
(class_declaration
  "class"
  name: (type_identifier) @code_class.name
  body: (class_body) @code_class.body
) @code_class.def

; Struct declarations
(class_declaration
  "struct"
  name: (type_identifier) @code_struct.name
  body: (class_body) @code_struct.body
) @code_struct.def

; Protocol declarations (interfaces)
(protocol_declaration
  name: (type_identifier) @code_interface.name
  body: (protocol_body) @code_interface.body
) @code_interface.def

; Enum declarations
(class_declaration
  "enum"
  name: (type_identifier) @code_enum.name
  body: (class_body) @code_enum.body
) @code_enum.def

; Function declarations
(function_declaration
  name: (simple_identifier) @code_function.name
  (parameter)* @code_function.params
  body: (function_body)? @code_function.body
) @code_function.def

; Method declarations inside class body
(class_body
  (function_declaration
    name: (simple_identifier) @code_function.name
    (parameter)* @code_function.params
    body: (function_body)? @code_function.body
  ) @code_function.def
)

; Init declarations (constructors)
(init_declaration
  (parameter)* @code_function.params
  body: (function_body)? @code_function.body
) @code_function.def

; Property declarations
(property_declaration
  (pattern
    (simple_identifier) @code_variable.name
  )
) @code_variable.def

; Call expressions
(call_expression
  (simple_identifier) @call.function
  (call_suffix)? @call.args
) @call

; Method calls
(call_expression
  (navigation_expression
    (navigation_suffix
      (simple_identifier) @call.method
    )
  )
  (call_suffix)? @call.args
) @call.method

; Import declarations
(import_declaration
  (identifier) @import.module
) @import

; Comments
(comment) @comment
(multiline_comment) @comment

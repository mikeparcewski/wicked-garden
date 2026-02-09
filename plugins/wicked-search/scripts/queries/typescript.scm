; TypeScript tree-sitter queries for extracting code symbols and relationships

; Function declarations
(function_declaration
  name: (identifier) @code_function.name
  parameters: (formal_parameters) @code_function.params
  return_type: (type_annotation)? @code_function.return_type
  body: (statement_block) @code_function.body
) @code_function.def

; Arrow functions
(arrow_function
  parameters: (_) @code_function.params
  return_type: (type_annotation)? @code_function.return_type
  body: (_) @code_function.body
) @code_function.arrow

; Method definitions
(method_definition
  name: (property_identifier) @code_method.name
  parameters: (formal_parameters) @code_method.params
  return_type: (type_annotation)? @code_method.return_type
  body: (statement_block) @code_method.body
) @code_method.def

; Class declarations
(class_declaration
  name: (type_identifier) @code_class.name
  body: (class_body) @code_class.body
) @code_class.def

; Interface declarations
(interface_declaration
  name: (type_identifier) @code_interface.name
  body: (interface_body) @code_interface.body
) @code_interface.def

; Type alias declarations
(type_alias_declaration
  name: (type_identifier) @code_type.name
  value: (_) @code_type.value
) @code_type.def

; Import statements
(import_statement
  source: (string) @import.source
) @import

; Export statements
(export_statement) @export

; Function calls
(call_expression
  function: (identifier) @call.function
  arguments: (arguments) @call.args
) @call

; Member expressions (method calls) - any member expression call
; Use (_) wildcard for object to capture all patterns like this.db.query(), get().method()
(call_expression
  function: (member_expression
    object: (_) @call.object
    property: (property_identifier) @call.method
  )
) @call.method

; Variable declarations
(variable_declarator
  name: (identifier) @code_variable.name
  type: (type_annotation)? @code_variable.type
  value: (_)? @code_variable.value
) @code_variable

; Comments
(comment) @comment

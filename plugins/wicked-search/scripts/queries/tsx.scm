; TSX tree-sitter queries for extracting code symbols and relationships
; TSX is TypeScript with JSX support

; Function declarations
(function_declaration
  name: (identifier) @code_function.name) @code_function.def

; Arrow functions assigned to variables
(lexical_declaration
  (variable_declarator
    name: (identifier) @code_function.name
    value: (arrow_function))) @code_function.def

; Class declarations
(class_declaration
  name: (type_identifier) @code_class.name) @code_class.def

; Interface declarations
(interface_declaration
  name: (type_identifier) @code_interface.name) @code_interface.def

; Type alias declarations
(type_alias_declaration
  name: (type_identifier) @code_type.name) @code_type.def

; Enum declarations
(enum_declaration
  name: (identifier) @code_enum.name) @code_enum.def

; Method definitions in classes
(method_definition
  name: (property_identifier) @code_method.name) @code_method.def

; Variable declarations
(lexical_declaration
  (variable_declarator
    name: (identifier) @code_variable.name)) @code_variable.def

; Import statements
(import_statement) @import

; Export statements
(export_statement) @export

; Function calls - simple function calls
(call_expression
  function: (identifier) @call.function
  arguments: (arguments) @call.args
) @call

; Method calls - any member expression call
; Use (_) wildcard for object to capture all patterns
(call_expression
  function: (member_expression
    object: (_) @call.object
    property: (property_identifier) @call.method
  )
) @call.method

; Comments
(comment) @comment

; JavaScript tree-sitter queries for extracting code symbols and relationships

; Function declarations
(function_declaration
  name: (identifier) @code_function.name
  parameters: (formal_parameters) @code_function.params
  body: (statement_block) @code_function.body
) @code_function.def

; Arrow functions assigned to variables
(variable_declarator
  name: (identifier) @code_function.name
  value: (arrow_function
    parameters: (_) @code_function.params
    body: (_) @code_function.body
  )
) @code_function.def

; ES6 Class declarations
(class_declaration
  name: (identifier) @code_class.name
  body: (class_body) @code_class.body
) @code_class.def

; Class expressions
(variable_declarator
  name: (identifier) @code_class.name
  value: (class
    body: (class_body) @code_class.body
  )
) @code_class.def

; Method definitions (inside classes)
(method_definition
  name: (property_identifier) @code_method.name
  parameters: (formal_parameters) @code_method.params
  body: (statement_block) @code_method.body
) @code_method.def

; Constructor
(method_definition
  name: (property_identifier) @code_method.name
  (#eq? @code_method.name "constructor")
  parameters: (formal_parameters) @code_method.params
  body: (statement_block) @code_method.body
) @code_method.def

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

; Method calls - any member expression call like obj.method(), this.db.query(), get().method()
; Use (_) wildcard for object to capture all patterns
(call_expression
  function: (member_expression
    object: (_) @call.object
    property: (property_identifier) @call.method
  )
) @call.method

; Variable declarations
(variable_declarator
  name: (identifier) @code_variable.name
  value: (_)? @code_variable.value
) @code_variable

; Comments
(comment) @comment

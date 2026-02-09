; PHP tree-sitter queries for extracting code symbols and relationships

; Class declarations
(class_declaration
  name: (name) @code_class.name
  body: (declaration_list) @code_class.body
) @code_class.def

; Interface declarations
(interface_declaration
  name: (name) @code_interface.name
  body: (declaration_list) @code_interface.body
) @code_interface.def

; Trait declarations
(trait_declaration
  name: (name) @code_interface.name
  body: (declaration_list) @code_interface.body
) @code_interface.def

; Method declarations
(method_declaration
  name: (name) @code_method.name
  parameters: (formal_parameters) @code_method.params
  body: (compound_statement)? @code_method.body
) @code_method.def

; Function definitions
(function_definition
  name: (name) @code_function.name
  parameters: (formal_parameters) @code_function.params
  body: (compound_statement) @code_function.body
) @code_function.def

; Property declarations
(property_declaration
  (property_element
    (variable_name (name) @code_variable.name)
  )
) @code_variable.def

; Namespace declarations
(namespace_definition
  name: (namespace_name) @code_namespace.name
  body: (compound_statement)? @code_namespace.body
) @code_namespace.def

; Use declarations (namespace imports)
(namespace_use_declaration
  (namespace_use_clause
    (qualified_name) @import.module
  )
) @import

; Require/include statements
(include_expression
  (string) @import.source
) @import

(include_once_expression
  (string) @import.source
) @import

(require_expression
  (string) @import.source
) @import

(require_once_expression
  (string) @import.source
) @import

; Function calls
(function_call_expression
  function: (name) @call.function
  arguments: (arguments) @call.args
) @call

(function_call_expression
  function: (qualified_name
    (name) @call.function
  )
  arguments: (arguments) @call.args
) @call

; Method calls
(member_call_expression
  name: (name) @call.method
  arguments: (arguments) @call.args
) @call.method

; Static method calls
(scoped_call_expression
  name: (name) @call.method
  arguments: (arguments) @call.args
) @call.method

; Object creation
(object_creation_expression
  (name) @call.constructor
  arguments: (arguments)? @call.args
) @call

; Comments
(comment) @comment

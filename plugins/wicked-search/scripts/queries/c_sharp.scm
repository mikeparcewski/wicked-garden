; C# tree-sitter queries for extracting code symbols and relationships

; Class declarations
(class_declaration
  name: (identifier) @code_class.name
  body: (declaration_list) @code_class.body
) @code_class.def

; Interface declarations
(interface_declaration
  name: (identifier) @code_interface.name
  body: (declaration_list) @code_interface.body
) @code_interface.def

; Struct declarations
(struct_declaration
  name: (identifier) @code_struct.name
  body: (declaration_list) @code_struct.body
) @code_struct.def

; Method declarations
(method_declaration
  name: (identifier) @code_method.name
  parameters: (parameter_list) @code_method.params
  body: (block)? @code_method.body
) @code_method.def

; Constructor declarations
(constructor_declaration
  name: (identifier) @code_method.name
  parameters: (parameter_list) @code_method.params
  body: (block) @code_method.body
) @code_method.def

; Property declarations
(property_declaration
  name: (identifier) @code_variable.name
) @code_variable.def

; Namespace declarations
(namespace_declaration
  name: (_) @code_namespace.name
  body: (declaration_list) @code_namespace.body
) @code_namespace.def

; Enum declarations
(enum_declaration
  name: (identifier) @code_enum.name
  body: (enum_member_declaration_list) @code_enum.body
) @code_enum.def

; Using directives (imports)
(using_directive
  (qualified_name) @import.module
) @import

(using_directive
  (identifier) @import.module
) @import

; Method invocations - capture expression for chained calls
; Handles obj.Method(), this.Method(), GetObj().Method(), etc.
(invocation_expression
  function: (member_access_expression
    expression: (_) @call.object
    name: (identifier) @call.method
  )
  arguments: (argument_list) @call.args
) @call.method

; Simple function calls
(invocation_expression
  function: (identifier) @call.function
  arguments: (argument_list) @call.args
) @call

; Comments
(comment) @comment

; C tree-sitter queries for extracting code symbols and relationships

; Struct definitions
(struct_specifier
  name: (type_identifier) @code_struct.name
  body: (field_declaration_list) @code_struct.body
) @code_struct.def

; Union definitions
(union_specifier
  name: (type_identifier) @code_struct.name
  body: (field_declaration_list) @union.body
) @code_struct.def

; Function definitions
(function_definition
  declarator: (function_declarator
    declarator: (identifier) @code_function.name
    parameters: (parameter_list) @code_function.params
  )
  body: (compound_statement) @code_function.body
) @code_function.def

; Function declarations (prototypes)
(declaration
  declarator: (function_declarator
    declarator: (identifier) @code_function.name
    parameters: (parameter_list) @code_function.params
  )
) @code_function.decl

; Enum definitions
(enum_specifier
  name: (type_identifier) @code_enum.name
  body: (enumerator_list) @code_enum.body
) @code_enum.def

; Type definitions
(type_definition
  declarator: (type_identifier) @code_type.name
) @code_type.def

; Include directives
(preproc_include
  path: (_) @import.source
) @import

; Function calls
(call_expression
  function: (identifier) @call.function
  arguments: (argument_list) @call.args
) @call

; Comments
(comment) @comment

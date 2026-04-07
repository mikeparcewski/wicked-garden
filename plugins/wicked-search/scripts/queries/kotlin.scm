; Kotlin tree-sitter queries for extracting code symbols and relationships

; Class declarations
(class_declaration
  (type_identifier) @code_class.name
  (class_body)? @code_class.body
) @code_class.def

; Data class declarations
(class_declaration
  (modifiers (class_modifier) @_mod)
  (type_identifier) @code_class.name
  (class_body)? @code_class.body
  (#eq? @_mod "data")
) @code_class.def

; Object declarations (singletons)
(object_declaration
  (type_identifier) @code_class.name
  (class_body)? @code_class.body
) @code_class.def

; Interface declarations
(class_declaration
  (modifiers (class_modifier) @_mod)
  (type_identifier) @code_interface.name
  (#eq? @_mod "interface")
) @code_interface.def

; Function declarations
(function_declaration
  (simple_identifier) @code_function.name
  (function_value_parameters) @code_function.params
  (function_body)? @code_function.body
) @code_function.def

; Property declarations
(property_declaration
  (variable_declaration
    (simple_identifier) @code_variable.name
  )
) @code_variable.def

; Call expressions
(call_expression
  (simple_identifier) @call.function
  (call_suffix
    (value_arguments) @call.args
  )?
) @call

; Navigation call expressions (method calls)
(call_expression
  (navigation_expression
    (navigation_suffix
      (simple_identifier) @call.method
    )
  )
  (call_suffix
    (value_arguments) @call.args
  )?
) @call.method

; Import declarations
(import_header
  (identifier) @import.module
) @import

; Comments
(multiline_comment) @comment
(line_comment) @comment

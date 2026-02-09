; Scala tree-sitter queries for extracting code symbols and relationships

; Object definitions (singletons)
(object_definition
  name: (identifier) @code_class.name
) @code_class.def

; Class definitions
(class_definition
  name: (identifier) @code_class.name
) @code_class.def

; Trait definitions (interfaces)
(trait_definition
  name: (identifier) @code_interface.name
) @code_interface.def

; Function definitions
(function_definition
  name: (identifier) @code_function.name
) @code_function.def

; Value definitions
(val_definition
  pattern: (identifier) @code_variable.name
) @code_variable.def

; Package declarations
(package_clause
  name: (_) @code_module.name
) @code_module.def

; Import declarations (just capture the whole import)
(import_declaration) @import

; Call expressions
(call_expression
  function: (identifier) @call.function
) @call

; Comments
(comment) @comment

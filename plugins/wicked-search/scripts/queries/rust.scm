; Rust tree-sitter queries for extracting code symbols and relationships

; Function definitions
(function_item
  name: (identifier) @code_function.name
  parameters: (parameters) @code_function.params
  return_type: (type_identifier)? @code_function.return_type
  body: (block) @code_function.body
) @code_function.def

; Struct definitions
(struct_item
  name: (type_identifier) @code_struct.name
  body: (_)? @code_struct.body
) @code_struct.def

; Enum definitions
(enum_item
  name: (type_identifier) @code_enum.name
  body: (enum_variant_list) @code_enum.body
) @code_enum.def

; Trait definitions
(trait_item
  name: (type_identifier) @code_interface.name
  body: (declaration_list) @code_interface.body
) @code_interface.def

; Implementation blocks
(impl_item
  type: (type_identifier) @impl.type
  body: (declaration_list
    (function_item
      name: (identifier) @code_method.name
      parameters: (parameters) @code_method.params
      return_type: (type_identifier)? @code_method.return_type
      body: (block) @code_method.body
    ) @code_method.def
  )
) @code_type.def

; Use declarations (imports)
(use_declaration) @import

; Module declarations
(mod_item
  name: (identifier) @code_module.name
) @code_module

; Function calls - simple function calls
(call_expression
  function: (identifier) @call.function
  arguments: (arguments) @call.args
) @call

; Method calls - field expressions like obj.method(), self.method()
; Use (_) wildcard for value to capture all patterns
(call_expression
  function: (field_expression
    value: (_) @call.object
    field: (field_identifier) @call.method
  )
) @call.method

; Macro invocations
(macro_invocation
  macro: (identifier) @code_macro.name
) @code_macro

; Comments
(line_comment) @comment
(block_comment) @comment

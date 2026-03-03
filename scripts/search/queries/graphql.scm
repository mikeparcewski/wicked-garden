; GraphQL tree-sitter queries for extracting code symbols and relationships

; Object type definitions (Query, Mutation, User, etc.)
(object_type_definition
  (name) @code_type.name) @code_type.def

; Interface type definitions
(interface_type_definition
  (name) @code_interface.name) @code_interface.def

; Enum type definitions
(enum_type_definition
  (name) @code_enum.name) @code_enum.def

; Input object type definitions
(input_object_type_definition
  (name) @code_type.name) @code_type.def

; Scalar type definitions
(scalar_type_definition
  (name) @code_type.name) @code_type.def

; Union type definitions
(union_type_definition
  (name) @code_type.name) @code_type.def

; Directive definitions
(directive_definition
  (name) @code_function.name) @code_function.def

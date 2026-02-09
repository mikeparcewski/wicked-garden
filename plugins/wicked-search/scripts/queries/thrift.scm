; Thrift tree-sitter queries for extracting code symbols and relationships

; Struct definitions
(struct_definition
  (identifier) @code_struct.name) @code_struct.def

; Enum definitions
(enum_definition
  (identifier) @code_enum.name) @code_enum.def

; Service definitions
(service_definition
  (identifier) @code_interface.name) @code_interface.def

; Exception definitions
(exception_definition
  (identifier) @code_class.name) @code_class.def

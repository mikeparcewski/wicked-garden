; Protocol Buffers tree-sitter queries for extracting code symbols and relationships

; Package declaration
(package
  (full_ident) @code_module.name) @code_module.def

; Message definitions
(message
  (message_name
    (identifier) @code_class.name)) @code_class.def

; Enum definitions
(enum
  (enum_name
    (identifier) @code_enum.name)) @code_enum.def

; Service definitions
(service
  (service_name
    (identifier) @code_interface.name)) @code_interface.def

; RPC method definitions
(rpc
  (rpc_name
    (identifier) @code_function.name)) @code_function.def

; Field definitions
(field
  (identifier) @code_variable.name) @code_variable.def

; Oneof definitions
(oneof
  (identifier) @code_variable.name) @code_variable.def

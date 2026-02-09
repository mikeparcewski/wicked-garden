; Solidity tree-sitter queries for extracting code symbols and relationships
; Converted from solidity-tags.scm

;; Method and Function declarations
(contract_declaration (_
    (function_definition
        name: (identifier) @code_function.name) @code_function.def))

(source_file
    (function_definition
        name: (identifier) @code_function.name) @code_function.def)

;; Contract, struct, enum and interface declarations
(contract_declaration
  name: (identifier) @code_class.name) @code_class.def

(interface_declaration
  name: (identifier) @code_interface.name) @code_interface.def

(library_declaration
  name: (identifier) @code_class.name) @code_interface.def

(struct_declaration name: (identifier) @code_class.name) @code_class.def
(enum_declaration name: (identifier) @code_class.name) @code_class.def
(event_definition name: (identifier) @code_class.name) @code_class.def

;; Function calls
(call_expression (expression (identifier)) @call.function ) @call.ref

(call_expression
    (expression (member_expression
        property: (_) @call.method ))) @call.ref

;; Log emit
(emit_statement name: (_) @code_class.ref) @code_class.ref


;; Inheritance

(inheritance_specifier
    ancestor: (user_defined_type (_) @code_class.ref . )) @code_class.ref


;; Imports ( note that unknown is not standardised )
(import_directive
  import_name: (_) @code_module.ref ) @unknown.ref

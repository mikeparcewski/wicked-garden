; Gleam tree-sitter queries for extracting code symbols and relationships
; Converted from gleam-tags.scm

; Modules
(module) @code_module.ref @code_module.ref
(import alias: (identifier) @code_module.ref) @code_module.ref
(remote_type_identifier
  module: (identifier) @code_module.ref) @code_module.ref
((field_access
  record: (identifier) @code_module.ref)
 (#is-not? local)) @code_module.ref

; Functions
(function
  name: (identifier) @code_function.name) @code_function.def
(external_function
  name: (identifier) @code_function.name) @code_function.def
(unqualified_import (identifier) @call.function) @code_function.ref
((function_call
   function: (identifier) @call.function) @code_function.ref
 (#is-not? local))
((field_access
  record: (identifier) @_ignore
  field: (label) @call.function)
 (#is-not? local)) @code_function.ref
((binary_expression
   operator: "|>"
   right: (identifier) @call.function)
 (#is-not? local)) @code_function.ref

; Types
(type_definition
  (type_name
    name: (type_identifier) @code_type.name)) @code_type.def
(type_definition
  (data_constructors
    (data_constructor
      name: (constructor_name) @code_function.name))) @code_function.def
(external_type
  (type_name
    name: (type_identifier) @code_type.name)) @code_type.def

(type_identifier) @call.type @code_type.ref
(constructor_name) @call.constructor @code_function.ref

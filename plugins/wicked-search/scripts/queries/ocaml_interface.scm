; Ocaml_Interface tree-sitter queries for extracting code symbols and relationships
; Converted from ocaml_interface-tags.scm

; Modules
;--------

(
  (comment)? @doc .
  (module_definition
    (module_binding (module_name) @name) @code_module.def
  )
  (#strip! @doc "^\\(\\*+\\s*|\\s*\\*+\\)$")
)

(module_path (module_name) @name) @code_module.ref
(extended_module_path (module_name) @name) @code_module.ref

(
  (comment)? @doc .
  (module_type_definition (module_type_name) @name) @code_interface.def
  (#strip! @doc "^\\(\\*+\\s*|\\s*\\*+\\)$")
)

(module_type_path (module_type_name) @name) @implementation.ref


; Classes
;--------

(
  (comment)? @doc .
  [
    (class_definition
      (class_binding (class_name) @name) @code_class.def
    )
    (class_type_definition
      (class_type_binding (class_type_name) @name) @code_class.def
    )
  ]
  (#strip! @doc "^\\(\\*+\\s*|\\s*\\*+\\)$")
)

[
  (class_path (class_name) @name)
  (class_type_path (class_type_name) @name)
] @code_class.ref

(
  (comment)? @doc .
  (method_definition (method_name) @name) @code_method.def
  (#strip! @doc "^\\(\\*+\\s*|\\s*\\*+\\)$")
)

(method_invocation (method_name) @name) @call.ref


; Types
;------

(
  (comment)? @doc .
  (type_definition
    (type_binding
      name: [
        (type_constructor) @name
        (type_constructor_path (type_constructor) @name)
      ]
    ) @code_type.def
  )
  (#strip! @doc "^\\(\\*+\\s*|\\s*\\*+\\)$")
)

(type_constructor_path (type_constructor) @name) @code_type.ref

[
  (constructor_declaration (constructor_name) @name)
  (tag_specification (tag) @name)
] @code_variable.def

[
  (constructor_path (constructor_name) @name)
  (tag) @name
] @enum_variant.ref

(field_declaration (field_name) @name) @code_variable.def

(field_path (field_name) @name) @code_property.ref

(
  (comment)? @doc .
  (external (value_name) @name) @code_function.def
  (#strip! @doc "^\\(\\*+\\s*|\\s*\\*+\\)$")
)

(
  (comment)? @doc .
  (value_specification
    (value_name) @code_function.name
  ) @code_function.def
  (#strip! @doc "^\\(\\*+\\s*|\\s*\\*+\\)$")
)

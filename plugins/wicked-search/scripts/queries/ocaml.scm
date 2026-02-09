; Ocaml tree-sitter queries for extracting code symbols and relationships
; Converted from ocaml-tags.scm

; Modules
;--------

(
  (comment)? @doc .
  (module_definition (module_binding (module_name) @code_module.name) @code_module.def)
  (#strip! @doc "^\\(\\*\\*?\\s*|\\s\\*\\)$")
)

(module_path (module_name) @code_module.ref) @code_module.ref

; Module types
;--------------

(
  (comment)? @doc .
  (module_type_definition (module_type_name) @code_interface.name) @code_interface.def
  (#strip! @doc "^\\(\\*\\*?\\s*|\\s\\*\\)$")
)

(module_type_path (module_type_name) @call.implementation) @implementation.ref

; Functions
;----------

(
  (comment)? @doc .
  (value_definition
    [
      (let_binding
        pattern: (value_name) @code_function.name
        (parameter))
      (let_binding
        pattern: (value_name) @code_function.name
        body: [(fun_expression) (function_expression)])
    ] @code_function.def
  )
  (#strip! @doc "^\\(\\*\\*?\\s*|\\s\\*\\)$")
)

(
  (comment)? @doc .
  (external (value_name) @code_function.name) @code_function.def
  (#strip! @doc "^\\(\\*\\*?\\s*|\\s\\*\\)$")
)

(application_expression
  function: (value_path (value_name) @call.function)) @call.ref

(infix_expression
  left: (value_path (value_name) @call.function)
  operator: (concat_operator) @call.ref
  (#eq? @call.ref "@@"))

(infix_expression
  operator: (rel_operator) @call.ref
  right: (value_path (value_name) @call.function)
  (#eq? @call.ref "|>"))

; Operator
;---------

(
  (comment)? @doc .
  (value_definition
    (let_binding
      pattern: (parenthesized_operator (_) @code_function.name)) @code_function.def)
  (#strip! @doc "^\\(\\*\\*?\\s*|\\s\\*\\)$")
)

[
  (prefix_operator)
  (sign_operator)
  (pow_operator)
  (mult_operator)
  (add_operator)
  (concat_operator)
  (rel_operator)
  (and_operator)
  (or_operator)
  (assign_operator)
  (hash_operator)
  (indexing_operator)
  (let_operator)
  (let_and_operator)
  (match_operator)
] @call.function @call.ref

; Classes
;--------

(
  (comment)? @doc .
  [
    (class_definition (class_binding (class_name) @code_class.name) @code_class.def)
    (class_type_definition (class_type_binding (class_type_name) @code_class.name) @code_class.def)
  ]
  (#strip! @doc "^\\(\\*\\*?\\s*|\\s\\*\\)$")
)

[
  (class_path (class_name) @code_class.ref)
  (class_type_path (class_type_name) @code_class.ref)
] @code_class.ref

; Methods
;--------

(
  (comment)? @doc .
  (method_definition (method_name) @code_method.name) @code_method.def
  (#strip! @doc "^\\(\\*\\*?\\s*|\\s\\*\\)$")
)

(method_invocation (method_name) @call.function) @call.ref

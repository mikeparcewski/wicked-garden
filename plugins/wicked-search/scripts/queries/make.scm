; Makefile tree-sitter queries for extracting code symbols and relationships

; Rules (targets)
(rule
  (targets
    (word) @code_function.name)) @code_function.def

; Variable assignments
(variable_assignment
  (word) @code_variable.name) @code_variable.def

; Define directives (multi-line variables)
(define_directive
  (word) @code_variable.name) @code_variable.def

; Comments
(comment) @comment

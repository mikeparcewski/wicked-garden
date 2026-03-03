; Udev tree-sitter queries for extracting code symbols and relationships
; Converted from udev-tags.scm

(assignment
  key: "LABEL"
  (value
    (content) @code_variable.name)) @code_variable.def

(assignment
  key: "GOTO"
  (value
    (content) @call.label)) @label.ref

(assignment
  key: "ENV"
  (env_var) @code_variable.name) @code_variable.def

(match
  key: "ENV"
  (env_var) @call.variable) @code_variable.ref

(var_sub
  (env_var) @call.variable) @code_variable.ref

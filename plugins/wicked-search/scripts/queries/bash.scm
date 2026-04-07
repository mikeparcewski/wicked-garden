; Bash/Shell script query patterns

; Function definitions
(function_definition
  name: (word) @code_function.name) @code_function.def

; Variable assignments
(variable_assignment
  name: (variable_name) @code_variable.name) @code_variable.def

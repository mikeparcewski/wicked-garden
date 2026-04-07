; Fish shell tree-sitter queries for extracting code symbols and relationships

; Function definitions
(function_definition
  (word) @code_function.name) @code_function.def

; Variable assignments (set command)
(command
  name: (word) @_cmd
  argument: (word) @code_variable.name
  (#eq? @_cmd "set")) @code_variable.def

; Comments
(comment) @comment

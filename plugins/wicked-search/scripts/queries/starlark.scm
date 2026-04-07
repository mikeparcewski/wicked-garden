; Starlark (Bazel BUILD files) tree-sitter queries for extracting code symbols and relationships

; Function definitions
(function_definition
  name: (identifier) @code_function.name) @code_function.def

; Variable assignments
(assignment
  left: (identifier) @code_variable.name) @code_variable.def

; Load statements (imports)
(expression_statement
  (call
    function: (identifier) @_func
    (#eq? @_func "load"))) @import

; Rule invocations (targets)
(expression_statement
  (call
    function: (identifier) @code_function.name
    arguments: (argument_list
      (keyword_argument
        name: (identifier) @_name
        value: (string) @code_variable.name
        (#eq? @_name "name"))))) @code_variable.def

; Comments
(comment) @comment

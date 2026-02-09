; Nix tree-sitter queries for extracting code symbols and relationships

; Bindings (variable/function definitions)
(binding
  (attrpath
    (identifier) @code_variable.name)) @code_variable.def

; Let bindings
(let_expression
  (binding_set
    (binding
      (attrpath
        (identifier) @code_variable.name)))) @code_variable.def

; Function parameters in lambdas
(formals
  (formal
    (identifier) @code_variable.name)) @code_variable.def

; Comments
(comment) @comment

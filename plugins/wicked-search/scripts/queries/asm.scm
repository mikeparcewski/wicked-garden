; Assembly tree-sitter queries for extracting code symbols and relationships

; Labels (function/routine entry points)
(label
  (ident) @code_function.name) @code_function.def

; Global directives
(meta
  (meta_ident) @_directive
  (ident) @code_variable.name
  (#match? @_directive "^\\.global$")) @code_variable.def

; External references
(meta
  (meta_ident) @_directive
  (ident) @code_variable.name
  (#match? @_directive "^\\.extern$")) @code_variable.def

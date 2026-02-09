; Racket tree-sitter queries for extracting code symbols and relationships
; Converted from racket-tags.scm

(list
  .
  (symbol) @_define.ref
  (#match? @_define.ref "^(define|define/contract)$")
  .
  (list
    .
    (symbol) @code_function.name) @code_function.def)

(list
  .
  (symbol) @call.function)

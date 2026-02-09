; Clojure tree-sitter queries for extracting code symbols and relationships

; Function definitions (defn, defn-, def)
; Match: (defn name [...] body) or (def name value)
(list_lit
  (sym_lit (sym_name) @_deftype)
  (sym_lit (sym_name) @code_function.name)
  (#match? @_deftype "^def")
) @code_function.def

; Comments
(comment) @comment

; XML query patterns for tree-sitter-xml

; Element definitions with start tag
(element
  (STag
    (Name) @code_type.name)) @code_type.def

; Self-closing elements (empty elements)
(element
  (EmptyElemTag
    (Name) @code_type.name)) @code_type.def

; Attribute definitions
(Attribute
  (Name) @code_variable.name) @code_variable.def

; XML declaration/prolog
(prolog) @code_variable.def

; Comments
(Comment) @doc_section

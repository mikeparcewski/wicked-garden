; SPARQL tree-sitter queries for extracting code symbols and relationships

; Prefix declarations
(prefix_declaration
  (namespace) @code_namespace.name
) @code_namespace.def

; Variables
(var) @code_variable.def

; Select queries
(select_query) @code_function.def

; IRI references
(iri_reference) @symbol.ref

; Comments
(comment) @comment

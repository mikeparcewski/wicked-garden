; Julia tree-sitter queries for extracting code symbols and relationships
; Converted from julia-tags.scm

;; Minimal Julia query - only confirmed valid node types

(struct_definition) @code_struct.def

(function_definition) @code_function.def

; Import statements
(import_statement) @import

; Using statements
(using_statement) @import

; Haskell tree-sitter queries for extracting code symbols and relationships
; Converted from haskell-tags.scm

; Haskell query patterns - simplified

; Import statements
(import) @import

; All signatures
(signature) @code_function.def

; All function bindings
(function) @code_function.def

; All bind statements
(bind) @code_function.def

; Elisp tree-sitter queries for extracting code symbols and relationships
; Converted from elisp-tags.scm

;; defun/defsubst
(function_definition name: (symbol) @code_function.name) @code_function.def

;; Treat macros as function definitions for the sake of TAGS.
(macro_definition name: (symbol) @code_function.name) @code_function.def

;; Match function calls
(list (symbol) @call.function) @code_function.ref

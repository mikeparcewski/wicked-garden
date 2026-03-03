; Zig tree-sitter queries for extracting code symbols and relationships
; Converted from zig-tags.scm

; Zig query patterns - simplified

; Function declarations
(FnProto) @code_function.def

; Variable declarations
(VarDecl) @code_variable.def

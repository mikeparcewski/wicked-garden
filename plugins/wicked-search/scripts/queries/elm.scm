; Elm tree-sitter queries for extracting code symbols and relationships

; Function/value declarations
(value_declaration
  (function_declaration_left
    (lower_case_identifier) @code_function.name)
) @code_function.def

; Type annotations (function signatures)
(type_annotation
  (lower_case_identifier) @code_function.name
) @code_function.def

; Type declarations
(type_declaration
  (upper_case_identifier) @code_type.name
) @code_type.def

; Type alias declarations
(type_alias_declaration
  (upper_case_identifier) @code_type.name
) @code_type.def

; Module declarations
(module_declaration
  (upper_case_qid) @code_module.name
) @code_module.def

; Import statements
(import_clause) @import

; Comments
(line_comment) @comment
(block_comment) @comment

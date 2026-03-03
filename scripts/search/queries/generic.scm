; Generic query patterns that work across many languages
; Used as fallback when language-specific queries aren't available

; Common function-like patterns
(
  (identifier) @code_function.name
  ([(parameter_list) (formal_parameters) (parameters) (argument_list)] @code_function.params)?
  ([block statement_block] @code_function.body)?
) @code_function.generic

; Common class-like patterns
(
  [(class interface struct)] @code_struct.type
  (identifier) @code_struct.name
  ([block body class_body] @code_struct.body)?
) @code_struct

; Common variable/field patterns
(
  [(const let var val)] @code_variable.keyword
  (identifier) @code_variable.name
  (_)? @code_variable.value
) @code_variable

; Import/include patterns
(
  [(import include require use from)] @import.keyword
  (_) @import.path
) @import.statement

; String literals (potential docstrings)
(string) @string
(string_literal) @string
(interpreted_string_literal) @string

; Comments
(comment) @comment
(line_comment) @comment.line
(block_comment) @comment.block

; Identifiers (catch-all)
(identifier) @identifier
(type_identifier) @code_type.identifier
(field_identifier) @code_property.identifier
(property_identifier) @code_property.identifier

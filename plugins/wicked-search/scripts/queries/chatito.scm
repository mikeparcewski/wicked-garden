; Chatito tree-sitter queries for extracting code symbols and relationships
; Chatito is a domain-specific language for NLU training data

; Intent definitions - treat as functions
(intent_def
  (intent) @code_function.name
) @code_function.def

; Slot definitions - treat as variables
(slot_def
  (slot) @code_variable.name
) @code_variable.def

; Alias definitions - treat as variables
(alias_def
  (alias) @code_variable.name
) @code_variable.def

; Slot references - treat as calls
(slot_ref
  (slot) @call.function
) @call

; Alias references - treat as calls
(alias_ref
  (alias) @call.function
) @call

; Rego (Open Policy Agent) tree-sitter queries for extracting code symbols and relationships

; Rule definitions
(rule
  (rule_head
    (var) @code_function.name)) @code_function.def

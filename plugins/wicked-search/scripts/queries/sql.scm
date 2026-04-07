; SQL query patterns for tree-sitter-sql

; CREATE TABLE statements
(create_table
  (object_reference
    (identifier) @code_type.name)) @code_type.def

; CREATE VIEW statements
(create_view
  (object_reference
    (identifier) @code_type.name)) @code_type.def

; CREATE INDEX statements
(create_index
  (object_reference
    (identifier) @code_variable.name)) @code_variable.def

; Common Table Expressions (CTEs)
(cte
  (identifier) @code_variable.name) @code_variable.def

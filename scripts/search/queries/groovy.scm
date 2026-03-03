; Groovy tree-sitter queries for extracting code symbols and relationships
; Converted from groovy-tags.scm

; Groovy query - grammar uses generic nodes (command/unit/identifier)
; Pattern: command > unit > identifier[keyword] + block

; Classes: command containing "class" identifier followed by block
(command
  (unit (identifier) @_class_keyword)
  (block
    (unit (identifier) @code_class.name))
  (#eq? @_class_keyword "class")
) @code_class.def

; Functions: command containing "def" identifier followed by block
(command
  (unit (identifier) @_def_keyword)
  (block)
  (#eq? @_def_keyword "def")
) @code_function.def

; Imports: command containing "import" identifier
(command
  (unit (identifier) @_import_keyword)
  (#eq? @_import_keyword "import")
) @import

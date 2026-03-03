; Objective-C tree-sitter queries for extracting code symbols and relationships

; Class interfaces
(class_interface
  (identifier) @code_class.name) @code_class.def

; Class implementations
(class_implementation
  (identifier) @code_class.name) @code_class.def

; Protocol declarations
(protocol_declaration
  (identifier) @code_interface.name) @code_interface.def

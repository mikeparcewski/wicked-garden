; CUDA tree-sitter queries for extracting code symbols and relationships
; CUDA extends C/C++ with kernel and device function qualifiers

; Global kernel functions (__global__)
(function_definition
  (storage_class_specifier) @_specifier
  (function_declarator
    (identifier) @code_function.name)
  (#match? @_specifier "__global__")) @code_function.def

; Device functions (__device__)
(function_definition
  (storage_class_specifier) @_specifier
  (function_declarator
    (identifier) @code_function.name)
  (#match? @_specifier "__device__")) @code_function.def

; Host functions (__host__)
(function_definition
  (storage_class_specifier) @_specifier
  (function_declarator
    (identifier) @code_function.name)
  (#match? @_specifier "__host__")) @code_function.def

; Regular C/C++ function definitions (fallback)
(function_definition
  (function_declarator
    (identifier) @code_function.name)) @code_function.def

; Struct definitions
(struct_specifier
  name: (type_identifier) @code_struct.name) @code_struct.def

; Class definitions
(class_specifier
  name: (type_identifier) @code_class.name) @code_class.def

; Typedef declarations
(type_definition
  declarator: (type_identifier) @code_type.name) @code_type.def

; Enum definitions
(enum_specifier
  name: (type_identifier) @code_enum.name) @code_enum.def

; Comments
(comment) @comment

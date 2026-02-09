; CMake tree-sitter queries for extracting code symbols and relationships

; Function definitions
(function_def
  (function_command
    (argument_list
      (argument) @code_function.name))) @code_function.def

; Macro definitions
(macro_def
  (macro_command
    (argument_list
      (argument) @code_function.name))) @code_function.def

; Variable assignments (set command)
(normal_command
  (identifier) @_cmd
  (argument_list
    (argument) @code_variable.name)
  (#eq? @_cmd "set")) @code_variable.def

; Project definition
(normal_command
  (identifier) @_cmd
  (argument_list
    (argument) @code_module.name)
  (#eq? @_cmd "project")) @code_module.def

; Add library
(normal_command
  (identifier) @_cmd
  (argument_list
    (argument) @code_variable.name)
  (#eq? @_cmd "add_library")) @code_variable.def

; Add executable
(normal_command
  (identifier) @_cmd
  (argument_list
    (argument) @code_variable.name)
  (#eq? @_cmd "add_executable")) @code_variable.def

; Comments
(line_comment) @comment
(bracket_comment) @comment

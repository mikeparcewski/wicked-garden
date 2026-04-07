; Ruby tree-sitter queries for extracting code symbols and relationships

; Class definitions
(class
  name: (constant) @code_class.name
  body: (_) @code_class.body
) @code_class.def

; Singleton class definitions
(singleton_class
  value: (constant) @code_class.name
  body: (_) @code_class.body
) @code_class.def

; Module definitions
(module
  name: (constant) @code_module.name
  body: (_) @code_module.body
) @code_module.def

; Method definitions
(method
  name: (identifier) @code_method.name
  parameters: (method_parameters)? @code_method.params
  body: (_)? @code_method.body
) @code_method.def

; Singleton method definitions (class methods)
(singleton_method
  name: (identifier) @code_method.name
  parameters: (method_parameters)? @code_method.params
  body: (_)? @code_method.body
) @code_method.def

; Method calls - capture receiver for chained calls
; Handles obj.method(), self.method(), get_obj().method(), etc.
(call
  receiver: (_)? @call.object
  method: (identifier) @call.method
  arguments: (argument_list)? @call.args
) @call

; Require/require_relative imports
(call
  method: (identifier) @_method
  arguments: (argument_list
    (string) @import.source
  )
  (#match? @_method "^require(_relative)?$")
) @import

; Comments
(comment) @comment

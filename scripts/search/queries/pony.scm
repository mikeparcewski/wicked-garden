; Pony tree-sitter queries for extracting code symbols and relationships
; Converted from pony-tags.scm

;Class definitions 	@code_class.def
;Function definitions 	@code_function.def
;Interface definitions 	@code_interface.def
;Method definitions 	@code_function.def
;Module definitions 	@code_module.def
;Function/method calls 	@call.ref
;Class reference 	@code_class.ref
;Interface implementation 	@implementation.ref
(
  (identifier) @code_class.ref
  (#match? @code_class.ref "^_*[A-Z][a-zA-Z0-9_]*$")
)

(class_definition (identifier) @code_class.name) @code_class.def
(actor_definition (identifier) @code_class.name) @code_class.def
(primitive_definition (identifier) @code_class.name) @code_class.def
(struct_definition (identifier) @code_class.name) @code_class.def
(type_alias (identifier) @code_class.name) @code_class.def

(trait_definition (identifier) @code_interface.name) @code_interface.def
(interface_definition (identifier) @code_interface.name) @code_interface.def

(constructor (identifier) @code_function.name) @code_function.def
(method (identifier) @code_function.name) @code_function.def
(behavior (identifier) @code_function.name) @code_function.def

(class_definition (type) @call.implementation) @implementation.ref
(actor_definition (type) @call.implementation) @implementation.ref
(primitive_definition (type) @call.implementation) @implementation.ref
(struct_definition (type) @call.implementation) @implementation.ref
(type_alias (type) @call.implementation) @implementation.ref

; calls - not catching all possible call cases of callees for capturing the method name
(call_expression callee: [(identifier) (ffi_identifier)] @call.function) @call.ref
(call_expression callee: (generic_expression [(identifier) (ffi_identifier)] @call.function)) @call.ref
(call_expression callee: (member_expression (identifier) @call.function .)) @call.ref
(call_expression callee: (member_expression (generic_expression [(identifier) (ffi_identifier)] @call.function) .)) @call.ref
; TODO: add more possible callee expressions
(call_expression) @call.ref

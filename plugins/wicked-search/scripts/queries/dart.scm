; Dart tree-sitter queries for extracting code symbols and relationships
; Converted from dart-tags.scm

; Import declarations
(import_specification) @import

; Top-level classes only
(program
  (class_definition
    name: (identifier) @code_class.name) @code_class.def)

(method_signature
  (function_signature)) @code_function.def

(type_alias
  (type_identifier) @code_type.name) @code_type.def

(method_signature
  (getter_signature
    name: (identifier) @code_function.name)) @code_function.def

(method_signature
  (setter_signature
    name: (identifier) @code_function.name)) @code_function.def

(method_signature
  (function_signature
  name: (identifier) @code_function.name)) @code_function.def

(method_signature
  (factory_constructor_signature
    (identifier) @code_function.name)) @code_function.def

(method_signature
  (constructor_signature
  name: (identifier) @code_function.name)) @code_function.def

(method_signature
  (operator_signature)) @code_function.def

(method_signature) @code_function.def

(mixin_declaration
  (mixin)
  (identifier) @code_class.name) @code_class.def

(extension_declaration
  name: (identifier) @code_class.name) @code_class.def

(enum_declaration
  name: (identifier) @code_enum.name) @code_enum.def

(function_signature
  name: (identifier) @code_function.name) @code_function.def

(new_expression
  (type_identifier) @code_class.ref) @code_class.ref

(initialized_variable_definition
  name: (identifier)
  value: (identifier) @code_class.ref
  value: (selector
	"!"?
	(argument_part
	  (arguments
	    (argument)*))?)?) @code_class.ref

(assignment_expression
  left: (assignable_expression
		  (identifier)
		  (unconditional_assignable_selector
			"."
			(identifier) @call.function))) @call.ref

(assignment_expression
  left: (assignable_expression
		  (identifier)
		  (conditional_assignable_selector
			"?."
			(identifier) @call.function))) @call.ref

((identifier) @name
 (selector
    "!"?
    (conditional_assignable_selector
      "?." (identifier) @call.function)?
    (unconditional_assignable_selector
      "."? (identifier) @call.function)?
    (argument_part
      (arguments
        (argument)*))?)*
	(cascade_section
	  (cascade_selector
		(identifier)) @call.function
	  (argument_part
		(arguments
		  (argument)*))?)?) @call.ref

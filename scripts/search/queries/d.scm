; D tree-sitter queries for extracting code symbols and relationships
; Converted from d-tags.scm

(module_def (module_declaration (module_fqn) @code_module.name)) @code_module.def

(struct_declaration (struct) . (identifier) @code_class.name) @code_class.def
(interface_declaration (interface) . (identifier) @code_interface.name) @code_interface.def
(enum_declaration (enum) . (identifier) @code_type.name) @code_type.def

(class_declaration (class) . (identifier) @code_class.name) @code_class.def
(constructor (this) @code_function.name) @code_function.def
(destructor (this) @code_function.name) @code_function.def
(postblit (this) @code_function.name) @code_function.def

(manifest_declarator . (identifier) @code_type.name) @code_type.def

(function_declaration (identifier) @code_function.name) @code_function.def

(union_declaration (union) . (identifier) @code_type.name) @code_type.def

(anonymous_enum_declaration (enum_member . (identifier) @code_variable.name)) @code_variable.def

(enum_declaration (enum_member . (identifier) @code_variable.name)) @code_variable.def

(call_expression (identifier) @call.function) @call.ref
(call_expression (type (template_instance (identifier) @call.function))) @call.ref
(parameter (type (identifier) @code_class.ref) @code_class.ref (identifier))

(variable_declaration (type (identifier) @code_class.ref) @code_class.ref (declarator))

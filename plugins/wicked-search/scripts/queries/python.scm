; Python tree-sitter queries for extracting code symbols and relationships
; Enhanced for SQLAlchemy and Django ORM detection

; ============================================================================
; Class definitions with inheritance (for ORM model detection)
; ============================================================================

; Class with bases (captures SQLAlchemy Base, Django Model, etc.)
(class_definition
  name: (identifier) @code_class.name
  superclasses: (argument_list
    (identifier) @code_class.base
  )?
  body: (block) @code_class.body
) @code_class.def

; ============================================================================
; SQLAlchemy ORM patterns
; ============================================================================

; __tablename__ = "table_name"
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @orm_sqlalchemy.tablename_key
        right: (string) @orm_sqlalchemy.tablename_value
      )
    )
  )
) @orm_sqlalchemy.model
(#eq? @orm_sqlalchemy.tablename_key "__tablename__")

; Column definitions: field = Column(Type, ...)
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @orm_sqlalchemy.field_name
        right: (call
          function: (identifier) @orm_sqlalchemy.column_func
          arguments: (argument_list
            (_)* @orm_sqlalchemy.column_args
          )
        )
      )
    )
  )
)

; Relationship definitions: field = relationship("Model", ...)
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @orm_sqlalchemy.rel_name
        right: (call
          function: (identifier) @orm_sqlalchemy.rel_func
          arguments: (argument_list
            (string)? @orm_sqlalchemy.rel_target
            (_)* @orm_sqlalchemy.rel_args
          )
        )
      )
    )
  )
)

; mapped_column() for SQLAlchemy 2.0 style
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @orm_sqlalchemy.field_name
        right: (call
          function: (identifier) @orm_sqlalchemy.mapped_func
          arguments: (argument_list) @orm_sqlalchemy.mapped_args
        )
      )
    )
  )
)

; ============================================================================
; Django ORM patterns
; ============================================================================

; Django model field: field = models.CharField(max_length=100)
(class_definition
  body: (block
    (expression_statement
      (assignment
        left: (identifier) @orm_django.field_name
        right: (call
          function: (attribute
            object: (identifier) @orm_django.models_module
            attribute: (identifier) @orm_django.field_type
          )
          arguments: (argument_list) @orm_django.field_args
        )
      )
    )
  )
)

; Django Meta class for table name
(class_definition
  body: (block
    (class_definition
      name: (identifier) @orm_django.meta_class
      body: (block
        (expression_statement
          (assignment
            left: (identifier) @orm_django.meta_key
            right: (_) @orm_django.meta_value
          )
        )
      )
    )
  )
)

; ============================================================================
; Standard Python patterns
; ============================================================================

; Method definitions (functions inside classes)
(class_definition
  body: (block
    (function_definition
      name: (identifier) @code_method.name
      parameters: (parameters) @code_method.params
      body: (block) @code_method.body
    ) @code_method.def
  )
)

; Function definitions
(function_definition
  name: (identifier) @code_function.name
  parameters: (parameters) @code_function.params
  body: (block) @code_function.body
) @code_function.def

; Import statements
(import_statement
  name: (dotted_name) @import.module
) @import

(import_from_statement
  module_name: (dotted_name) @import.module
  name: (dotted_name)? @import.name
) @import.from

; Function calls - simple function calls like foo()
(call
  function: (identifier) @call.function
) @call

; Method calls - any attribute call like obj.method()
(call
  function: (attribute
    object: (_) @call.object
    attribute: (identifier) @call.method
  )
) @call.method

; Variable assignments
(assignment
  left: (identifier) @code_variable.name
  right: (_) @code_variable.value
) @assignment

; Decorators with name and arguments
(decorated_definition
  (decorator
    (identifier) @code_decorator.name
  )
  definition: (_) @decorated.target
)

(decorated_definition
  (decorator
    (call
      function: (identifier) @code_decorator.name
      arguments: (argument_list) @code_decorator.args
    )
  )
  definition: (_) @decorated.target
)

; Attribute decorators like @app.route
(decorated_definition
  (decorator
    (call
      function: (attribute
        object: (identifier) @code_decorator.object
        attribute: (identifier) @code_decorator.name
      )
      arguments: (argument_list) @code_decorator.args
    )
  )
  definition: (_) @decorated.target
)

; Comments and docstrings
(comment) @comment

(expression_statement
  (string) @docstring
)

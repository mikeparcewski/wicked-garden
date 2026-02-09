; Elixir tree-sitter queries for extracting code symbols and relationships
; Converted from elixir-tags.scm

; Definitions

; * modules and protocols
(call
  target: (identifier) @_ignore
  (arguments (alias) @code_module.name)
  (#match? @_ignore "^(defmodule|defprotocol)$")) @code_module.def

; * functions/macros
(call
  target: (identifier) @_ignore
  (arguments
    [
      ; zero-arity functions with no parentheses
      (identifier) @code_function.name
      ; regular function clause
      (call target: (identifier) @code_function.name)
      ; function clause with a guard clause
      (binary_operator
        left: (call target: (identifier) @code_function.name)
        operator: "when")
    ])
  (#match? @_ignore "^(def|defp|defdelegate|defguard|defguardp|defmacro|defmacrop|defn|defnp)$")) @code_function.def

; References

; ignore calls to kernel/special-forms keywords
(call
  target: (identifier) @_ignore
  (#match? @_ignore "^(def|defp|defdelegate|defguard|defguardp|defmacro|defmacrop|defn|defnp|defmodule|defprotocol|defimpl|defstruct|defexception|defoverridable|alias|case|cond|else|for|if|import|quote|raise|receive|require|reraise|super|throw|try|unless|unquote|unquote_splicing|use|with)$"))

; ignore module attributes
(unary_operator
  operator: "@"
  operand: (call
    target: (identifier) @_ignore))

; * function call
(call
  target: [
   ; local
   (identifier) @call.function
   ; remote
   (dot
     right: (identifier) @call.function)
  ]) @call.ref

; * pipe into function call
(binary_operator
  operator: "|>"
  right: (identifier) @call.function) @call.ref

; * modules
(alias) @code_module.ref @code_module.ref

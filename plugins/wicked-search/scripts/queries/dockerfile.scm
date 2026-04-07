; Dockerfile query patterns

; FROM instruction (base image)
(from_instruction) @statement.from

; RUN instruction (commands)
(run_instruction) @statement.run

; COPY/ADD instructions
(copy_instruction) @statement.copy
(add_instruction) @statement.add

; ENV instruction (environment variables)
(env_instruction) @statement.env

; EXPOSE instruction (ports)
(expose_instruction) @statement.expose

; WORKDIR instruction
(workdir_instruction) @statement.workdir

; CMD/ENTRYPOINT instructions
(cmd_instruction) @statement.cmd
(entrypoint_instruction) @statement.entrypoint

; LABEL instruction
(label_instruction) @statement.label

; ARG instruction (build arguments)
(arg_instruction) @statement.arg

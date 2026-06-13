# Repository Structure

The repository uses a hybrid structure:

```text
tools/<domain>/<subdomain>/<technology>/
packages/<language>/<package>/
bootstrap/<platform>/
```

Use `tools/` for standalone scripts that can be run by users. Use `packages/` for code that is imported by tools or has its own internal module structure. Use `bootstrap/` for scripts that install or expose the toolbox itself on a system.

## Entrypoint Markers

Publish a script as a command:

```text
scripts-toolbox: entrypoint
```

Never publish a script:

```text
scripts-toolbox: no-path
```

Override the generated command name:

```text
scripts-toolbox: command=my_command_name
```

This avoids relying on directory depth, which breaks as projects become larger.

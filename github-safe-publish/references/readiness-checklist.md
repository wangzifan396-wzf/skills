# Repository readiness checklist

Use this checklist when the scanner reports missing or weak repository essentials. Verify every
statement against the project; do not fill sections with guesses.

## README

Include, when applicable:

1. Project name and a one-sentence value statement.
2. A real screenshot or output example.
3. Supported environment and prerequisites.
4. Copyable install and run commands.
5. Test or verification commands.
6. A concise project structure or main entry-point map.
7. Known limitations and status.
8. Contribution/contact route if the maintainer wants one.
9. The license name with a link to the license file.

Keep badges truthful. Do not add build, coverage, download, or version badges that have no backing
service.

## License

- Ask the user when no license intent is known.
- Do not infer MIT, Apache-2.0, GPL, or another license merely because the repository is public.
- Preserve third-party notices and bundled license files.
- State when legal review may be necessary; this Skill does not provide legal advice.

## Run and test instructions

- Derive commands from package scripts, project configuration, or commands actually executed.
- Distinguish installation, development, production build, and test commands.
- Mention environment variables by name but never include real values.
- For a static/single-file project, state whether opening the file is sufficient or a local HTTP
  server is required.

## Repository metadata

Check the default branch, repository description, topics, homepage, and release status after source
publication. Changing these settings is a separate external action and requires user authorization
and a suitable GitHub tool.

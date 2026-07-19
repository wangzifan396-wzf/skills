# CSDN technical article standard

Use this standard before outlining or drafting.

## Evidence first

- Record the source of every number, version, date, benchmark, test result, commit, and feature.
- Distinguish measured values from targets, configuration limits, and estimates.
- Describe the tested environment for performance or compatibility results.
- Link public claims to the repository, commit, data file, or reproducible command when appropriate.
- State material limitations close to the claim they qualify.

## Choose one primary argument

Good article centers include:

- solving a concrete engineering problem;
- explaining a reusable workflow;
- comparing two designs with explicit tradeoffs;
- reporting a reproducible experiment;
- open-sourcing a tool and explaining its safety boundary;
- reflecting on a project using real data rather than impressions alone.

Avoid a chronological list of everything done unless chronology is itself the insight.

## Recommended structure

1. **H1 title**: include the problem, result, or reusable object without unsupported superlatives.
2. **Publication note**: keep local cover/category/image instructions in a removable top blockquote.
3. **Opening**: establish the reader's problem, stakes, and article payoff within the first few
   paragraphs.
4. **Scope and evidence**: define what was inspected, tested, measured, or built.
5. **Main explanation**: use H2 sections for the story and H3 only when the subsection is useful.
6. **Reproduction**: include copyable commands, important code, data, or install steps.
7. **Limitations**: explain what the method or tool deliberately does not prove or automate.
8. **Conclusion and CTA**: summarize the transferable lesson, then link the relevant project once.
9. **Publication information**: keep alternative titles, tags, cover and editor reminders in a
   removable final section.

## Writing quality

- Prefer concrete nouns and verbs over generic claims such as “greatly improved.”
- Explain why a design exists before listing implementation details.
- Keep paragraphs readable on mobile; split dense reasoning into short paragraphs or lists.
- Introduce every code block and explain the part that matters afterward.
- Use tables for exact comparisons, not for decorative summaries.
- Avoid repeating the same conclusion in the opening, every section, and the ending.
- Keep promotional language proportional to demonstrated results.

## Originality and attribution

- Write from project evidence and direct reasoning.
- Quote sparingly and identify the source.
- Do not paraphrase another article section-by-section.
- Attribute third-party libraries, datasets, diagrams, and licensed assets where material.
- Do not imply that an AI-generated draft was independently researched when evidence was not
  inspected.

## CSDN-oriented details

- Use one H1 and a clear H2 table-of-contents structure.
- Prefer 3-5 precise tags over broad tag stuffing.
- Write an abstract that contains the problem, method, evidence and outcome.
- Keep local editor instructions outside the paste-ready body.
- Verify that commands are valid for the stated shell and operating system.
- Use fenced code language labels such as `python`, `javascript`, `json`, `bash`, or `powershell`.
- Preserve Markdown source separately from the CSDN editor version.

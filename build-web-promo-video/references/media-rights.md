# Media provenance and rights

Use this checklist before rendering and before distributing any generated bundle. This is an
engineering checklist, not legal advice.

## Verify

- The author owns or may record the web project and visible data.
- Logos, screenshots, artwork, fonts, music, sound effects, clips, and voice output may be used for
  the intended distribution.
- Third-party notices and attribution requirements are preserved.
- Private information, account details, tokens, email addresses, and user content are absent.
- Public links and product claims are accurate.

## Generated audio

- Procedural music produced by this Skill is deterministic code output, but still review it for
  accidental resemblance and project suitability.
- Optional TTS output depends on the selected provider's current terms and the user's use case.
  Do not assume the Skill repository license automatically grants rights to a service's output.
- Keep user-supplied narration and music outside the Skill repository unless redistribution rights
  are clear.

## Tooling licenses

- Do not redistribute FFmpeg or browser binaries from the output bundle by default.
- Follow the licenses of FFmpeg, Playwright, codecs, and any installed dependencies.
- A code license does not automatically cover third-party media or generated service output.

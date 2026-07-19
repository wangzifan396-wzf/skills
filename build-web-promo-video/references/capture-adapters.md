# Capture actions and adapters

Prefer declarative actions in configuration. Use an adapter only when the project cannot reach a
useful deterministic state through ordinary interaction.

## Supported declarative actions

- `click`: require `selector`.
- `press`: require `key`; optionally provide `selector`.
- `type`: require `selector` and `text`.
- `mouseMove`: require numeric `x` and `y`; optionally provide `steps`.
- `mouseDown` / `mouseUp`: optionally provide a mouse `button`.
- `scroll`: provide numeric `deltaX` and/or `deltaY`.
- `wait`: do nothing until the action's configured `at` time.

Every action uses an `at` value in seconds from the moment the page and adapter are ready. Keep
actions sorted and within the scene duration.

## Adapter contract

Set `adapter` to a JavaScript module below the project root. Export a default async function:

```javascript
export default async function prepare({ page, context, scene, config, baseUrl, profile }) {
  // Put the real page in a deterministic, recordable state.
}
```

`profile` is the active render profile when `capture.perProfile` is enabled, otherwise it is
`null`. Use it only when the page needs profile-specific deterministic setup.

Review adapter code as project code. It runs with browser-page access and can modify application
state. Keep it local, deterministic, and limited to the requested project.

## Safety

- Do not use adapters to read cookies, passwords, storage from unrelated origins, or account data.
- Do not bypass authentication, CAPTCHA, anti-bot controls, subscriptions, or access restrictions.
- Do not capture private dashboards or personal information without explicit authorization.
- Prefer a project-owned debug hook or seeded fixture over manipulating hidden implementation
  details.
- Record adapter usage in the capture manifest.

# Chapter 56 - Governance tabs

> **Goal:** fix a small but real annoyance - the governance sub-pages (Committee,
> Protocol parameters, Protocol updates) were dead ends. From one you had to go
> back to the governance overview to reach another. A shared tab bar fixes that.

Each governance view now renders the same tab bar at the top - **Overview**,
**Committee**, **Protocol parameters**, **Protocol updates** - with the current one
highlighted. So from any governance page you can jump straight to any other, the
way a professional explorer's sectioned tabs work.

It is one helper, `govTabs(active)`, placed at the top of `governancePage`,
`committeePage`, `paramsPage`, and `protocolUpdatesPage`. Purely presentational -
no backend or endpoint changes.

## Test

No Python changed, so `make check` stays green; the behaviour is verified by
opening the governance section and switching tabs.

## What we built

- A `govTabs` tab bar shared across all governance sub-pages.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch56): shared governance tab bar across the sub-pages"
git tag ch56
```

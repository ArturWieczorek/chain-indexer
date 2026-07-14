# Chapter 53 - Favicons, theme, and colour

> **Goal:** polish both front-ends - a favicon for each, a dark/light theme
> toggle, and a small accent-colour picker - remembered across visits. This is a
> presentation chapter: no backend changes, no new endpoints.

## Favicons

Each page gets an inline-SVG favicon as a data URI (no extra file to serve): the
explorer a blue rounded square with a `C`, the live view a green dot, so the two
browser tabs are easy to tell apart.

## Theme and accent, remembered

The pages already styled everything through CSS variables (`--bg`, `--panel`,
`--accent`, ...). A light theme is just those variables overridden under
`:root[data-theme="light"]`. A **theme** button toggles `data-theme` on the root
element; a row of **accent swatches** sets `--accent`. Both choices are saved in
`localStorage` (`ci-theme`, `ci-accent`) and re-applied on load, and both pages
share those keys, so a choice made in the explorer carries over to the live view.

Because it is all CSS variables plus a few lines of vanilla JavaScript, there is no
build step and nothing new on the server.

## Test

There is no Python to test here; `make check` stays green (the change is entirely
in the two static HTML pages). The behaviour is verified by loading the pages and
toggling the theme and colours.

## What we built

- Inline-SVG favicons for the explorer and live pages.
- A light theme (CSS-variable overrides), a theme toggle, and accent-colour
  swatches, persisted in `localStorage` and shared across both pages.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch53): favicons, dark/light theme, and accent colour selection"
git tag ch53
```

## Next up

An optional, opt-in per-epoch stake history (via local-state-query) to chart stake
over time - the honest, feasible slice of a rewards/trend view.

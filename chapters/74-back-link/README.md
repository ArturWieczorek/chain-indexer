# Chapter 74 - A Back link on every detail page

> **Goal:** let a detail page return to where you came from, without re-clicking the
> nav section.

## The papercut

From **Tokens** you click a token to open its asset page. To get back to the list
you had to click **Tokens** in the nav again. The same was true of any drill-down (a
transaction, a pool, an account): the only way back was the nav, which does not
always match where you actually came from.

## The fix

One change in the hash router: after it renders any route other than home, it
prepends a small **Back** link that calls `history.back()`. Because the explorer is
a hash-routed single page, browser history already records each view, so this
returns to the exact previous page - the tokens list, the policy page, the tx you
came from - whatever it was. It is one central line, so every detail page gets it
for free, and it is more robust than a fixed breadcrumb because it follows your
actual path rather than a guessed parent.

## What we built

- A router-level Back link (`history.back()`) on every non-home page, with a small
  `.backlink` style.

## Commit and tag

```bash
git add -A
git commit -m "feat(ch74): a Back link on every detail page"
git tag ch74
```

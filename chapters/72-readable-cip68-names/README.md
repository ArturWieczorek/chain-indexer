# Chapter 72 - Readable CIP-68 names and graceful images

> **Goal:** stop showing a CIP-68 token as a wall of hex, and stop a dead image
> link from leaving a broken-image icon.

## Two small explorer bugs

Viewing a CIP-68 NFT (for example `000de140436970363844656d6f`) showed two rough
edges:

1. **The name was raw hex.** A CIP-68 name begins with a 4-byte CIP-67 label prefix
   (`000de140` for a 222 user token, `000643b0` for the 100 reference token, and so
   on). Those prefix bytes are not printable, so decoding the whole name to text
   failed and the page fell back to the raw hex.
2. **A dead image left a broken icon.** The asset page rendered the metadata image
   in an `<img>` with no error handling, so an unreachable link (a dead IPFS CID, an
   offline gateway) showed the browser's broken-image glyph.

## The fixes

- **Names:** `_asset_name_text` now strips a known CIP-67 label prefix before
  decoding, so the readable part shows (`Cip68Demo`) - everywhere the name appears
  (asset page, policy page, token and mint lists), not just one screen.
- **Asset page name:** it now prefers the metadata `name` (CIP-25 or CIP-68) when
  present, then the decoded asset name, then the raw hex - so a titled NFT shows its
  title.
- **Images:** the `<img>` gets an `onerror` that replaces a failed load with a plain
  "image did not load" note instead of a broken icon.

## Test first (red), make it pass (green)

`test_api.py` gains cases for the CIP-68 (`000de140...`) and reference
(`000643b0...`) prefixes decoding to their readable tail, alongside the existing
plain-name and non-text cases. The explorer changes are front-end only. `make check`
stays green at 100 percent.

## What we built

- `_asset_name_text` strips the CIP-67 label prefix before decoding.
- The asset page prefers the metadata name and handles a failed image gracefully.

## Commit and tag

```bash
git add -A
git commit -m "fix(ch72): readable CIP-68 asset names and graceful image failures"
git tag ch72
```

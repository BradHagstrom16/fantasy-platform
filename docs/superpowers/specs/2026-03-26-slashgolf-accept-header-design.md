# SlashGolf API: Add Accept Header for Clean JSON Responses

**Date:** 2026-03-26
**Status:** Approved

## Problem

The SlashGolf API returns EJSON (MongoDB Extended JSON) by default, wrapping values like:
```json
{"roundId": {"$numberInt": "1"}}
{"date": {"start": {"$date": {"$numberLong": "1768497660000"}}}}
```

The API supports an `Accept: application/json` header that returns standard JSON instead:
```json
{"roundId": 1}
```

Our codebase has EJSON-unwrapping logic scattered across `sync.py` and `utils.py`. Adding the header simplifies API responses while keeping fallback parsing for safety.

## Scope

Two changes in one file (`games/golf/services/sync.py`). No changes needed in `utils.py`.

### Change 1: Add `Accept: application/json` header

In `SlashGolfAPI.__init__`, add the Accept header to `self.headers`:

```python
self.headers = {
    "X-RapidAPI-Key": api_key,
    "X-RapidAPI-Host": api_host,
    "Accept": "application/json",
}
```

### Change 2: Fix hardcoded EJSON path in `sync_schedule()`

Line 358 has a hardcoded EJSON traversal with no fallback:
```python
start_ts = int(event["date"]["start"]["$date"]["$numberLong"]) / 1000
```

This will break when the API returns clean JSON. Replace with a helper that handles both formats, reusing the existing `_parse_tee_time_timestamp()` pattern (dict-unwrap with plain int fallback).

### No other changes needed

These three parsing functions already handle both EJSON and plain values:
- `_parse_tee_time_timestamp()` — handles `{"$date": {"$numberLong": ...}}` and plain `int`
- `_parse_api_number()` — handles `$numberInt`/`$numberLong`/`$numberDouble` and plain `int`
- `parse_score_to_par()` (in `utils.py`) — handles `$numberInt`/`$numberLong`, plain `int`, and strings

## Risk Assessment

**Low risk.** The header is additive. All existing EJSON fallback parsing remains intact. The one breaking path (hardcoded EJSON traversal in `sync_schedule`) gets fixed to handle both formats.

## Verification

- Smoke test the app starts without errors
- Read through each parsing path to confirm both formats are handled
- Existing production behavior unchanged (EJSON parsing still works as fallback)

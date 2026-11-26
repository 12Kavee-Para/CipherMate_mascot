# CipherMate acceptance checks

Run `python -m pytest -q` from the project root with the development dependencies installed. These 30 scenarios summarize assertions in `tests/test_backend.py`. Each test uses temporary state and synthetic credentials. Provider responses are simulated.

| # | Sample input or action | Verified outcome |
|---|---|---|
| 1 | Request capabilities without a token | HTTP 401 in authenticated mode |
| 2 | Alice uploads docs/a.txt containing hello world | Alice downloads the same bytes and Bob cannot see the file |
| 3 | Upload a path containing ../ | Request rejected |
| 4 | Upload 5 MiB plus one byte | HTTP 413 |
| 5 | Encrypt a 5 MiB file | Encoded output exceeds the file limit. Original survives and destination is absent |
| 6 | Upload two equal .txt files and one different .pdf | Duplicate group contains both text files and extension search returns two matches |
| 7 | Compare hello world with its SHA-256 and with 64 zeros | First comparison matches and second differs |
| 8 | Request copy from a to b | Destination appears only after owner approval with matching digest |
| 9 | Reject a copy or approve after expiry | No copy appears |
| 10 | Create the destination while approval is pending | Existing destination survives |
| 11 | Change the source while approval is pending | Stale approval is rejected |
| 12 | Submit the same copy twice with request-1 | Same job returned. Changing parameters with that key returns a conflict |
| 13 | Decrypt sample.cm containing bytes 0 through 255 | Owner downloads identical bytes after approval. Ciphertext survives and Bob cannot approve or download |
| 14 | Decrypt using the wrong key | Failed job and absent output |
| 15 | Alter the encrypted token before decrypting | Failed job and absent output |
| 16 | Decrypt opaque.bin with a missing key, then a valid key | Missing reference rejected and unsupported envelope fails. Source survives |
| 17 | Replace a vault key after requesting encryption | Pending approval reports RESOURCE_CHANGED |
| 18 | Sign a, then verify a and modified | Original verifies and changed data fails verification |
| 19 | Identify bytes containing unknown | Format reported as UNKNOWN |
| 20 | Store and list a synthetic credential | Listing and history omit the value. Database scan finds no plaintext sentinel |
| 21 | Submit an invalid vault kind with a sensitive value | HTTP 422 without echoing the value |
| 22 | Paste a synthetic OpenRouter key into chat | API blocks the request before planning |
| 23 | Move a to dir/a, rename to dir/b, then approve deletion | Bytes survive the move and rename. Deleted name becomes inaccessible |
| 24 | Request Linux resource inspection and template execution with lab mode disabled | Both rejected. Script preview remains available |
| 25 | Ask offline chat to show secrets | No job created |
| 26 | Ask simulated provider to calculate hash of a | Validated job completes. Uploaded bytes and vault sentinel stay out of provider payload |
| 27 | Provider returns invalid JSON or an approval field | HTTP 502 and no model-granted approval |
| 28 | Approve one copy concurrently twice | Exactly one completion |
| 29 | Alice clears activity after Bob lists files | Alice retains a clear event. Bob retains his history |
| 30 | Submit local-demo chat with a foreign Origin | HTTP 403. Same-origin loopback chat succeeds |

Local result on Python 3.14: 37 passed. One Starlette TestClient deprecation warning references AnyIO BlockingPortal. JavaScript syntax check passed. The GitHub Actions workflow targets Python 3.13. Hosted CI, browser interaction and live provider credentials were not verified in this run.

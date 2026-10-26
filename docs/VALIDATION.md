# Public export validation

Verified on 26 October 2026. These checks apply to the curated public package and its included synthetic fixture. They do not rerun the historical full studies or establish operational calibration.

| Check | Result |
| --- | --- |
| Focused engine tests | 85 passed on Python 3.9.6 and Python 3.14 |
| Local dashboard tests | 18 passed on Python 3.9.6 and Python 3.14, including loopback access controls, real execution, ZIP export and restart history |
| Dashboard self-test | Passed; engine 0.10.0 and dashboard 0.3.0 |
| Deterministic workflow smoke | 8 training needs completed and 9 proof records, including one proof-only case; reconciliation passed |
| Clean local Git clone | Fresh history cloned into a separate directory; 85 engine tests, 18 dashboard tests, dashboard self-test and workflow smoke passed on Python 3.9.6 |
| Generated run provenance | Engine location is `src`; no absolute source directory is serialized |
| Static explorer | Both JavaScript files pass syntax checks; local HTML assets resolve; three JSON datasets parse |
| Language links | Valid `?lang=en` / `?lang=de` overrides saved and browser preferences; manual selection updates the URL while retaining other parameters and the fragment; invalid queries and unavailable storage/history retain working fallbacks |
| Publication boundary | No copied private history, original documents, employee roster or symlink |
| Targeted text scan | No absolute user path, internal service URL, email, common credential signature or private document-path citation detected |

The clone test uses only the exported files, with no bundled second engine and no access to original research inputs. Final attribution/documentation changes do not alter its verified executable or input bytes. No remote publication is asserted by this local record.

The targeted scan is a bounded inspection of current text bytes, not a guarantee against every possible sensitive pattern. Inputs retain anonymized topic labels and source-derived aggregate counts; synthetic people and demand remain explicit.

## Saved evidence

The original 50-fixture comparison receipt reports 200 runs, matching paired fixtures/seed maps and 3,000 verified run-output hashes. Its study manifest hash is:

```text
c4251b673644fb0ee3db757a37c0a6fb1b54f54fa8598a7633fd1c83bd45fe8f
```

That receipt was inspected when curating the frozen aggregates. The historical raw run outputs and private archive are excluded. The public package tests above establish portability and selected behavioural checks; they do not transform the saved receipt into a new study of changed public inputs.

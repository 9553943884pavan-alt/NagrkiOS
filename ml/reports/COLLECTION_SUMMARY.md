# Collection summary

Collected on 2026-11-20 UTC from the [NYC 311 public dataset](https://data.nyc.gov/Social-Services/311-Service-Requests-from-2020-to-Present/erm2-nwe9) through its HTTPS Socrata API. The query requests the first 1,000 records in calendar 2024 ordered by creation time and unique key. It selects case ID, dates, agency, complaint type, descriptor, status and borough. This is a bounded convenience sample, concentrated near the start of 2024; it is not a random or representative sample of NYC, and has no Indian jurisdiction relevance.

| Artifact | Count / size | SHA-256 | Location |
| --- | ---: | --- | --- |
| Raw JSON export | 1,000 rows / 278,980 bytes | `541ab5bca0212d7bc44debfddbabbeb75dded9a5229f9b4267be3d878a4e272b` | Ignored `ml/data/raw/nyc_311_2024_bounded/` |
| Prepared JSONL | 1,000 rows | `a1998e58774e6995e32b3c42be2ce7f733ab48fbb63fbc2b2e448823eb3866b4` | Ignored `ml/data/processed/` |
| Grouped split manifest | 1,000 IDs | `a8261bcbed8af6e6af389316f5bed9ce453cff3ed1b3a665caa53a6560258e54` | Ignored `ml/data/evaluation/` |
| Annotation review sample | 15 IDs | `86336d8f336163fcd860a06601263e2847dadd03a0f2c454bdc0e230e8243a4` | Ignored `ml/data/evaluation/` |

Raw and processed manifests, local collection timestamp, exact query, and license evidence remain in `ml/data/manifests/nyc_311_2024_bounded.json` and the prepared manifest. Automated verification passed: 1,000 unique record IDs, complete split coverage, no cross-split exact/near-duplicate groups, and no obvious remaining identifiers detected by the defined regex rules. A second acquisition reused the verified file without downloading it again.

No Indian complaint-text dataset was downloaded. Conditional and restricted source decisions appear in `SOURCE_AUDIT.md`.

## Phase 2 addition

The [Nandi synthetic subset](NANDI_PHASE2.md) was acquired from the public Hugging Face dataset viewer at pinned revision `cf76fd674a7bf03c770a92eaca0e81825cb949fc` under its stated Apache-2.0 license. Nine bounded 100-row train slices produced a deterministic 150-row subset: 50 English, 50 Hindi and 50 Hinglish; 120 generated complaint-domain rows plus 30 generated out-of-scope rows. This is a quota sample, not representative of citizen traffic. Minimal selected raw JSONL SHA-256: `53d9f1f517aadaa442f61ae5be050111e26c01dcddf1981cefcfe397baf8c5ef`; prepared JSONL SHA-256: `c4d60f63e7d82a064e5814783ee11dc57aac2e746dc7063e9e318c4894f2d618`. Both files and their split/review manifests are ignored under `ml/data/`. A repeat acquisition reused the verified files without network access. No conditional real Indian narrative source was downloaded.

## Track A Phase 3 addition

An already-present normal browser CSV download from the [official OpenCity/Janaagraha resource](https://data.opencity.in/dataset/i-change-my-city-data/resource/a60abf5c-3a15-4967-af32-c3074248580f) matched the publisher's MD5 `7cf55ab5a16658abd83f372b5c26851d` exactly. Its SHA-256 was `d951dbb484532421801f6cbd7550edaa6f9ab143da7c4d0e835ba574e4e6d5ac`, with 8,377,752 bytes and **16,071 parsed rows**. Under the publisher-stated CC BY-SA 2.0 resource license, 14,841 rows met the narrative-length plus original-category screening rule; a systematic 1,000-row sample was field-minimized and redacted. Minimized SHA-256: `ccedcc13897bd856b82ce3fa7997409f4729f22dbdb19f1af57aa88f65b636cc`; processed SHA-256: `2e2470a7820fb98a0c6fc94869660b210d19d8d98ecd8fc4915c019d451807d9`; grouped split SHA-256: `c58aa51f60bf174b3262694ab2153ce22398d70bef2713607b0d1603a18c24f0`. The full CSV containing addresses and coordinates was deleted after those checks. The selected rows are **candidates**, with 0 human privacy-reviewed usable rows. See [publisher verification](OPENCITY_PHASE3.md) and [privacy protocol](PHASE3_PRIVACY_PROTOCOL.md).

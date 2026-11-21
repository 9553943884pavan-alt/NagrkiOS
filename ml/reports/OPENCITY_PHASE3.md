# Phase 3 official OpenCity/Janaagraha CSV provenance

Checked 2026-11-20. The [official dataset page](https://data.opencity.in/dataset/i-change-my-city-data) identifies Janaagraha's I Change My City portal as the source. Its [2019–2022 complaint-log resource](https://data.opencity.in/dataset/i-change-my-city-data/resource/a60abf5c-3a15-4967-af32-c3074248580f) identifies a normal CSV upload, `CC BY-SA 2.0` as the resource license ID, source `Janaagraha iCMyC`, credit to Vivek Mathew and Haji Shariefullah, and a 17-field dictionary that includes `title`, `description`, `category_title`, `sub_category_title`, `civic_agency_title`, `created_at` and `complaint_status_title`. It also includes `address`, `location`, latitude, longitude and ward data, which must be excluded from the research extract. Publisher metadata reports hash `7cf55ab5a16658abd83f372b5c26851d` and size about 7.9 MiB.

## Normal CSV versus DataStore API

The ordinary CSV URL published in the resource metadata is:

`https://newdata.opencity.in/dataset/9183b0b2-b49a-40a9-b36d-275e1eaedb3f/resource/a60abf5c-3a15-4967-af32-c3074248580f/download/5f99b09a-64b5-45f0-ab18-4cf0a0cabf6d.csv`

An already-present browser-downloaded CSV was quarantined under Git-ignored `ml/data/raw/opencity_unreviewed/`. I did **not** download another copy. Its Windows `Zone.Identifier` recorded the official resource page as `ReferrerUrl` and the matching `data.opencity.in/.../download/5f99b09a-64b5-45f0-ab18-4cf0a0cabf6d.csv` path as `HostUrl`. The local file had 8,377,752 bytes, 16,071 parsed data rows, and the exact 17 dictionary columns. Its computed MD5 was `7cf55ab5a16658abd83f372b5c26851d`, **identical to the publisher's resource hash**. Its SHA-256 was `d951dbb484532421801f6cbd7550edaa6f9ab143da7c4d0e835ba574e4e6d5ac`. The MD5 match and browser origin provide strong provenance evidence; MD5 is used here only to compare the publisher's published hash, while SHA-256 records local integrity.

The earlier CKAN DataStore field-selected request returned HTTP 403. A single separate HEAD request to the ordinary CSV URL from this shell ended in a network `WebException`, with no HTTP status; it was not retried. We therefore do not claim that programmatic download currently returns HTTP 200. The already-present ordinary browser download is independently matched to the official resource by its hash, size, schema and Windows origin marker. No access restriction was bypassed.

## Rights, minimization and retention

The resource-level CC BY-SA 2.0 notice is publisher-stated reuse permission. Preserve attribution to OpenCity/Janaagraha and the listed credits, cite the resource URL, identify transformations, and review share-alike obligations before distributing an adapted dataset. The license does not by itself eliminate privacy duties or prove that every individual contributor consented to public ML training.

The full CSV contained precise address and coordinate fields. The lead agent verified and deleted it after generating checked, Git-ignored minimized and redacted extracts. The publisher CSV had 16,071 rows; the lead agent's eligibility pass found 14,841 rows with narrative-length text and original category, then selected a bounded 1,000-row research sample. That count is an extraction criterion, **not** a count of human-cleared usable narratives. The source required `cp1252` decoding; encoding and malformed-text effects remain part of the quality review. The minimized raw research file contains only allowed complaint text and source labels, remains Git-ignored and access-limited, and has a redacted processed copy. All narratives require human privacy review before public sharing or model training. No complaint text appears in this report.

The strongest legitimate fallback if the normal CSV is unavailable in a fresh environment is to contact [OpenCity/Janaagraha through the publisher site](https://data.opencity.in/dataset/i-change-my-city-data) for a working public download or a field-minimized authorized export. Do not scrape alternate mirrors or retry a 403-protected endpoint.

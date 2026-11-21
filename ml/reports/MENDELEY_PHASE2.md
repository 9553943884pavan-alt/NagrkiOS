# Phase 2 Mendeley Indian complaint-tweet decision

Reviewed 2026-11-20. **Decision: conditional; acquisition blocked.** No Mendeley archive, post text, post ID, personal metadata, or label rows were downloaded in this phase. The usable real Indian complaint count from this source is **0**.

## Verified provenance and labels

The [publisher's version-1 dataset page](https://data.mendeley.com/datasets/w2cp7h53s5/1) names Swati Agarwal, Nitish Mittal and Ashish Sureka, gives DOI `10.17632/w2cp7h53s5.1`, a 23 July 2016 publication date, and a **CC BY 4.0** license for the deposited dataset. It says the records came from public tweets addressed to four Indian government service accounts. The `Annotated` table has `tweet_ID`, `text`, and a `complaint`/`unknown` class. This is a possible **complaint-detection** annotation, not a civic category, department, urgency, or closure outcome label. The page does not establish that `unknown` means a reviewed non-complaint, so that class needs annotation review before use as a negative label.

The same publisher description says its SQL archive also contains `Posts`, `User_Mentions`, and `Users` tables, with account IDs, handles, names, timestamps, coordinates, and location. The public page does not offer a verified, bounded, privacy-minimized export of just post text plus independent class. Downloading the SQL file merely to extract those columns would bring the unwanted personal metadata into the raw workspace.

## Rights and privacy assessment

- The deposited dataset's CC BY 4.0 notice establishes the publisher's stated license for the deposit. It does **not by itself establish** that the depositor could sublicense every individual user's post text for this project's research or later ML training. [X's current Terms](https://x.com/en/tos) say posters retain rights in their content and uses by others remain subject to platform terms.
- The [official X Developer Policy](https://docs.x.com/developer-terms/policy) restricts redistribution of X content in downloadable datasets to IDs, subject to narrow exceptions. It also requires offline stored content to reflect deletion, modification, protected status, and removal. Whether that policy directly governs this 2016 third-party archive's intended internal research use is **not established here**; it is a material unresolved platform-rights and lifecycle issue, not a blanket legal conclusion.
- The [X Developer Agreement](https://docs.x.com/developer-terms/agreement) requires approved use for X API/content analysis and expressly bars training a foundation or frontier model from X content. This phase proposes no training, but a future conventional classifier would still require a documented, appropriate usage basis.
- Removing SQL account columns would not erase @mentions, phone numbers, names, addresses, coordinates, or other identifiers inside post text. Historical posts may have been deleted or made private since 2016. A regex-only deidentification pass cannot establish current visibility or lawful retention. A human privacy review and takedown/update process would be needed.

**Conclusion:** privacy-minimized text-only research use cannot presently be verified as permitted and operationally compliant. The source remains disabled in `ml/configs/sources.json`. Do not infer that CC BY on the repository removes user-content, platform, or privacy obligations.

## Exact clearance path

1. Obtain a written rights determination or permission covering internal full-text research use, redistribution limits, and any later model-training scope, including the relationship between the Mendeley deposit and current X terms.
2. Obtain a source export or authorized method yielding only bounded `tweet_ID`, text, and `complaint`/`unknown` label; exclude users, handles, mentions tables, profile data, coordinates, and unnecessary dates. If the only source is the full SQL archive, approve a controlled temporary extraction protocol before acquisition.
3. Define how deleted, protected, and modified posts are checked and removed, and how account-owner requests are honored without retaining unnecessary account data.
4. Approve an access-controlled, text-level privacy review before any derived text is shared or used for training. Preserve source attribution and the original binary class as `complaint_label`; leave NagrikOS category, department, and urgency null.

Until those decisions are documented, the source contributes **0 collected rows, 0 usable real complaints, and 0 independently usable labels** to the Phase 2 readiness matrix.

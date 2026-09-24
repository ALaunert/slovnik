# Serbian resource register

Research collected: **2026-09-24**. This is a selection and integration proposal, not an
implemented importer or a claim that Slovnik contains these resources. The current product
has three seed words and no bulk import or audio capability; see [product state](../product-state.md).

The practical starting set is **srLex 1.3 for form candidates and initial frequency evidence,
CLASSLA-web.sr 2.0 for contemporary usage analysis, Tatoeba for individually reviewed example
pairs, and UD Serbian SET for annotation checks**. None supplies a complete Serbian curriculum,
reliable Russian translations for every sense, or publication-ready stress information.

## How to read the register

Sizes retain the publisher's unit: words, tokens, forms, entries, sentences and compressed
bytes are not interchangeable. A resource's version is distinct from its crawl year. Numbers
below are metadata observations, not counts independently reproduced from downloaded corpora.
No bulk corpus or copyrighted dictionary was downloaded for this audit.

“Conditional” commercial reuse means an identified license permits commerce but imposes
requirements, or an additional rights/access question remains. “Unknown” is an unresolved
permission, never an implied license. Quality assessments marked **inference** are recommendations
for Slovnik, not measured accuracy or endorsements by the resource owner.

Keep three rights layers separate:

| Layer | Evidence to retain | Consequence for Slovnik |
| --- | --- | --- |
| Repository metadata | Catalog record, persistent identifier, retrieval date | A reusable description of a corpus does not license the corpus payload. |
| Released data and annotations | Exact release, file, license/version, checksum and attribution | License applies to the rights the provider can grant; models and code can have different licenses. |
| Original text, translation and recording | Original URL/author, sentence ID, speaker/audio ID and item-specific terms | A corpus license is not proof that every source author or performer cleared every intended redistribution. |

For example, CC0 expressly covers commercial purposes but limits its waiver to the affirmer's
rights and disclaims clearing other people's rights. Therefore a CC0 corpus label alone is
insufficient evidence for a blanket sentence republication policy. This is a concrete issue
for web material, not a reason to mislabel CC0 as noncommercial. [CC0 1.0 legal text](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en)

## Web corpora: choose versions deliberately

| Resource | Contents and size | Exact access/format | Declared license; commercial status | Proposed decision |
| --- | --- | --- | --- | --- |
| **CLASSLA-web.sr 2.0**; collection issued 2026-01-27, crawl 2024 | Serbian web text, approximately **3.71 billion words** | [CLARIN.SI 11356/2079](https://www.clarin.si/repository/xmlui/handle/11356/2079): `CLASSLA-web.sr.2.0.jsonl.gz` **9.66 GB**; `.anno.jsonl.gz` **50.08 GB**; `.vert.tar.gz` **32.94 GB** | **CC0 1.0 Universal**; commercial use permitted for covered rights; original sentence rights require review | **Shortlist** for corpus analysis; sentence publication needs source clearance |
| **CLASSLA-web.sr 1.0**; issued 2024-03-26, crawl 2021–2022 | **2,342,626,265 words**, **2,765,201,316 tokens**, **5,256,087 texts** | [CLARIN.SI 11356/1931](https://www.clarin.si/repository/xmlui/handle/11356/1931): `CLASSLA-web.sr.1.0.vert.gz`, **21.58 GB**, registry and URL list | **CC0 1.0 Universal**; same covered-rights distinction | **Secondary** temporal comparison; not the preferred first ingest |
| **srWaC 1.1**; issued 2016-05-12, crawl 2014 | **554,627,647 tokens**, **25,636,542 sentences**, **1,353,238 texts** | [CLARIN.SI 11356/1063](https://www.clarin.si/repository/xmlui/handle/11356/1063): six `srWaC1.1.0[1–6].xml.gz` files; XML/vertical, about **3.6 GB** total as listed | **CC BY-SA 4.0 International**; conditional: attribution/share-alike and source rights | **Secondary** legacy comparison, not default contemporary frequency source |

The annotated JSONL adds CoNLL-U to document text/metadata. The **files** section declares the
license; compressed URL lists are also available. [2.0 release record](https://www.clarin.si/repository/xmlui/handle/11356/2079)

The official methodology documents cleaning, language identification, duplicate removal and
automatic annotation. Version 2.0 adds topic labels alongside genre, offers Latin/Cyrillic
script metadata and expands inspection of frequent domains in response to generated and
low-quality web material. About 20% overlap is reported across releases; do not infer the
same exact percentage for every Serbian subset. Queries are available through the official
[CLARIN.SI concordancer](https://www.clarin.si/ske/), linked from the
[CLASSLA project page](https://clarinsi.github.io/classla-web/).

**Quality inference:** this makes 2.0 the strongest candidate for current collocations,
register evidence and domain-aware frequency ranking, but automatic labels are not editorial
truth. News, advertising and duplicate hosts can dominate counts. A common word may still be
pedagogically inappropriate; a rare inflection may still be essential. Retain per-domain
dispersion and register information instead of sorting lessons by raw counts.

The 1.0 release explicitly describes its additional cleaning and genre annotation over
MaCoCu-sr 1.0; it is not an independent sample of that crawl. Its notice-and-takedown wording
also makes source provenance operationally important. [1.0 release record](https://www.clarin.si/repository/xmlui/handle/11356/1931)

**srWaC version trap:** the downloadable record audited here is **1.1**. ReLDI describes
automatic diacritic restoration, lemmatization and morphology; hosted **1.2** variants have
different processing and counts. The provider's Sketch Engine inventory lists a Hunpos
variant at approximately **477.7 million words**. Do not relabel the 1.1 token count as a 1.2
word count or infer download rights from a paid concordancer subscription.
[ReLDI description](https://reldi.rs/blog/serbian-web-corpus/),
[Sketch Engine inventory](https://www.sketchengine.eu/corpora-and-languages/serbian-text-corpora/)

The [CLARIN.SI internet-corpus agreement](https://www.clarin.si/info/wp-content/uploads/2016/01/CLARIN.SI-WAC-2016-01.pdf)
is a separate document. Do not apply it indiscriminately to every CLARIN resource: record the
actual agreement encountered for the selected download/service. The named release records
above currently identify CC0 or CC BY-SA. A portal's access conditions and a dataset's license
are separate evidence fields.

## Lexicons, frequency evidence and dictionaries

### srLex 1.3 — first morphology candidate

The release contains **169,328 entries and 6,905,941 items**, dated 2019-03-31. Its
`srLex_v1.3.gz` is a **54.16 MB** compressed tab-separated lexicon. Columns represent wordform,
lemma, MSD, expanded MSD features, UPOS, UD morphology, frequency and frequency per million;
frequencies come from **srWaC 1.2**. It uses MULTEXT-East V6 and UD v2 conventions. License:
**CC BY-SA 4.0 International**. Access:
[CLARIN.SI 11356/1233](https://www.clarin.si/repository/xmlui/handle/11356/1233).

**Commercial status: conditional.** Attribution, license link, indicated changes and share-alike
for shared adaptations need an explicit delivery design; a permissive application-code
license does not erase obligations on derived data. [CC BY-SA 4.0 deed](https://creativecommons.org/licenses/by-sa/4.0/)

**Quality/integration inference:** use it to propose `Form` records and detect implausible
inflections, while retaining alternative analyses of homographs. Aggregate frequency by
lemma and part of speech carefully; individual rows are analyses, not independent vocabulary
items. It supplies no documented sense inventory, Russian gloss or stress field. An inflection
lexicon should not decide which Russian cue distinguishes a sense. Older srLex 1.1 used
**GNU GPL v3**, so pin 1.3 rather than generalizing its license backward.
[srLex 1.1 record](https://www.clarin.si/repository/xmlui/handle/11356/1066)

### Wiktionary through Kaikki/Wiktextract — candidate enrichment

| Dataset | Audited size/version | Format and access | License and commercial status |
| --- | --- | --- | --- |
| Russian Wiktionary, Serbian entries | Processed view: **14,491 distinct forms**, **15.8 MB**, dump **2026-09-01** | [Serbian view](https://kaikki.org/ruwiktionary/%D0%A1%D0%B5%D1%80%D0%B1%D1%81%D0%BA%D0%B8%D0%B9/index.html); JSONL. Preferred [raw export](https://kaikki.org/ruwiktionary/rawdata.html) contains all languages with Russian glosses; **292.7 MB gzip**, extraction 2026-09-22 | Standard Wikimedia text route **CC BY-SA 4.0**; conditional on attribution, adaptation requirements and entry/source exceptions |
| English Wiktionary, Serbo-Croatian entries | Processed view: **66,844 distinct forms**, **363.8 MB**, dump **2026-09-02**, extraction 2026-09-20 | [Serbo-Croatian view](https://kaikki.org/dictionary/Serbo-Croatian/index.html); JSONL; use linked [raw exports](https://kaikki.org/dictionary/rawdata.html) for a future importer | Same text-license route; media and quoted examples require separate checks |

Both processed views are marked **deprecated**. The figures describe browsing snapshots,
not guaranteed counts in the newer raw export. Do not silently combine snapshots. The
[Wikimedia terms, section 7](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content)
permit commercial reuse under the applicable license and explain attribution through article
links/history; imported text and non-text media can carry additional conditions.

Evidence: Wiktextract supports senses, forms, qualifiers and pronunciation fields where the
source edition provides them, and warns that coverage differs between editions.
[Extractor documentation](https://github.com/tatuylonen/wiktextract)
**Inference:** useful for Russian gloss candidates and sense discovery, with substantial
review required. The English macro-language bucket must be filtered for Serbian usage;
Croatian/Bosnian/Serbian alternatives and Ekavian/Ijekavian variants must remain labeled.
Pronunciation strings or accent marks require linguistic interpretation, not a blind conversion
into Slovnik's single stressed-syllable field. Keep source page, revision/dump and sense anchor.
**Decision: shortlist as enrichment after the morphology and attribution workflow.**

### Published dictionaries — reference use, not a bulk import

Matica srpska's official listing for **Rečnik srpskoga jezika**, **2011**, identifies
**1,561 pages**, ISBN **978-86-7946-004-2**, as a printed edition. No machine-readable
format, API or open reuse license was found on that listing. Entry count was not verified.
[Publisher record](https://www.maticasrpska.org.rs/%D1%80%D0%B5%D1%87%D0%BD%D0%B8%D0%BA-%D1%81%D1%80%D0%BF%D1%81%D0%BA%D0%BE%D0%B3%D0%B0-%D1%98%D0%B5%D0%B7%D0%B8%D0%BA%D0%B0/)

**Commercial redistribution: unknown; owner permission required.** Editorial recommendation:
use a lawfully acquired copy to resolve normative questions; draft original learning
explanations. Buying the book is not an import license. Do not ingest unofficial PDF/OCR
copies. A negotiated license would need explicit coverage of definitions, examples, stress
notation, adaptations, translations and digital distribution. **Decision: reference shortlist;
reject unlicensed scraping.**

### Standalone frequency lists — require identifiable provenance

The initial usable frequency source is **srLex 1.3's published frequency columns**; the next
is a reproducible aggregate over an approved CLASSLA release. Neither is a CEFR list. The
[Leipzig Serbian download route](https://www.wortschatz.uni-leipzig.de/en/download/Serbian)
is a possible comparison source, but access failed during this audit and the alternative
site presented a bot challenge. A current Serbian file, size, exact license version and
format were **not verified**. General indexed wording about CC BY is insufficient to approve
a particular payload. **Commercial status: unknown; decision: defer until its release and
terms can be inspected.** Do not substitute an unattributed “top 5,000 Serbian words” list.

## Example sentences and translation pairs

### Tatoeba — best small reviewed-pair candidate

Contents: community sentences, translation links, contributor metadata, reviews and optional
audio. Serbian sentence and direct Serbian–Russian pair counts were **not verified**; the
available inventory must be counted from a dated export before planning coverage.
[Downloads](https://tatoeba.org/en/downloads) provide tab-separated text in compressed archives,
including detailed sentences, links and reviews; exports refresh weekly. Use language codes
`srp` and `rus`. The official [API entry point](https://api.tatoeba.org/) links
[OpenAPI documentation](https://api.tatoeba.org/openapi); an importer should pin the documented
API version or use dated bulk exports, not scrape search pages.

Text's default license is [**CC BY 2.0 France**](https://creativecommons.org/licenses/by/2.0/fr/); a separately identified subset uses
**CC0 1.0**. Do not assume Serbian has meaningful CC0 coverage. **Commercial reuse:
conditional** on the selected sentence's license and attribution. Retain each sentence's
author, ID, URL and license for both sides of a pair. The terms explicitly treat translations
as derivative works and do not guarantee every contribution's rights were systematically
checked. [Tatoeba terms, section 6](https://tatoeba.org/en/terms_of_use)

**Quality inference:** community review is useful evidence, not a guarantee of naturalness,
translation equivalence or CEFR level. Require native Serbian and Russian review of meaning,
register, case government and context. A path Serbian→English→Russian through translation
links is not evidence of a directly checked Serbian–Russian pair. Keep directness separately
and reject ambiguous pedagogical cues. **Decision: shortlist for a small, reviewed example bank.**

### MaCoCu-sr-en 1.0 — optional corroboration

The 2023-04-26 release has **2,068,916 entries**, **95,863,993 words** and **312,335 texts**
across the Serbian–English corpus; those words are not a Serbian-only count. It offers
sentence-level **TXT/TMX gzip**, separate Cyrillic/Latin files, and document TXT. For example,
Latin sentence TXT is **499.71 MB**. Alignment quality and source-URL metadata support filtering.
[CLARIN.SI 11356/1819](https://www.clarin.si/repository/xmlui/handle/11356/1819)

License **CC0 1.0 Universal**; commercial covered-rights reuse permitted, source sentence
rights unresolved for blanket republication. **Inference:** useful to inspect translation
contexts, but English pivoting can erase the distinctions Russian learners need and automatic
alignment adds errors. **Decision: secondary research resource**, behind direct reviewed
Serbian–Russian examples; no automatic translation-to-lesson pipeline.

## Syntactic resources and audio

### CLASSLA-Stanza and upstream Stanza — annotation tools

**Access:** the official [CLASSLA installation and API documentation](https://github.com/clarinsi/classla)
specifies `pip install classla`, followed by `classla.download('sr')` and
`classla.Pipeline('sr', processors='tokenize,pos,lemma,depparse')`. Output can be serialized as
CoNLL-U with `doc.to_conll()`. These are prospective usage references; nothing was installed
or executed in this audit. Serbian support includes sentence/token segmentation, POS and
morphological features, lemmas, UD dependencies and optional named entities. Standard,
nonstandard and web modes are documented; nonstandard mode reuses the standard dependency
parser. The README demonstrates **Latin-script Serbian** but does not document automatic
Cyrillic transliteration or full orthographic normalization.

Therefore native Cyrillic behavior for the selected package/model is **unverified**, not
assumed from the corpus's script metadata. Proposed integration: preserve original text,
document any Cyrillic→Latin analysis copy, retain offset alignment and test both scripts
before adopting a processor. Nonstandard model training explicitly includes diacritic-stripped
examples; robustness to missing diacritics is not permission to silently “correct” learner
answers or source sentences. [Serbian nonstandard POS model 2.1](https://www.clarin.si/repository/xmlui/handle/11356/1825)

| Component | License, size and commercial decision |
| --- | --- |
| CLASSLA code | [Apache License 2.0](https://github.com/clarinsi/classla/blob/master/LICENSE); commercial use permitted under its terms. Dependency licenses still need inventory. |
| Serbian standard lemmatizer **2.1**, issued 2023-05-10 | [CLARIN.SI 11356/1830](https://www.clarin.si/repository/xmlui/handle/11356/1830): `baseline_lemma_lemmatizer.zip`, **104.93 MB**, model weights; **CC BY-SA 4.0**, conditional commercial reuse. Publisher reports lemma F1 about **98.02**, not a Slovnik-domain evaluation. |
| Complete selected Serbian model bundle | Total size and complete license inventory **not verified**. The current downloader's selected weights must be mapped to release records; the lemmatizer's terms do not establish every parser/tagger/embedding license. |
| Upstream Stanza | [Official documentation](https://stanfordnlp.github.io/stanza/) specifies **Apache 2.0** code and `pip install stanza`; [available-model inventory](https://stanfordnlp.github.io/stanza/available_models.html) is the access route for pretrained packages. Exact chosen Serbian package size and model/data terms remain **unverified**; commercial model use conditional pending that check. |

**Decision: shortlist CLASSLA for an offline annotation pilot.** Compare predictions against
reviewed examples and UD checks; never publish a predicted lemma, case, aspect or construction
as catalog truth solely because a model returned it. Record package version, processor list,
model checksums, training-resource references and transformation steps. Code, pretrained
weights, training corpora and Slovnik's own input sentences need separate provenance entries.

### UD Serbian SET — annotation and construction checks

The audited UD v2 page reports **4,384 sentences and 97,673 tokens**, news genre, manually
annotated lemmas and dependencies, with some other annotation converted from non-UD schemes.
License **CC BY-SA 4.0 International**, commercial use conditional on its requirements.
[Treebank description](https://universaldependencies.org/treebanks/sr_set/index.html)
Access: [UD_Serbian-SET repository](https://github.com/UniversalDependencies/UD_Serbian-SET),
`sr_set-ud-{train,dev,test}.conllu` in **CoNLL-U**. Pin a release tag/commit when ingesting;
the live page and repository can change independently.

**Inference:** appropriate for validating dependency queries, morphology mappings and candidate
construction extraction, not broad conversational coverage. Preserve original train/dev/test
splits if evaluating a parser. Annotation absence is not grammatical absence: the Serbian UD
documentation does not supply lexical Aspect as a standard language-specific feature and
often uses `expl` for different functions of `se/si`. [Serbian UD guidance](https://universaldependencies.org/sr/index.html)
Audit actual feature coverage before implementing aspect-pair or reflexive-construction
extraction. **Decision: shortlist for quality assurance; limited example source after review.**

### Audio choices

| Resource | Contents, size and exact access | License/commercial status | Quality and integration decision |
| --- | --- | --- | --- |
| **Tatoeba audio** | Per-sentence recordings; Serbian usable count **unknown**. [Audio export](https://downloads.tatoeba.org/exports/sentences_with_audio.tar.bz2), tab-separated IDs/author/license/attribution URL; download route `https://tatoeba.org/audio/download/{audio_id}` | **Per recording**; no single version. An empty license prohibits offsite reuse. NC recordings unsuitable for the commercial lane; ND/adaptation questions need separate review | **Conditional shortlist** after counting licensed Serbian clips and listening review; text permission never substitutes for recording permission |
| **ParlaSpeech-RS 1.0**, issued 2024-02-08 | **290,778 entries**, **896 hours**; parliamentary speech with transcripts and word offsets. [CLARIN.SI 11356/1834](https://www.clarin.si/repository/xmlui/handle/11356/1834): JSONL gzip **102.73 MB**; two FLAC tar archives **36.41/26.62 GB** | **CC BY-SA 4.0 International**; commercial reuse conditional; preserve provenance and assess intended speaker use | Evidence: aligned real parliamentary recordings. **Inference:** useful for advanced listening/ASR evaluation, poor default for everyday A1 pronunciation; **defer** |
| **Common Voice Scripted Speech 27.0, Serbian** | Official [dataset inventory](https://commonvoice.mozilla.org/nan-tw/datasets) lists **246.90 MB**, **MP3**, locale `sr`; validated hours/clip count and exact Serbian download record **not verified** | Inventory says **CC0 1.0**. Commercial covered-rights use permitted, but current access/redistribution conditions **unresolved** for this exact release | **Needs owner/access review** before a content decision; possible speech benchmark, not approved pronunciation asset source |

Tatoeba's [download documentation](https://tatoeba.org/en/downloads) explicitly separates audio
rights and supports multiple voices per sentence. For Common Voice, current Mozilla Data
Collective cards for other languages additionally prohibit rehosting and speaker identification;
that evidence is a reason to inspect the **Serbian** card and download agreement, not to assume
either unrestricted redistribution or identical terms without checking.
[Example official card documenting the access issue](https://datacollective.mozillafoundation.org/datasets/cmn2avimf019no107bb37vfx8)

## Recommended adoption boundaries

| Lane | Accept initially | Do not infer |
| --- | --- | --- |
| Internal evidence | Versioned lemma/form frequencies; human-inspected concordance evidence; source IDs | That a rank is a CEFR level or that every attested construction is suitable for beginners |
| Published catalog | Reviewed sense/form mapping, original Russian explanations, approved attribution packages | That share-alike data can be silently relabeled proprietary |
| Published examples | Original commissioned examples or individually reviewed, licensed source sentences/translations | That splitting text into sentences clears copyright or that an AI paraphrase automatically does |
| Audio | Commissioned recordings with explicit reuse rights, then individually approved open clips | That a text license covers a recording or that a speech-recognition corpus is pronunciation teaching material |

For an initial content experiment, select a bounded list of frequent learner-relevant lemmas,
sample ambiguous forms and identify missing senses. Evaluate acceptance rate and reviewer time
before importing millions of analyses. Prefer the smallest source set that answers the question:
the lexicon can supply form candidates before any multi-gigabyte corpus download is justified.

Require a source manifest with persistent identifier, release/crawl date, access date, file
name/checksum, license URL and saved license evidence. Derived frequencies should record
normalization, inclusion filters, corpus denominator and script handling. A frequency table
is a different output from a sentence library; do not assume a method for publishing one also
authorizes the other. For web-derived frequencies intended for redistribution, document the
rights assessment rather than claiming all statistics are automatically exempt.

Keep low-confidence analyses and conflicting dictionaries visible to reviewers. Do not overwrite
approved catalog facts merely because a newer corpus changed rank. Distinguish Serbian-standard
judgment, source attestation, script conversion, morphology prediction and translation review.
These are separate claims with separate evidence. A pipeline can propose candidates; publication
needs linguistic review and a recorded rights decision.

## Verification and remaining work

Verified through official release records, project documentation and linked license texts:
CLASSLA 1.0/2.0, srWaC 1.1, srLex 1.3, MaCoCu-sr-en, UD Serbian SET, Tatoeba's text/audio
distinction, Wiktionary extraction snapshots and ParlaSpeech. No corpus-wide accuracy audit,
import, redistribution, owner contact or acquisition was performed. Unknown sizes and access
questions above are explicit research gaps, not implementation blockers for original content.

Before choosing production sources: count licensed direct Serbian–Russian Tatoeba pairs;
review a representative Serbian sample; confirm any Common Voice access agreement; resolve
Leipzig's exact release/license if still useful; and decide how attribution/share-alike artifacts
will be delivered. Every resource retained in a future importer needs release-specific review
again, because this register is a dated research snapshot.

# Evidence for Slovnik's learning design

Research date: 2026-09-24. Status: research and proposed product policy; no runtime
changes or demonstrated learning outcomes are implied. The implemented baseline is
documented in [product-state.md](../product-state.md).

## Decision and scope

Build a Serbian learning assistant around meaningful tasks, understandable input,
explicitly taught forms when useful, retrieval across time, and evidence of use in
new contexts. Keep vocabulary review as one component. Do not equate a remembered
translation, a completed lesson, or a scheduler's prediction with communicative
competence.

This is a focused evidence review for product decisions, **not a systematic review**
of all second-language acquisition research. Searches covered official Council of
Europe material, journal publishers, author/university repositories, ACL Anthology,
and educational-data-mining publications. Search terms combined spacing, retrieval,
incidental vocabulary, receptive/productive knowledge, feedback, formulaic language,
interleaving, and learner modelling with review/meta-analysis. Primary publications
and the original reports of research syntheses were preferred over commercial
learning advice. No Serbian-for-Russian-speakers intervention study was established
by this search; absence here does not establish absence in the literature.

Evidence labels below distinguish **strong**, meaning convergent or substantial
experimental synthesis for the stated outcome; **moderate**, meaning narrower,
heterogeneous, or indirect support; **limited**, meaning a useful hypothesis with
little direct evidence for this product; and **framework**, meaning an organizing
proposal or standard rather than a causal effectiveness result. These are editorial
confidence judgements, not a formal GRADE assessment. Access limitations are recorded
in the bibliography. Recommendations are separately labelled as design proposals.

## Evidence-to-decision matrix

| Question | Observed evidence | Confidence and boundary | Proposed decision |
| --- | --- | --- | --- |
| What should progress mean? | CEFR describes communicative activities, strategies, and competences, including reception, production, interaction, and mediation [R1]. | Framework; authoritative for descriptors, not a Serbian curriculum or proof of an app's effectiveness. | Map a small curriculum to practical outcomes and assess skills separately. |
| Does retrieval help? | Large classroom synthesis finds benefits from quizzing relative to comparison conditions [R2]; broad review also supports practice testing [R3]. | Strong for assessed retention; transfer and optimal implementation vary. | Require an attempted answer before feedback, with low stakes and useful correction. |
| Does spacing help L2 learning? | L2 meta-analysis supports distributed practice; delayed tests favour longer over shorter spacing on average [R4]. | Strong general direction; insufficient to prescribe one interval formula. | Space successful retrievals and reintroduce difficult targets with support. |
| Is harder always better? | Desirable difficulty distinguishes temporary performance from durable learning and requires sufficient prior knowledge [R5]. | Framework supported by experiments, not a universal difficulty percentage. | Increase difficulty by reducing help or changing context; respond to repeated failure. |
| Should everything be mixed? | Interleaving meta-analysis finds important material/similarity moderators, including an advantage for blocking in word studies [R6]. | Mixed; many studies concern category induction, not language conversation. | Use purposeful contrasts after initial teaching; test their benefit locally. |
| Is comprehensible input enough? | Input theory motivates meaning-focused exposure [R7]; extensive-reading synthesis supports reading outcomes [R8]; incidental vocabulary gains are real but incomplete [R9]. | Moderate to strong for particular input outcomes; input-only sufficiency is not established here. | Pair short understandable texts/dialogues with intentional practice and later use. |
| Can recognition stand for production? | Vocabulary experiments distinguish dimensions of knowledge; task comparisons change when time is controlled differently [R10]. | Moderate, specific study/population. | Store evidence direction, modality, response format, and assistance. |
| Should phrases be taught? | Formulaic-language review supports attending to and learning multiword sequences, with unresolved instructional questions [R11]. | Moderate; spontaneous-use evidence is less secure than trained-item gains. | Teach useful chunks plus variable slots, then test recombination. |
| Do grammar explanations and correction help? | Focused instruction synthesis supports targeted gains [R12]; oral-feedback meta-analysis supports durable effects [R13]. | Moderate for the app: older, heterogeneous classroom studies; outcome measurement matters. | Use brief explanations, meaningful examples, repair, and delayed reuse. |
| Do drills transfer? | Retrieval-transfer synthesis finds average benefits with substantial moderators [R14]. | Moderate; task similarity and initial retrieval success influence transfer. | Reserve unfamiliar prompts and communicative tasks for assessment. |
| Does a sophisticated learner model improve learning? | HLR predicts recall and reports engagement gains [R15]; knowledge-tracing comparison finds model performance depends on data/features [R16]. | Moderate for prediction; limited for causal learning benefit in Slovnik. | Begin with inspectable rules and evaluate prediction separately from policy impact. |
| How should activities be balanced? | Four Strands proposes input, output, language-focused learning, and fluency practice [R17]. | Framework; equal quarters are a pedagogical proposal, not an experimentally fixed optimum. | Audit coverage across these opportunities over a week, without rigid daily quotas. |

## From findings to a learning method

### Outcomes before lists of words

The CEFR Companion Volume's action-oriented discussion treats learners as social
agents accomplishing tasks and recommends alignment between goals, teaching, and
assessment. It also explicitly avoids prescribing one teaching method [R1]. A CEFR
label on a word therefore cannot establish the learner's level or complete coverage
of that level.

**Design proposal:** choose outcomes such as obtaining an item in a shop,
understanding a short appointment message, or asking for clarification. For each,
define situation, expected response, allowable support, target language resources,
and a scoring rubric. A scenario can involve both reading and speaking, but each
must have its own evidence. A text-only pilot should describe its scope honestly;
it cannot demonstrate listening or pronunciation competence. Scenario labels and
level mappings need Serbian-teacher review, not automatic assignment from vocabulary
frequency or an LLM's confidence.

### Understandable input with purposeful attention

Krashen's original input hypothesis is a theoretical account, including claims about
the sufficiency of comprehensible input and the emergence of speaking [R7]. It is
useful background, not a product validation. More directly, Nakanishi's meta-analysis
of 34 studies supports extensive reading for reading proficiency [R8]. Webb,
Uchihara, and Yanagisawa's 24-study synthesis finds incidental vocabulary learning,
while the mean proportion learned remains a minority of exposed target words;
learner, material, activity, and measurement differences matter [R9].

**Design proposal:** introduce each practical situation through a short, coherent
text or dialogue. Give a meaning question before inspecting individual forms. Make
translation and explanations available on demand, record their use, and permit a
second pass. Select texts using both lexical familiarity and task complexity. An
unknown-word count alone misses sentence structure, ambiguity, world knowledge,
and whether a familiar word has an unfamiliar sense. Do not hard-code a universal
"95% known words" rule or operationalize *i+1* as a numerical mastery increment
without local validation. Deliberately recycle a few useful targets in fresh
contexts; do not turn every encounter into a vocabulary quiz.

### Retrieval and spacing without magical intervals

Yang and colleagues synthesized 222 independent classroom studies involving 48,478
students [R2]. Dunlosky and colleagues rate practice testing and distributed practice
highly across multiple settings [R3]. For L2 specifically, Kim and Webb synthesized
48 experiments with 3,411 participants: spacing helped, but equal and expanding
spacing did not differ statistically in their comparison [R4]. None of this
validates Slovnik's exact rating multipliers or three-success learned status.

**Design proposal:** preserve cue-before-reveal recall, but distinguish an observable
answer from a self-report. Separate first attempt, hint use, reveal, corrective
retry, and delayed retrieval. Correctly copying a just-revealed answer is a useful
learning event with weak diagnostic value. After failure, show the relevant answer
and explanation, provide a supported retry, and later test without that support.
Avoid endless immediate repetition. A returning learner should get a manageable
review budget and fresh evidence, not a punitive overdue backlog.

Treat review timing as a policy to compare against a simple baseline. Report the
learning target and retention horizon for any fitted scheduler. Memory for a
translation pair and ability to select a case ending in conversation have different
assessment demands, even when both involve the same word.

### Difficulty and interleaving must serve the target

Bjork and Bjork explain why smooth practice performance can misrepresent enduring
learning, while difficulties beyond a learner's capacity cease to be desirable [R5].
Brunmair and Richter's synthesis covers 59 studies and finds material-dependent
effects; word studies favoured blocking on average [R6]. This prevents treating
random switching as a universal learning principle.

**Design proposal:** initially demonstrate a new pattern clearly, then contrast it
with one already understood when that contrast resolves a real choice. Mix familiar
and recently introduced content across sessions. Distinguish interleaving
categories from spacing the same target and from simply varying screen formats.
For each failure, ask whether the problem is missing knowledge, an ambiguous prompt,
an input-method issue, or excessive combined demand. Lower one demand at a time:
show the script the learner reads best, restore a cue, simplify the sentence, or
return to an example. Do not add time pressure until speed itself is the target.

### Vocabulary is multidimensional; chunks need flexible use

Webb's two experiments with Japanese learners of English measured receptive and
productive aspects of several dimensions of word knowledge. Reading performed
better under equal time, while writing performed better when allowed its longer
completion time [R10]. It would misrepresent that evidence to claim sentence
production always wins. Boers and Lindstromberg review noticing, lookup, and
memorization approaches to formulaic sequences and identify remaining research
needs [R11].

**Design proposal:** distinguish a lexical sense, its written/spoken forms, typical
combinations, and the ability to use it in an appropriate situation. Link a useful
phrase to a communicative function and any variable slots. Practice the whole
expression, then require a suitable substitution or response to a changed situation.
Maintain recognition and controlled-production evidence separately; introduce
independent-use checks before claiming broader command. Memorizing a phrase should
not silently award mastery of every grammatical construction inside it. Conversely,
one spelling error should not automatically erase evidence of understanding.

### Teach grammar in context, and make correction diagnostic

Norris and Ortega's synthesis found sizeable targeted instructional gains and an
advantage for explicit instruction, while warning that outcome measures and weak
construct replication limit generalization [R12]. Lyster and Saito's 15-classroom-study
meta-analysis found durable corrective-feedback effects and larger effects for
prompts than recasts [R13]. These results concern particular learning conditions;
they do not prove that every error needs interruption or that automated feedback
matches an experienced teacher.

**Design proposal:** give a compact rule only when it helps interpret or produce the
current message. Follow it with a meaning-bearing contrast, a constrained attempt,
specific correction, and a later unfamiliar example. Mark the error's location and
type without overwhelming the learner with a full grammar lecture. Allow plausible
alternative Serbian answers. If an evaluator cannot confidently distinguish valid
variation from error, record the answer as unresolved rather than treating model
uncertainty as learner failure. Teacher review must validate explanations and answer
rubrics before publication. Open-ended AI feedback needs a separate agreement and
error audit; fluent prose is not evidence of grammatical correctness.

## Exercise design and the evidence each format can support

The following is a proposed assessment contract, not a ranked list of universally
effective exercise types. Pan and Rickard's transfer synthesis found an average
benefit of retrieval but substantial dependence on conditions, including response
congruency and elaborated retrieval [R14]. Practice should therefore resemble the
desired use while assessment also checks whether learning survives changed cues.

| Format | Useful purpose | Evidence it can contribute | Main limitation / required follow-up |
| --- | --- | --- | --- |
| Serbian cue, meaning choice | Initial comprehension and distinguishing senses | Cued recognition with recorded distractors | Guessing and elimination; follow with meaning recall or a new context. |
| Russian situation, Serbian answer | Controlled lexical or phrase retrieval | Productive response under a specific L1 cue | Translation ambiguity; accepted variants and a clear intended situation are essential. |
| Contextual gap completion | Choosing a form or lexical combination | Targeted form selection with visible context | Remaining sentence may reveal answer; follow with changed wording. |
| Sentence assembly | Supported sequencing after explanation | Ordering from supplied components | Supplies vocabulary/forms; do not label it independent production. |
| Read/listen, then act on meaning | Integrating a message | Comprehension of tested information | A written transcript changes listening demand; log its availability. |
| Contrast and explain a choice | Diagnosing a misconception | Discrimination and explicit explanation | Metalinguistic explanation is not spontaneous use. |
| Short message or spoken response | Applying language to a purpose | Task success, intelligibility, appropriateness, targeted accuracy | Requires reliable rubric/scoring; do not penalize harmless variants. |
| Repeated familiar task with changed details | Developing fluent access | Successful use with reduced assistance and, where appropriate, time | Speed alone rewards guessing and penalizes device/accessibility differences. |
| Self-rated recall after reveal | Low-friction review | Learner judgement and exposure | Calibration unknown; cannot substitute for scored performance. |

**Design proposal:** use distractors representing plausible distinctions, not traps.
Keep assessment examples out of practice rotation. Avoid measuring an exercise by
its completion rate alone: easier cues can raise completion while reducing what
can be inferred from a correct answer. Limit a session's switches when navigation
cost overwhelms useful practice. A balanced week should expose gaps in input,
output, focused study, and fluent use; Nation's Four Strands is useful for that
audit, while its equal-time recommendation remains a framework choice [R17].

## Adaptation, learner modelling, and mastery

Settles and Meeder's half-life regression study reports improved recall prediction
and an operational engagement gain; it does not establish a gain in communicative
proficiency [R15]. Gervet and colleagues compare knowledge-tracing approaches on
nine datasets and show that simpler models can be competitive, with calibration
important for downstream use [R16]. Predicting the next answer and choosing the
best next learning activity are separate problems.

**Design proposal:** start with an inspectable selector that obeys prerequisites,
limits new material, revisits memory risk, and samples under-observed skills. Keep
curriculum readiness, estimated retention, and confidence in the evidence distinct.
A learner who never attempted a skill has unknown ability, not proven inability.
Success with hints should affect learning history without being treated as equal
to independent success. Evidence should retain target/version, prompt family,
response modality, assistance, first-attempt result, error category, delay, and
scoring provenance. Only valid, attributable evidence should update progress.

Use mastery labels as reversible summaries with an evidence trail. For example,
"demonstrated in controlled practice" and "demonstrated in a new situation" are
more interpretable than one percentage. Thresholds, minimum occasions, and acceptable
uncertainty require pilot calibration; no source above establishes a universal
80%, 90%, or three-correct threshold. Learners must be able to revise their goal,
skip known material through a check, and understand why a task was suggested.

## Transfer limits for Russian-speaking Serbian learners

Most cited interventions examine other language pairs or general educational
material. Rađenović's Serbian aspect study [R18] uses a post-course contextual
choice task with mixed-L1 beginners. It shows uneven performance across items;
without a causal comparison or delayed spontaneous-production test, it cannot
establish the best teaching sequence.

Shared Slavic vocabulary and familiar grammatical concepts might reduce
some beginner demands, but apparent familiarity can also hide sense or usage
differences. Treat both as hypotheses to test, not as a reason to omit diagnostics.
The roadmap should investigate transfer patterns with Serbian instructors and
Russian-speaking learners, using documented errors rather than invented lists.

Script knowledge, grammatical terminology, prior Serbian exposure, and real-life
use in Serbia can differ greatly within the audience. A Cyrillic-looking word may
be recognized without the learner being able to pronounce or use it. Latin-script
typing speed may reflect keyboard habits. Keep script, meaning, spelling,
pronunciation, and morphosyntax distinguishable in assessment. Proposed Serbian
examples require linguistic review before becoming teaching material.

Laboratory vocabulary tests often have brief interventions, narrow targets, and
short follow-ups. Classroom syntheses contain differing controls and measures;
their average effect is not a forecast for this app. Even a sound paper can support
only a narrow design inference. Older sources here establish foundational
distinctions; they are not a claim that the complete 2026 literature was reviewed.
Revisit the search when choosing a specific intervention or public efficacy claim.

## Evaluation proposal before and after implementation

### 1. Offline content and scoring review

Create a frozen, versioned evaluation set before tuning content generation or answer
checking. Include ordinary answers, valid alternatives, misspellings, partial
responses, wrong senses, wrong inflections, both scripts, and ambiguous prompts.
Recruit qualified Serbian reviewers and document their remit; use two independent
ratings on a meaningful overlapping sample, resolve disagreements, and retain the
original ratings. Report false acceptance, false rejection, unresolved cases,
rubric agreement, and examples of severe errors separately. A high aggregate score
must not hide systematic rejection of a legitimate variant.

The set must include unfamiliar contexts, not only the generator's own expected
answers. Split by target and prompt family so cosmetic paraphrases cannot leak
between development and evaluation. Check level appropriateness, naturalness,
single-target focus, answerability, accidental answer leakage, and explanation
accuracy. These checks validate materials and scoring; they do not prove learning.

### 2. Offline selector and model evaluation

Use deterministic synthetic histories to inspect cold start, sparse evidence,
repeated failure, a long absence, uneven skills, exhausted curriculum, and contradictory
observations. Evaluate prerequisite compliance, workload caps, target diversity,
starvation, and reproducibility. These are engineering checks, not efficacy tests.

Once real histories exist, predict future first attempts using chronological splits.
Separately report performance on new learners and unseen targets. Compare with a
constant predictor, item/skill baselines, and the existing scheduling policy. Assess
log loss or Brier score and reliability plots alongside ranking metrics; inspect
calibration by modality, assistance, delay, and learner experience. Do not infer
policy effectiveness from replay accuracy: the old policy determined what was
observed, and unchosen tasks have unknown outcomes. Counterfactual estimates need
appropriate logging and defensible assumptions, not fabricated rewards.

### 3. Human pilot and controlled learning comparison

First run a small usability/content pilot to find confusing prompts, unrealistic
session burden, and rubric failures. Describe it as feasibility work. Then test
one important decision at a time, such as contextual retrieval plus delayed reuse
versus the current vocabulary routine, with comparable targets and planned time.
Randomize learners where feasible; if randomizing targets within learners, account
for interference and shared learning. Stratify or adjust for baseline ability and
prior exposure, and record outside study without assuming it is absent.

Pre-register the primary outcome, retention interval, exclusion rules, attrition
handling, and analysis before seeing outcomes. Candidate endpoints are independent
productive recall after one and four weeks, and blinded scoring of held-out practical
tasks. Those intervals are proposed measurement horizons, not proven optimal
training gaps. Report task accuracy, communicative success, hints needed, practice
minutes, return rate, and review burden separately. Engagement is a secondary
outcome, not a substitute for learning. Report confidence intervals, effect sizes,
missing data, and adverse patterns; determine sample size from a minimally useful
effect and pilot variance, not an arbitrary number of beta users.

Keep a fair baseline available and make assessment accessible. Stop or revise a
pilot when scoring defects or content ambiguity make its results uninterpretable.
A release decision should require reviewed content, usable workload, and credible
delayed learning evidence; public CEFR attainment claims require additional aligned
assessment and validation beyond this pilot.

## Source register

All sources were checked on 2026-09-24. “Abstract” means that bibliographic details
and abstract claims were inspected, not the inaccessible full study. Dates below
refer to the publication, not a search engine's crawl date. No long quotations or
unverified references are used.

| ID | Primary publication / original synthesis | Access and use |
| --- | --- | --- |
| R1 | Council of Europe (2020). *Common European Framework of Reference for Languages: Learning, teaching, assessment – Companion volume*. ISBN 978-92-871-8621-8. [Official PDF](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4). | Full PDF; especially §§2.2, 2.7–2.9 and activity/competence scales. |
| R2 | Yang, C., Luo, L., Vadillo, M. A., Yu, R., & Shanks, D. R. (2021). *Testing (quizzing) boosts classroom learning: A systematic and meta-analytic review*. DOI [10.1037/bul0000309](https://doi.org/10.1037/bul0000309). [Author-university PDF](https://metacog.bnu.edu.cn/pdf/articles/2020/YangLuoVadilloYuShanks2020.pdf). | Full PDF opened; synthesis scope and overall direction. |
| R3 | Dunlosky, J., Rawson, K. A., Marsh, E. J., Nathan, M. J., & Willingham, D. T. (2013). *Improving Students' Learning With Effective Learning Techniques*. DOI [10.1177/1529100612453266](https://doi.org/10.1177/1529100612453266). [APS publication page](https://www.psychologicalscience.org/journals/pspi/1529100612453266/). | Publisher abstract and official summary; general review, not L2-specific. |
| R4 | Kim, S. K., & Webb, S. (2022). *The Effects of Spaced Practice on Second Language Learning: A Meta-Analysis*. *Language Learning*, 72, 269–319. DOI [10.1111/lang.12479](https://doi.org/10.1111/lang.12479). | Publisher abstract and study metadata; schedule comparisons. |
| R5 | Bjork, E. L., & Bjork, R. A. (2011). *Making things hard on yourself, but in a good way: Creating desirable difficulties to enhance learning*. In *Psychology and the Real World*, pp. 56–64. [Author-lab PDF](https://bjorklab.psych.ucla.edu/wp-content/uploads/sites/13/2016/11/Making-Things-Hard-on-Yourself-but-in-a-Good-Way-20111.pdf). | Full chapter; theory/review, including prerequisites for useful difficulty. |
| R6 | Brunmair, M., & Richter, T. (2019). *Similarity matters: A meta-analysis of interleaved learning and its moderators*. *Psychological Bulletin*, 145, 1029–1052. DOI [10.1037/bul0000209](https://doi.org/10.1037/bul0000209). [PubMed record](https://pubmed.ncbi.nlm.nih.gov/31556629/). | Indexed original abstract; publisher/author full-text fetch failed. Do not infer specific Serbian contrasts from this study. |
| R7 | Krashen, S. D. (1982). *Principles and Practice in Second Language Acquisition*. [Author-hosted PDF](https://sdkrashen.com/content/books/principles_and_practice.pdf). | Full PDF; historical input hypothesis, especially chapter II. |
| R8 | Nakanishi, T. (2015; online 2014). *A Meta-Analysis of Extensive Reading Research*. *TESOL Quarterly*, 49, 6–37. DOI [10.1002/tesq.157](https://doi.org/10.1002/tesq.157). | Publisher abstract; reading outcomes, not proof of input-only fluency. |
| R9 | Webb, S., Uchihara, T., & Yanagisawa, A. (2023). *How effective is second language incidental vocabulary learning? A meta-analysis*. *Language Teaching*, 56, 161–180. DOI [10.1017/S0261444822000507](https://doi.org/10.1017/S0261444822000507). | Open-access article inspected; learning proportions and moderators. |
| R10 | Webb, S. (2005). *Receptive and Productive Vocabulary Learning: The Effects of Reading and Writing on Word Knowledge*. *Studies in Second Language Acquisition*, 27, 33–52. DOI [10.1017/S0272263105050023](https://doi.org/10.1017/S0272263105050023). | Publisher abstract; two experiments and time-on-task qualification. |
| R11 | Boers, F., & Lindstromberg, S. (2012). *Experimental and Intervention Studies on Formulaic Sequences in a Second Language*. *Annual Review of Applied Linguistics*, 32, 83–110. DOI [10.1017/S0267190512000050](https://doi.org/10.1017/S0267190512000050). | Publisher abstract and annotated bibliography; no unsupported pooled effect claimed. |
| R12 | Norris, J. M., & Ortega, L. (2000). *Effectiveness of L2 Instruction: A Research Synthesis and Quantitative Meta-analysis*. *Language Learning*, 50, 417–528. DOI [10.1111/0023-8333.00136](https://doi.org/10.1111/0023-8333.00136). | Publisher abstract; original 2000 issue, despite later online metadata. |
| R13 | Lyster, R., & Saito, K. (2010). *Oral Feedback in Classroom SLA: A Meta-Analysis*. *Studies in Second Language Acquisition*, 32, 265–302. DOI [10.1017/S0272263109990520](https://doi.org/10.1017/S0272263109990520). | Publisher abstract; 15 studies, 827 learners; oral classroom feedback. |
| R14 | Pan, S. C., & Rickard, T. C. (2018). *Transfer of test-enhanced learning: Meta-analytic review and synthesis*. *Psychological Bulletin*, 144, 710–756. DOI [10.1037/bul0000151](https://doi.org/10.1037/bul0000151). [Author PDF](https://sc-pan.github.io/pdf/PR_2018.pdf). | Full PDF and indexed abstract; transfer moderators, not a promise of conversation gains. |
| R15 | Settles, B., & Meeder, B. (2016). *A Trainable Spaced Repetition Model for Language Learning*. ACL, pp. 1848–1858. DOI [10.18653/v1/P16-1174](https://doi.org/10.18653/v1/P16-1174). [Official paper](https://aclanthology.org/P16-1174/). | Full paper; prediction and engagement endpoints distinguished. |
| R16 | Gervet, T., Koedinger, K., Schneider, J., & Mitchell, T. (2020). *When is Deep Learning the Best Approach to Knowledge Tracing?* *Journal of Educational Data Mining*, 12(3), 31–54. DOI [10.5281/zenodo.4143614](https://doi.org/10.5281/zenodo.4143614). [Journal article](https://jedm.educationaldatamining.org/index.php/JEDM/article/view/451). | Publisher abstract; model comparison and calibration, not a causal intervention. |
| R17 | Nation, P. (2007). *The Four Strands*. *Innovation in Language Learning and Teaching*, 1(1), 1–12. DOI [10.2167/illt039.0](https://doi.org/10.2167/illt039.0). [University manuscript](https://www.victoria.ac.nz/__data/assets/pdf_file/0019/1626121/2007-Four-strands.pdf). | Original manuscript text indexed in search and publisher abstract; direct PDF fetch timed out. Framework only. |
| R18 | Rađenović, A. M. (2023). *Категорија глаголског аспекта у српском као страном језику*. DOI [10.18485/ssjtip.2023.5.ch7](https://doi.org/10.18485/ssjtip.2023.5.ch7). [Faculty PDF](https://doi.fil.bg.ac.rs/pdf/eb_ser/ssjtip/2023-5/ssjtip-2023-5-ch7.pdf). | Full text; descriptive study. |

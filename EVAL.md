# Evaluation results

Run date: 2026-11-07/08. Nothing in the repo's code was changed. Tests: 84/84 passed earlier (see `BUILD_LOG.md`).

## Results

| book | chapters | metric | value | notes |
|------|----------|--------|-------|-------|
| Pride and Prejudice | Ch. I (pipeline ch. 2) | word match rate | 95.5% | strict 95.2%; 97.5% with 8 Gutenberg-markup lines removed; WER 6.6% |
| Pride and Prejudice | Ch. II (pipeline ch. 3) | word match rate | 97.3% | strict 96.8%; WER 17.8% is one Whisper loop (109 inserted words), not TTS; 97.7% without markup lines |
| Pride and Prejudice | Ch. III (pipeline ch. 4) | word match rate | 97.4% | strict 97.2%; 9 lines over 30 s; 98.1% without markup lines |
| Pride and Prejudice | Ch. I-III | mean of 3 chapters | 96.7% | unweighted |
| Holmes (A Scandal in Bohemia) | Sec. I (pipeline ch. 1) | word match rate | 98.3% | strict 98.0%; 168 of 212 lines perfect |
| Holmes (A Scandal in Bohemia) | Sec. II (pipeline ch. 2) | word match rate | 98.5% | strict 98.3%; 113 of 150 lines perfect |
| Holmes (A Scandal in Bohemia) | Sec. III (pipeline ch. 3) | word match rate | 98.5% | strict 98.3%; 58 of 70 lines perfect |
| Holmes (A Scandal in Bohemia) | Sec. I-III | mean of 3 chapters | 98.4% | unweighted |
| both books | all 6 chapters | **mean word match rate** | **97.6%** | unweighted mean of the 6 chapter rates; strict 97.3%; pooled over all 12,058 words 98.0% |
| both books | all 6 chapters | audio scored | 596 lines, 71 min | 36 lines (6%) are longer than 30 s, see Caveats |
| both books | Holmes sec. I | music level vs voice | -12.4 dB during speech | observation only, see "Music level"; not part of the fidelity score |

## How it was run

- **Books.** Pride and Prejudice from the Project Gutenberg plain-text file (#1342); Chapters I-III. Holmes from the Gutenberg EPUB (#1661): the three numbered sections of "A Scandal in Bohemia", written out as `Chapter 1-3` headings and uploaded as TXT. The pipeline's own EPUB splitter does not give chapters (see Findings), so I fed it chapter-sized units. Both books went through the unchanged pipeline: upload, analyze (LM Studio), render (VoxCPM2), mix.
- **Transcription.** Every cached `lines/*.wav` was transcribed by itself (596 separate Whisper calls, no chapter-level audio). `openai-whisper small.en`, English, `temperature=0`, `condition_on_previous_text=False`.
- **Second opinion.** The 31 worst or most inflated lines were also run through `medium.en` to separate TTS errors from Whisper errors.
- **Match rate.** Source words matched in a word-level edit-distance alignment, divided by source words. Insertions do not lower it; WER (which counts them) is given where it matters. Chapter rate = words pooled within the chapter. Mean = unweighted mean of the 6 chapter rates.
- **Normalisation.** Lower-case, punctuation removed, numbers spelled out. The headline ("lenient") figures also treat `Mister`=`Mr`, `chapter II`=`chapter 2`, and hyphen compounds (`to-morrow`) as matching joined or spaced forms. Strict figures (without these three rules) are shown beside them; they differ by 0.3-0.5 points.
- **Spoken text.** The text compared is `script.lines[i].text`, the string handed to the TTS.

## Per chapter

| chapter | lines | source words | audio | match rate | strict | WER | perfect lines |
|---|---|---|---|---|---|---|---|
| P&P Ch. I | 53 | 893 | 5.0 min | 95.5% | 95.2% | 6.6% | 31 |
| P&P Ch. II | 59 | 816 | 4.8 min | 97.3% | 96.8% | 17.8% | 34 |
| P&P Ch. III | 52 | 1,729 | 11.0 min | 97.4% | 97.2% | 10.0% | 23 |
| Holmes sec. I | 212 | 3,475 | 20.7 min | 98.3% | 98.0% | 2.0% | 168 |
| Holmes sec. II | 150 | 4,050 | 23.1 min | 98.5% | 98.3% | 1.9% | 113 |
| Holmes sec. III | 70 | 1,095 | 6.4 min | 98.5% | 98.3% | 1.7% | 58 |
| **mean of 6** | | | | **97.6%** | 97.3% | | |

## The 10 worst lines

Ranked by match rate (lowest first) among lines with 3 or more source words, ties broken by longer line first; 119 lines with 1-2 words are left out because one word swings them to 0% or 50%. There is a three-way tie for 10th at 50%; the third line (`31f81c75:3#35`) is listed after the table. Line IDs are `book:pipeline-chapter#line`. Heard = `small.en`; `medium.en` in brackets where it differs in a way that matters.

| # | line | rate | source text | heard text | class | evidence |
|---|---|---|---|---|---|---|
| 1 | `b71a690c:2#16` | 0% | `[_Copyright 1894 by George Allen._]]` | (nothing) [medium: `. . . . .`] | **TTS error** | The wav is near-silent (RMS 0.0005 vs about 0.07-0.18 for speech); neither model hears a word. The input was Gutenberg markup, not prose. |
| 2 | `b71a690c:2#48` | 0% | `[_Copyright 1894 by George Allen._]]` | `under Erlebuncles and they were fawn under guard.` [medium: `and they were fond under guard.`] | **TTS error** | Same input string as #1, a different output. Speech-like babble that contains none of the source words in either model. |
| 3 | `b71a690c:2#51` | 0% | `[_Copyright 1894 by George Allen._]]` | `Oh, Bokai.` [medium: `Oh, bokai...`] | **TTS error** | Third rendering of the same string, third different result. Both models agree on what was said and it is not the text. |
| 4 | `b71a690c:4#11` | 0% | `[_Copyright 1894 by George Allen._]]` | `MUN, NUAD-MINDEE, FINNERS, AND MINDEE` [medium: `Mine, no it mine-dy, fin-ner-ys, and mine-dy.`] | **TTS error** (moderate) | The two models disagree with each other, but neither finds a single source word. A clear reading of "Copyright 1894 by George Allen" would be easy for either. |
| 5 | `b71a690c:4#30` | 0% | `[_Copyright 1894 by George Allen._]]` | `Me nah nah nah nah ...` (108 more words) [medium: `Neenah neele nah nah No, no, no, ...`] | **TTS error** | 13.3 s of repeating syllables for a 4-word line, at very high Whisper confidence (avg logprob -0.06). Both models confirm the audio is not the text. |
| 6 | `b71a690c:2#47` | 33% | `[Illustration: M^{r.} & M^{rs.} Bennet` | `But, to an R&M, do not ask Bennett.` [medium: `But, you are not them, you are Erse Bennett.`] | **unclear** | The source is not pronounceable text, so there is no correct reading to compare against. Models agree only on "Bennett". |
| 7 | `31f81c75:1#115` | 33% | `said Holmes dryly.` | `Set homes dryly.` [medium: same] | **Whisper error** (moderate) | "Holmes" and "homes" are homophones and "said"/"set" differ by one consonant; 1.5 s with no context. `medium.en` gets the same phrase right on `1#186` and `2#147`, where `small.en` also says "set homes". |
| 8 | `31f81c75:1#148` | 33% | `Pooh, pooh! Forgery.` | `Poo poo forgery` [medium: same] | **Whisper error** | Spelling only: "Pooh" written "Poo". "Forgery" is correct. The audio is almost certainly right. |
| 9 | `b71a690c:3#7` | 50% | `But you forget, mamma,` | `You forget, Mama!` [medium: same] | **unclear** | "mamma"/"Mama" is a spelling difference (Whisper). The dropped initial "But" is in both models, so it may be a TTS clipped onset or Whisper skipping a weak first word; the audio was not listened to. |
| 10 | `31f81c75:3#27` | 50% | `I am Mr. Holmes,` | `I'm Mr. Holmes.` [medium: same] | **unclear** | Either the TTS said "I'm" or Whisper contracted "I am". Whisper often contracts; the 1.08 s duration cannot settle it. |

Tied for 10th: `31f81c75:3#35`, `asked the King hoarsely.` heard `Ask the king Horsley.` (both models). Whisper error: "Horsley" is a homophone spelling of "hoarsely", and the dropped "-ed" is typical of Whisper on a short clip.

Summary of the 10: 5 TTS errors, 2 Whisper errors, 3 unclear. **All 5 TTS errors come from one cause: Gutenberg markup in the TXT was read out as prose.** No line in the worst 10 shows a TTS error on real book text. The nearest candidate is #9 (dropped "But"), which is unclear.

### Largest absolute errors outside the worst 10

| line | what happened | class |
|---|---|---|
| `b71a690c:3#2` (25.8 s) | `small.en` repeats "She's a great person." about 20 times after the correct 65 words (178 words heard for 70 in the source, 109 insertions). `medium.en` transcribes the same wav cleanly in 70 words, and the wav has speech through to the end (RMS 0.11 in the last 2 s). The match rate is still 97%, but WER is huge. | **Whisper error** (decoding loop; not a 30 s boundary effect) |
| `b71a690c:2#14` | `[Illustration:` spoken as `I'm not sure why I'm here.` (5 inserted words) | TTS error, same markup cause |
| `b71a690c:3#54` | A lone `]` line spoken as `Hmm, I guess. Any glass?` | TTS error, same markup cause |

## Findings that are not fidelity scores

1. **Gutenberg TXT markup becomes script lines.** P&P's plain-text file contains `[Illustration: ...]`, `[_Copyright 1894 by George Allen._]]` and stray `]` lines. 19 such lines (about 12% of P&P's 164 lines; found by a regex for brackets, "Illustration" and "Copyright") were analyzed, voiced and mixed. The titles also pick up the bracket: `Chapter I.]`, spoken framing "End of chapter I.].". The same TTS input gave silence, babble and a 13 s loop on different lines. Removing these lines from scoring lifts P&P Ch. I from 95.5% to 97.5%.
2. **The EPUB splitter does not give chapters for either book.** P&P's EPUB came out as 16 units, each lumping about 6 real chapters (one is 57k characters); the first unit starts with the Gutenberg header. Holmes's EPUB comes out as whole stories (about 46k characters, 50 minutes of audio each). Both EPUB uploads were deleted from `data/`; the evaluation used the TXT route described above.
3. **Most of the remaining low-scoring real-prose lines look like spelling, not audible errors.** Names and rare words (Bennett, Lizzie, mamma/Mama, Pooh/Poo, brougham/Broam, hoarsely/Horsley, Saint/St.) and near-homophones (said/set, Holmes/homes) dominate the candidate list I reviewed (31 lines). I did not review every imperfect line. `medium.en` repaired several of them (`said Holmes`, `stoutly`, `wedlock`), so part of the 97.6% is Whisper's ceiling, not the TTS.

## Music level (user feedback, not fixed)

You reported that background music is a little loud, hard to hear words over, and in Holmes chapter 1 did not fit the chapter. Measured as `final.wav` minus `chapter.wav` (music plus sound effects against voice-only):

| chapter | music+sfx vs voice, during speech | cues |
|---|---|---|
| Holmes sec. I, this run (`31f81c75` ch01) | **-12.4 dB** (-10.8 dB overall) | melancholy 3-237 s, calm to 441 s, mysterious to 645 s, tense 646-1312 s, calm to 1353 s |
| Sherlock Holmes Complete, ch. 1 (`ca3f6ba2`, rendered 19:04) | **-13.2 dB** | melancholy to 243 s, mysterious to 881 s, playful to 1019 s |
| third book, ch. 1 (`e7a43d95`, 1 min) | -24.4 dB | one tense cue |

BUILD_LOG records about -18 dB for the earlier Holmes chapter. Both Holmes chapters sit 5-6 dB closer to the voice than that, and speech is barely ducking the bed (about 1.6 dB below the overall level). The numbers include sound effects, so the music alone is somewhat quieter; they were not separated. Whether the moods fit is a judgment I cannot make from the labels. Nothing was changed.

## Caveats

- **Lines over 30 s.** 36 of 596 lines run longer than 30 s (up to 80 s), so Whisper's internal 30 s windows still apply inside them; separating lines removes chapter-level contamination, not this. Dropping those lines moves the chapter rates by at most 0.8 points (P&P Ch. III 97.4% to 96.6%, the rest within 0.4). Among them, only one (`b71a690c:4#15`, 48 s) has more than 2 inserted words (3 of them, match rate 99%); none shows a boundary-style repeat.
- **One Whisper loop got through.** `temperature=0` with no fallback is deterministic but lets `small.en` loop; it hit `b71a690c:3#2` and nearly tripled that line's word count (P&P Ch. II WER). It does not move the match rate, which ignores insertions.
- **Classification is from transcripts, durations, and signal levels. No clip was listened to.** "Unclear" means the two models and the numbers do not settle it. Both Whisper models share biases, so two models agreeing is evidence, not proof.
- **One transcriber for the scores.** All 596 lines use `small.en`; `medium.en` only covers the 31 candidate lines.
- **Normalisation was extended after the first look.** The lenient rules were added after seeing that `Mister/Mr`, `chapter II/2` and hyphen compounds were inflating the error count; strict figures are shown so the choice is visible.
- **Shared server.** The jobs ran on the app's normal queue where an Atomic Habits analysis was already running at the start (you cancelled it later; my jobs waited behind it). Nothing in `data/` for other books was modified; the two EPUB test uploads I created were removed.

The scoring scripts and raw results were kept in a temporary session folder and are not part of the repo.

---

# Stress tests and performance (2026-11-08)

Nothing in the repo's code was changed. Stress tests called the same module functions the server calls and wrote only to a temporary folder outside the repo. "Broke" below means behaved wrongly; only one case raised an error.

## Hardware and software

| | |
|---|---|
| Machine | MacBook Pro, model identifier Mac16,6 |
| Chip | Apple M4 Max, 16-core CPU (12 performance + 4 efficiency), 40-core GPU |
| Memory | 64 GB unified |
| OS | macOS 27.2 (build 26B123), arm64 |
| Power | AC attached, battery 80%, not charging |
| LLM | `qwen/qwen3.8-27b` (4-bit) in LM Studio; context 64,000, parallel 4 |
| TTS | VoxCPM2 on MPS (10 timesteps, cfg 2.0), separate process and venv |
| Voice design | Qwen3-TTS VoiceDesign (MLX) |
| Music / SFX | MusicGen small (MPS) / AudioLDM small (CPU) |
| Python | 3.12.11 |

## Summary

| test | result | what broke | where |
|---|---|---|---|
| (a) TXT with no headings | Runs, wrong structure | Whole book becomes one 130,294-word chapter announced as "Preface."; 8 of 14 heading styles are not recognised | `books.py:6` `CHAPTER_RE`, `books.py:10-11`, `annotate.py:521` `frame` |
| (a) hard-wrapped TXT | **Error above the context limit** | No paragraph breaks means one LLM chunk of any size; a 300k-character chunk fails with HTTP 400 | `annotate.py:128` `chunk`, `annotate.py:222` `label_chunk` |
| (b) EPUB with footnotes / ToC | Runs, wrong content | Footnote numbers spoken, footnote bodies read as narration, notes and contents pages become chapters, heading announced twice | `books.py:37` `_epub` |
| (c) lines over 800 characters | **Nothing failed** | 7 lines, 911-3,606 characters, 96.9-99.4% match, no retries. Minor: pauses at arbitrary words when there is no punctuation | `tts.py:44` `_cut`, `tts.py:55` `split_text` |
| (d) 6+ speakers | Runs, cast errors | One person got two voices; look-alike hints contradict the description; two main characters got no voice traits | `annotate.py:459`, `tts.py:88` `voice_prompt` |

## (a) TXT with no chapter headings

**P&P with every heading line removed:** parsed in 0.004 s into 1 chapter titled "Full text" (130,294 words, 747,340 characters, including the Gutenberg header and licence). `annotate.frame` announces it as **"Preface."** and closes with **"End of preface."**. It would be 231 LLM chunks in a single job.

Extrapolated from the timed chapter below, not measured: about 5.6 h of annotation, 13.8 h of audio and 8.4 h of TTS, as one job. From reading `main.analyze`, `script.json` is written only after the whole annotation returns, so a failure late in the job would lose the earlier chunks. That was not run.

**Heading styles** (8-chapter synthetic books):

| heading style | expected | found |
|---|---|---|
| `Chapter 1` | 8 | 8 |
| `CHAPTER I.` | 8 | 8 |
| `Chapter 1: Title` | 8 | 8 |
| `Chapter 1` + title on next line | 8 | 8 |
| `    Chapter 1` (indented) | 8 | 8 |
| `CHAPTER 1` | 8 | 8 |
| `Chapter One` | 8 | **1** |
| `CHAPTER ONE` | 8 | **1** |
| bare `I.` | 8 | **1** |
| bare `1.` | 8 | **1** |
| `Part One` | 8 | **1** |
| `BOOK I` | 8 | **1** |
| `Section 1` | 8 | **1** |
| `* * *` separators | 8 | **1** |

Spelled-out chapter numbers are a common format, and they fall through to the single "Full text" chapter with no warning.

**Other parser cases:**

| case | expected | found | note |
|---|---|---|---|
| Line starting `Chapter 7 will show...` inside ch. 2 | 4 | 4 | Handled; sentence kept |
| Line starting `CHAPTER IV will show...` mid-chapter | 4 | **5** | Bogus chapter, and the sentence leaves the body and becomes a title. Roman numerals skip the in-order check (`books.py:16`, `num()` only reads digits) |
| `Chapter Civil Wars`, `Chapter Mix`, `Chapter Livid` | 3 | **1** | "Civil" is made only of letters in the numeral class, so it is accepted; the other two are not, and their text is absorbed |
| Table of contents + body (Roman or arabic) | 3 | 3 | Handled |

**Hard-wrapped TXT (paragraphs separated by one newline).** `chunk()` only cuts where a paragraph ends, so the whole text is one chunk regardless of the 3,000-character target. Each case is one direct `label_chunk` call.

| chunk | est. tokens | result | time |
|---|---|---|---|
| 9,731 chars, 117 units | ~2.5k | All labelled, 6 speakers | 92 s |
| 58,888 chars, 537 units | ~15k | All labelled, 17 speakers | 434 s |
| 117,910 chars, 1,028 units | ~30k | All labelled, 21 speakers | 839 s |
| 299,544 chars, 2,117 units | ~75k | **`BadRequestError: Error code: 400`** | 0.2 s |

- The limit lies between about 30k and 75k estimated tokens; the exact point was not searched. A hard-wrapped full novel would be past it.
- `label_chunk` only catches JSON errors, so per the code this exception reaches the job handler and fails the whole chapter. It was run directly, not through the server.
- I expected a failure near 16k tokens (64,000 / 4 parallel slots). That did not happen.
- Duplicate speakers appear in the big chunks: `Jane` / `Jane Bennet`, `Mr. Collins` / `William Collins`, `Sir William Lucas` / `William Lucas`, `Miss Bingley` / `Caroline Bingley`. Label accuracy was not scored.
- Separately, the blank-line book had one 15,058-character chunk (97 units with no paragraph end), 5x the target. Cause not investigated.

## (b) EPUB with footnotes and a table of contents

Synthetic EPUB (known contents): title page, EPUB nav, a contents page made of `<p>` links, two chapters with footnote markers, in-chapter footnotes, and a separate endnotes document. Chapter 1 went through annotate and TTS, then Whisper per line.

| item in the EPUB | what happened |
|---|---|
| Title page, EPUB nav | Dropped, correct (under the 200-character rule, or no `<p>`) |
| Contents page in `<p>` tags | **Became a chapter** ("Contents", 210 chars), dot leaders and page numbers included |
| Endnotes document | **Became a chapter** ("Notes", 877 chars), citations included |
| `<sup>` marker in a sentence | **Spoken.** `...to come (1). 1 He had seen...` heard as "One he had seen"; a trailing `3` heard as "three" |
| Inline `[2]` | Stays in the script text; not heard by Whisper |
| Footnote body in `<aside>` / `<div>` | **Read as narration** at the end of the chapter, e.g. "The harbor of St. Ives, C.F. Smith, Coastal Towns, London, 1894, P. 212." |
| Chapter heading | **Announced twice:** "Chapter one." (frame) then "Chapter 1" (from the body). `_epub` keeps `h1-h3` as text; heading removal exists only on the PDF path |

`_epub` takes every `p`, `h1`, `h2`, `h3` with `get_text`, with no notion of `epub:type="footnote"` or `noteref`.

The `(1)` in the test sentences was my own device for varying them, not a footnote. It came out garbled ("Mafwint"), so that error is a test artefact and I do not count it as a footnote failure. It does show parenthesised numbers are a risk. Also from real books: the P&P EPUB gave 16 units lumping about 6 chapters each, and the Holmes EPUB gave whole stories (see above).

## (c) Lines over 800 characters through TTS

Run through `tts.render` with the narrator voice. Each clip was cut at exact-zero gaps (all under 11 s) and transcribed separately; the transcripts were joined and scored against the whole line, so Whisper's 30 s window is not involved.

| line | chars | pieces | audio | render | RTF | match rate |
|---|---|---|---|---|---|---|
| Prose, several sentences | 922 | 8 | 59.8 s | 36.2 s | 0.61 | 98.8% |
| Prose, several sentences | 911 | 7 | 59.8 s | 38.9 s | 0.65 | 99.4% |
| One run-on sentence with commas | 1,053 | 9 | 74.3 s | 45.7 s | 0.62 | 98.1% |
| No punctuation, lower case | 987 | 7 | 62.8 s | 39.7 s | 0.63 | 96.9% |
| Natural Holmes line | 1,255 | 12 | 85.7 s | 56.4 s | 0.66 | 98.8% |
| Holmes opening prose | 1,966 | 17 | 141.4 s | 88.9 s | 0.63 | 99.1% |
| P&P's longest natural unit (a letter) | 3,606 | 31 | 253.4 s | 164.2 s | 0.65 | 99.1% |

**Nothing failed.** No exceptions, no worker retries logged, no truncation, and render cost stays linear. `split_text` cuts every line to pieces of about 160 characters, so the TTS model never sees a long input. The pipeline also produces such lines by itself: 3 of the 596 lines in the fidelity run exceed 800 characters (up to 1,255).

Weak spots, none of them failures:
- **No punctuation:** cuts land between arbitrary words (`_cut` falls back to the last space), each followed by 0.3 s of inserted silence (`tts.py:227`). 6 such joins on the 987-character line. Most of that line's score loss is a test artefact: my punctuation stripping joined "scissors-grinder" into one word.
- **Off by one:** the longest piece was 161 characters against a stated maximum of 160, because `split_text` does not count the joining space. Harmless.
- **Italic markers:** the 3,606-character line contains `_word_` italics. Whisper heard "underscore" once, so the marker may have been voiced there. One occurrence, not confirmed by ear.
- **Not tested:** voice drift or prosody across joins. Those need listening.

## (d) Chapter with 6+ speakers

P&P Chapter VII (2,004 words, 85 lines). Analyzed, every voice designed, the 2 longest lines per speaker rendered. No crash. Annotate 311 s, voice design 27 s.

| character | gender / age | lines | pitch | voice prompt |
|---|---|---|---|---|
| Mr. Bennet | male / adult | 8 | 146 Hz | "An adult male speaking voice." |
| Mrs. Bennet | female / adult | 14 | 178 Hz | "An adult female speaking voice." |
| Caroline Bingley | female / young | 3 | 188 Hz | "...clear, refined, and moderately pitched... **low and gravelly**" |
| Lydia Bennet | female / young | 3 | 231 Hz | "...loud, high-pitched, fast... **warm and breathy**" |
| Elizabeth Bennet | female / young | 6 | 244 Hz | "...a quick, witty pace... **soft and slow**" |
| Lydia | female / young | 4 | 285 Hz | "...bright, high-pitched, quick, and eager..." |
| Jane Bennet | female / young | 6 | 307 Hz | "...soft, gentle, and low-pitched... **higher-pitched and bright**" |
| Mary Bennet | female / young | 2 | 349 Hz | "...soft, high-pitched, slow... **crisp and brisk**" |

What broke:
1. **One person, two voices.** "Lydia" and "Lydia Bennet" are the same character, cast at 285 Hz and 231 Hz. She changes voice partway through the chapter. 0 of 85 lines are flagged `unsure`, so nothing prompts a review. Where the names are minted: `annotate.py:459`; the server's manual merge is the only remedy.
2. **Look-alike hints contradict the description.** `voice_prompt` appends a fixed `VARIETY` hint by position, regardless of the text before it. All 5 characters that received one have a clash (bold above). Jane is described as low-pitched and measured second-highest of the cast.
3. **The two most-voiced characters got no traits.** Mr. and Mrs. Bennet's prompts are only "An adult male/female speaking voice." Cause not investigated.
4. **Close pitches.** Mrs. Bennet / Caroline are 10 Hz apart and Lydia Bennet / Elizabeth 13 Hz. Pitch says nothing about timbre; voices were not compared by ear.
5. **Joint speech goes to one speaker.** "said Catherine and Lydia" was voiced as Lydia alone.
6. **Markup again.** 4 `[Illustration...]` lines, plus a Gutenberg `/* NIND “My dear friend, */` marker, voiced as "How kind, my dear friend."

Not triggered: `VARIETY` has 6 entries and reached index 5 here. A seventh same-gender, same-age character would reuse the first hint (`k % len(VARIETY)`), and the server counts `k` across the whole book, so longer books reach it sooner.

Word fidelity held up: 97.4% pooled over the sampled lines, 93-100% per speaker.

## Per-stage time for one full chapter

Holmes "A Scandal in Bohemia" section III: 1,081 words, 93 units, 71 lines, 4 characters, **413.2 s of audio**. Fresh output folder and empty music/SFX caches. One run on 2026-11-08, 04:39:32-04:47:31 (479 s wall). Server queue idle.

| stage | time | notes |
|---|---|---|
| **Parse** | 0.00 s | `extract_chapters` on the TXT |
| LLM load | 8.2 s | `ensure_loaded`, model was not loaded |
| **Annotate** | 159.0 s | Labels and descriptions 74.5 s, emphasis 70.3 s, SFX spotting 14.2 s |
| Voice design | 16.7 s | 4 voices: 8.1 s (includes model load), then 2.7-3.0 s each |
| TTS worker load | 12.8 s | Start plus one short line. README says about 2 min; model files were already in the OS cache |
| **TTS render** | 251.2 s | 71 lines |
| Music cues | 0.00 s | |
| **Music** generate + mix | 28.4 s | Cold: model load, 2 moods. About 26.5 s is generation |
| **Mix** (music only, warm cache) | 1.85 s | Re-run with clips cached |
| SFX | 0.01 s | **This chapter has no effects, so this is not a real cost** (see below) |
| Write WAV + MP3 | 0.9 s | |
| **Total** | **477.1 s** | Warm mix re-run not counted |

Measured separately, model load vs per-clip: MusicGen load 3.0 s, then 10.5-11.5 s per 20 s clip. AudioLDM load plus first clip 3.7 s, then about 2.8 s per 3 s clip.

**Real-time factor** (processing time / audio time; below 1 is faster than real time):

| scope | time | RTF |
|---|---|---|
| TTS render only | 251.2 s | **0.61** |
| Audio side (TTS + music + SFX + MP3) | 280.5 s | 0.68 |
| Full pipeline, models already loaded (excludes LLM and TTS worker load) | 456.2 s | **1.10** |
| Full pipeline including those loads | 477.1 s | **1.15** |

The 7 long-line runs in (c) gave TTS RTF 0.61-0.66, so the single-chapter figure is consistent.

## Peak memory (same run)

| measure | peak | notes |
|---|---|---|
| **System memory used** (active + wired + compressed) | **53.97 GB of 64 GB** | During TTS render. 23.99 GB at start, so about +30 GB. Includes everything else on the machine |
| LM Studio LLM worker RSS | 17.82 GB | During annotate |
| Pipeline processes RSS (Python + VoxCPM worker) | 11.90 GB | During TTS worker load |

By stage, system used peaked at 49.2 GB in annotate, 51.8 GB in voice design, 54.0 GB in TTS, 52.5 GB in music. The system figure is the one to trust. RSS undercounts Metal and MLX memory: LM Studio's RSS read 0.41 GB during TTS while system use stayed above 50 GB.

## Caveats on this section

- **One run of one 1,081-word chapter.** No repeats, so no variance. The LLM's cast also varies by run: this chapter had 3 characters in the fidelity run and 4 here.
- **Cold starts are partly warm.** Model files were on local disk and likely in the OS file cache after earlier runs. A first load after reboot was not measured and could be much slower.
- **Other load.** The app server stayed up with its idle workers throughout, and baseline memory drifted (24 GB and 33 GB at the start of different runs). Peak system memory depends on what else is open.
- **Main-server steps skipped.** The timed run did not apply aliases or first-person-narrator detection, and used an empty `about`. Those are small text operations.
- **Synthetic inputs.** Heading styles and the footnote EPUB were built for this test. Real books may combine these problems differently.
- **Token counts are estimates** (characters / 4).
- **Nothing was judged by ear.**
- **Added to your library.** The two evaluation books from the fidelity run (`b71a690c`, `31f81c75`) are still in `data/`. These stress tests added nothing there.

The stress and timing scripts were also kept in that temporary folder and are not in the repo.

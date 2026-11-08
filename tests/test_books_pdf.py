from app.books import reflow


def test_reflow_paragraphs_headers_and_page_numbers():
    page = ("Chapter\t1\nLOG\tENTRY:\tSOL\t6\nI’m\tpretty\tmuch\tscrewed\tand\tthis\tline\tis\tlong\tenough\tto\tbe\tfull\twidth\nhere.\n"
            "Screwed.\nSix\tdays\tin\tto\twhat\tshould\tbe\ta\tgreat\ttwo\tmonths\tof\tmy\tlife,\tand\tmore\tmore\nsoft-\nlanded\tok.")
    out = reflow(["", page, "7\nnext page text goes here"])
    paras = out.split("\n\n")
    assert paras[:3] == ["Chapter 1", "Log entry: sol 6.", "I’m pretty much screwed and this line is long enough to be full width here."]
    assert "Screwed." in paras and any(p.endswith("soft-landed ok.") for p in paras)
    assert "\t" not in out and "\n7\n" not in out


def test_heading_with_footer_before_it_and_endnote_lookalikes():
    from app.books import _split_by_headings
    body = "\n\n".join(f"Sentence number {i} of a long enough body paragraph for the chapter." for i in range(30))
    pages = ["Some earlier text that ends mid " * 12 + "\nwww.example.com", "CHAPTER 1\nInvestment versus Speculation: Results to\nBe Expected\n" + body,
             "CHAPTER 2\nThe Investor and Inflation\n" + body, "Chapter 1. Investment versus Speculation\nA short endnote."]
    out = _split_by_headings(reflow(pages))
    assert [c["title"] for c in out] == ["Opening", "Chapter 1: Investment versus Speculation: Results to Be Expected", "Chapter 2: The Investor and Inflation"]
    assert "www.example" not in out[0]["text"]


def test_outline_split_names_chapters_and_skips_matter():
    from app.books import split_by_outline
    body = "A paragraph of real chapter text that is long enough to count as content. " * 6
    pages = ["Title"] + [f"p{i} {body}" for i in range(1, 12)]
    W, P = ("Study in Scarlet",), ("Study in Scarlet", "Part 1")
    ents = [("Title Page", 0, ()), ("Study in Scarlet", 1, ()), ("Part 1", 1, W), ("Chapter 1 — A", 2, P), ("Chapter 2 — B", 4, P),
            ("Part 2", 6, W), ("Chapter 1 — C", 7, ("Study in Scarlet", "Part 2")), ("Red-Headed League", 9, ()), ("Notes", 11, ())]
    out = split_by_outline(ents, pages)
    assert [(c["part"], c["title"]) for c in out] == [
        ("Study in Scarlet › Part 1", "Chapter 1 — A"), ("Study in Scarlet › Part 1", "Chapter 2 — B"),
        ("Study in Scarlet › Part 2", "Chapter 1 — C"), ("", "Red-Headed League")]
    assert "p2 " in out[0]["text"] and "p4 " not in out[0]["text"] and "p9 " in out[3]["text"] and "p11 " not in out[3]["text"]


def test_frame_announces_the_work_and_closes_with_short_chapter_name():
    from app.annotate import frame
    f = frame("Chapter 1 — Mr. Sherlock Holmes", [], "A Study In Scarlet › Part 1")
    assert f[0]["text"] == "A Study In Scarlet, Part 1, Chapter one — Mr. Sherlock Holmes."
    assert f[-1]["text"] == "End of chapter one."


def test_repeated_headers_footers_and_links_are_dropped():
    from app.books import running_junk
    pages = [f"MY BOOK TITLE\nPage {i} of 90\nYes.\nBody line {i} that is real text.\nSee www.example.com/x for more.\nwww.watermark.com"
             for i in range(6)] + [f"CHAPTER {i}\nIntro {i}\nbody {i}" for i in range(5)]
    drop = running_junk(pages)
    assert {"my book title", "page # of #", "www.watermark.com"} <= drop and "chapter #" not in drop and "yes." not in drop
    out = reflow(pages, drop)
    assert "MY BOOK" not in out and "watermark" not in out and "example.com" not in out and "Page 3" not in out
    assert "Yes." in out and "Body line 3 that is real text." in out and "Chapter 1" in out


def test_dropcaps_ligatures_and_hyphens():
    # "I" + "n the year" is a drop cap; a lone "I" before "could" is a word; "cate-gory" loses its hyphen, "half-past" keeps it
    pages = ["I\nn the year 1878 I took my degree and was in the category of rows, and before\nI could join it I read the ﬂoor plan, ﬁt for a cate-\ngory of men. It was half-\npast five."]
    out = reflow(pages)
    assert out.startswith("In the year 1878") and "before I could join" in out and "floor plan, fit" in out
    assert "category of men" in out and "half-past five" in out


def test_chapter_starting_mid_page_is_cut_at_its_heading_and_heading_not_repeated():
    from app.books import cut_offset, split_by_outline
    body = "A paragraph of real chapter text that is long enough to count as content. " * 8
    p1 = "A Study In Scarlet\nCHAPTER I.\nMr. S herlock Holmes\nI\nn the year 1878 I took my degree. " + body + "\nEnd of the first chapter.\n"
    p2 = "The first chapter ends here at the top of this page.\nCHAPTER II.\nThe Science Of Deduction\nWe met next day. " + body
    assert p2[cut_offset(p2, "Chapter 2 — The Science Of Deduction"):].startswith("CHAPTER II.")
    assert p1[cut_offset(p1, "Chapter 1 — Mr. Sherlock Holmes"):].startswith("CHAPTER I.")  # the running page header above it is left out
    out = split_by_outline([("Chapter 1 — Mr. Sherlock Holmes", 0, ()), ("Chapter 2 — The Science Of Deduction", 1, ())], [p1, p2])
    assert "ends here at the top" in out[0]["text"] and "ends here" not in out[1]["text"]
    assert out[0]["text"].startswith("In the year 1878") and out[1]["text"].startswith("We met next day.")


def test_title_words_inside_a_sentence_are_not_a_heading():
    from app.books import cut_offset
    page = "Header\nwe have had the advantage of meeting Dr. Mortimer and Sir Henry\nBaskerville in the morning.\nCHAPTER IV.\nSir Henry Baskerville\nIt was nine."
    assert page[cut_offset(page, "Chapter 4 — Sir Henry Baskerville"):].startswith("CHAPTER IV.")

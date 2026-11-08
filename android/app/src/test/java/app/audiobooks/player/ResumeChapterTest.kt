package app.audiobooks.player

import app.audiobooks.player.data.Chapter
import app.audiobooks.player.ui.resumeChapter
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ResumeChapterTest {
    private fun c(n: Int, file: String? = "/f/$n.mp3", at: Long = 0) =
        Chapter("b", n, "Ch $n", "", "v", true, true, localFile = file, positionMs = if (at > 0) 1000 else 0, positionAt = at)

    @Test fun resumesTheMostRecentlyListenedDownloadedChapter() {
        assertEquals(3, resumeChapter(listOf(c(1, at = 10), c(2, at = 5), c(3, at = 99), c(4))))
    }

    private fun done(n: Int, at: Long) = Chapter("b", n, "Ch $n", "", "v", true, true, localFile = "/f/$n.mp3", positionMs = 0, positionAt = at)

    @Test fun movesOnToTheNextDownloadedChapterAfterAFinishedOne() {
        assertEquals(3, resumeChapter(listOf(done(1, 5), done(2, 99), c(3), c(4))))
    }

    @Test fun staysOnTheLastChapterWhenNothingFollowsAFinishedOne() {
        assertEquals(2, resumeChapter(listOf(done(1, 5), done(2, 99), c(3, file = null))))
    }

    @Test fun startsAtTheFirstDownloadedChapterWhenNothingWasPlayed() {
        assertEquals(2, resumeChapter(listOf(c(1, file = null), c(2), c(3))))
    }

    @Test fun ignoresChaptersThatAreNotDownloadedAndReturnsNullWhenNoneAre() {
        assertEquals(1, resumeChapter(listOf(c(1, at = 5), c(2, file = null, at = 50))))
        assertNull(resumeChapter(listOf(c(1, file = null), c(2, file = null))))
    }
}

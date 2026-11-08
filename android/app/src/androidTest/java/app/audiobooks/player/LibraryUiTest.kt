package app.audiobooks.player

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.audiobooks.player.data.Book
import app.audiobooks.player.data.BookWithProgress
import app.audiobooks.player.data.Chapter
import app.audiobooks.player.ui.AudiobooksTheme
import app.audiobooks.player.ui.BookScreen
import app.audiobooks.player.ui.LibraryScreen
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Compose tests: the phone's screen must be on and unlocked while they run. */
@RunWith(AndroidJUnit4::class)
class LibraryUiTest {
    @get:Rule val rule = createComposeRule()

    private val book = Book("b1", "A Study in Scarlet", "Arthur Conan Doyle", onPhone = true, onPc = true)
    private fun ch(n: Int, file: String? = null, ready: Boolean = true, onPc: Boolean = true) =
        Chapter("b1", n, "Chapter $n", "", "v1", ready, onPc, localFile = file)

    @Test fun libraryEmptyState_showsAddTile() {
        rule.setContent { AudiobooksTheme { LibraryScreen(emptyList(), onOpen = {}, onAdd = {}) } }
        rule.onNodeWithText("Add a book").assertIsDisplayed()
        rule.onNodeWithText("0 books on this phone").assertIsDisplayed()
    }

    @Test fun libraryShowsDownloadBadgesAndOpensABook() {
        var opened = ""
        val books = listOf(BookWithProgress(book, downloaded = 14, total = 16), BookWithProgress(book.copy(id = "b2", title = "Atomic Habits"), 3, 3))
        rule.setContent { AudiobooksTheme { LibraryScreen(books, onOpen = { opened = it }, onAdd = {}) } }
        rule.onNodeWithText("↓ 14/16").assertIsDisplayed()
        rule.onNodeWithText("↓ all").assertIsDisplayed()
        rule.onNodeWithText("Atomic Habits", substring = true).performClick()
        assertEquals("b2", opened)
    }

    @Test fun chapterRows_showWaitingForPcAndOffPcStates() {
        val chapters = listOf(ch(1, file = "/f/1.mp3"), ch(2, ready = false), ch(3, file = "/f/3.mp3", onPc = false), ch(4))
        rule.setContent { AudiobooksTheme { BookScreen(book, chapters, onBack = {}, onPlay = {}, onRemove = {}) } }
        rule.onNodeWithText("waiting for PC").assertIsDisplayed()
        rule.onNodeWithText("no longer on PC").assertIsDisplayed()
        rule.onNodeWithText("downloading…").assertIsDisplayed()
    }

    @Test fun removeAsksForConfirmationBeforeDeleting() {
        var removed = 0
        rule.setContent { AudiobooksTheme { BookScreen(book, listOf(ch(1, file = "/f/1.mp3")), onBack = {}, onPlay = {}, onRemove = { removed++ }) } }
        rule.onNodeWithText("Remove").performClick()
        assertEquals(0, removed)
        rule.onNodeWithText("Remove from phone").performClick()
        assertEquals(1, removed)
    }
}

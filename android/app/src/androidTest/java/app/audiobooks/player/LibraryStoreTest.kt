package app.audiobooks.player

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.audiobooks.player.data.AppDb
import app.audiobooks.player.data.Pairing
import app.audiobooks.player.data.PairingStore
import app.audiobooks.player.data.RemoteBook
import app.audiobooks.player.data.RemoteChapter
import app.audiobooks.player.data.RoomLibraryStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LibraryStoreTest {
    private lateinit var db: AppDb
    private lateinit var store: RoomLibraryStore

    private fun book(vararg ch: RemoteChapter) = RemoteBook("b1", "Book One", "A. Writer", ch.toList())
    private fun ch(n: Int, title: String = "Ch $n", ready: Boolean = true, version: String? = "100-1") =
        RemoteChapter(n, title, "P1", ready, if (ready) version else null, if (ready) 100L else null)

    @Before
    fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(ctx, AppDb::class.java).allowMainThreadQueries().build()
        store = RoomLibraryStore(db)
    }

    @After
    fun tearDown() = db.close()

    @Test
    fun applyCatalog_keepsLocalFileWhenChapterVanishesFromPc() = runBlocking {
        store.applyCatalog(listOf(book(ch(1), ch(2))))
        store.setOnPhone("b1", true)
        store.markDownloaded("b1", 1, "/files/b1/1.mp3", "100-1", "Ch 1")
        store.applyCatalog(listOf(book(ch(2))))                       // chapter 1 is gone from the PC
        val c1 = store.chapters("b1").first().first { it.n == 1 }
        assertEquals("/files/b1/1.mp3", c1.localFile)
        assertFalse(c1.onPc)
        store.applyCatalog(emptyList())                                 // the whole book is gone
        assertFalse(store.books().first().single().book.onPc)
        assertEquals("/files/b1/1.mp3", store.chapters("b1").first().first { it.n == 1 }.localFile)
    }

    @Test
    fun pendingWork_includesNewChangedVersionAndTitleChange() = runBlocking {
        store.applyCatalog(listOf(book(ch(1), ch(2), ch(3), ch(4, ready = false))))
        store.setOnPhone("b1", true)
        store.markDownloaded("b1", 1, "/f/1.mp3", "100-1", "Ch 1")
        store.markDownloaded("b1", 2, "/f/2.mp3", "100-1", "Ch 2")
        store.markDownloaded("b1", 3, "/f/3.mp3", "100-1", "Ch 3")
        assertTrue(store.pendingWork().isEmpty())                       // everything ready is downloaded, chapter 4 is not ready
        store.applyCatalog(listOf(book(ch(1, version = "200-9"), ch(2, title = "A different chapter"), ch(3), ch(4))))
        assertEquals(listOf(1, 2, 4), store.pendingWork().map { it.n })  // new version, renumbered title, newly ready
    }

    @Test
    fun pendingWork_ignoresBooksNotOnPhone() = runBlocking {
        store.applyCatalog(listOf(book(ch(1))))
        assertTrue(store.pendingWork().isEmpty())
    }

    @Test
    fun setOnPhone_false_clearDownloads_returnsFilesAndKeepsPositions() = runBlocking {
        store.applyCatalog(listOf(book(ch(1), ch(2))))
        store.setOnPhone("b1", true)
        store.markDownloaded("b1", 1, "/f/1.mp3", "100-1", "Ch 1")
        store.savePosition("b1", 1, 4200, 77)
        store.setOnPhone("b1", false)
        assertEquals(listOf("/f/1.mp3"), store.clearDownloads("b1"))
        val c1 = store.chapters("b1").first().first { it.n == 1 }
        assertNull(c1.localFile)
        assertEquals(4200L, c1.positionMs)
        assertEquals(77L, store.positions("b1").getValue(1).at)
    }

    @Test
    fun savePosition_keepsNewestWrite() = runBlocking {
        store.applyCatalog(listOf(book(ch(1))))
        store.savePosition("b1", 1, 5000, 100)
        store.savePosition("b1", 1, 1000, 50)                           // older write must not win
        assertEquals(5000L, store.positions("b1").getValue(1).ms)
    }

    @Test
    fun books_reportDownloadedOverTotal() = runBlocking {
        store.applyCatalog(listOf(book(ch(1), ch(2), ch(3, ready = false))))
        store.setOnPhone("b1", true)
        store.markDownloaded("b1", 1, "/f/1.mp3", "100-1", "Ch 1")
        val b = store.books().first().single()
        assertEquals(1 to 2, b.downloaded to b.total)
    }

    @Test
    fun pairingStore_roundtripAndClear() = runBlocking {
        val ps = PairingStore(ApplicationProvider.getApplicationContext())
        ps.clear()
        assertNull(ps.pairing.first())
        ps.save(Pairing("192.168.1.5", 8001, "tok"))
        assertEquals(Pairing("192.168.1.5", 8001, "tok"), ps.pairing.first())
        ps.clear()
        assertNull(ps.pairing.first())
        assertNotNull(ps)
    }
}

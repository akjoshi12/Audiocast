package app.audiobooks.player

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.audiobooks.player.data.AppDb
import app.audiobooks.player.data.RemoteBook
import app.audiobooks.player.data.RemoteChapter
import app.audiobooks.player.data.RoomLibraryStore
import app.audiobooks.player.ui.LibraryActions
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class LibraryActionsTest {
    private lateinit var db: AppDb
    private lateinit var store: RoomLibraryStore
    private lateinit var dir: File
    private var syncs = 0
    private lateinit var actions: LibraryActions

    @Before fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(ctx, AppDb::class.java).allowMainThreadQueries().build()
        store = RoomLibraryStore(db)
        dir = File(ctx.cacheDir, "actions-${System.nanoTime()}").also { it.mkdirs() }
        actions = LibraryActions(store) { syncs++ }
        runBlocking {
            store.applyCatalog(listOf(RemoteBook("b1", "Book", "A", listOf(RemoteChapter(1, "Ch 1", "P", true, "v1", 10), RemoteChapter(2, "Ch 2", "P", true, "v1", 10)))))
        }
    }

    @After fun tearDown() { db.close(); dir.deleteRecursively() }

    @Test fun addBook_putsItOnThePhone_andRequestsASync() = runBlocking {
        actions.addBook("b1")
        assertTrue(store.books().first().single().book.onPhone)
        assertEquals(1, syncs)
    }

    @Test fun removeBook_deletesFilesAndKeepsPositions_andNeverTouchesThePcCatalogue() = runBlocking {
        actions.addBook("b1")
        val f = File(dir, "1.mp3").also { it.writeBytes(ByteArray(10)) }
        store.markDownloaded("b1", 1, f.path, "v1", "Ch 1")
        store.savePosition("b1", 1, 4000, 9)
        actions.removeBook("b1")
        assertFalse(f.exists())
        val b = store.books().first().single()
        assertFalse(b.book.onPhone)
        assertTrue(b.book.onPc)                                      // still listed as available on the PC
        assertNull(store.chapters("b1").first().first { it.n == 1 }.localFile)
        assertEquals(4000L, store.positions("b1").getValue(1).ms)    // position survives, so re-adding resumes
        assertEquals(1, syncs)                                       // only the add asked for a sync
    }
}

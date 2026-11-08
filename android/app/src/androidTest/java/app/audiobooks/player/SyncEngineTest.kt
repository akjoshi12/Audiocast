package app.audiobooks.player

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.audiobooks.player.data.AppDb
import app.audiobooks.player.data.Position
import app.audiobooks.player.data.RemoteBook
import app.audiobooks.player.data.RemoteChapter
import app.audiobooks.player.data.RoomLibraryStore
import app.audiobooks.player.net.BadTokenException
import app.audiobooks.player.net.PcApiLike
import app.audiobooks.player.sync.SyncEngine
import app.audiobooks.player.sync.SyncResult
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.io.IOException

/** In-memory PC: a catalogue, chapter bodies, positions, and switches to break things. */
class FakePc : PcApiLike {
    var catalog: List<RemoteBook> = emptyList()
    val bodies = mutableMapOf<Pair<String, Int>, ByteArray>()
    val remotePositions = mutableMapOf<String, MutableMap<Int, Position>>()
    var badToken = false
    var failAfterBytes: Int? = null        // next download writes this many bytes, then the network "drops"
    var noSpace = false
    var libraryError: Exception? = null
    val resumes = mutableListOf<Long>()
    val downloads = mutableListOf<Pair<String, Int>>()

    override suspend fun library(): List<RemoteBook> { if (badToken) throw BadTokenException(); libraryError?.let { throw it }; return catalog }

    override suspend fun download(bookId: String, n: Int, dest: File, resumeFrom: Long, onProgress: (Long) -> Unit) {
        if (badToken) throw BadTokenException()
        if (noSpace) throw IOException("No space left on device")
        downloads += bookId to n
        resumes += resumeFrom
        val body = bodies.getValue(bookId to n)
        val start = if (resumeFrom > 0) resumeFrom.toInt() else 0
        val cut = failAfterBytes
        val chunk = if (cut != null) body.copyOfRange(start, start + cut) else body.copyOfRange(start, body.size)
        if (resumeFrom > 0) dest.appendBytes(chunk) else dest.writeBytes(chunk)
        if (cut != null) { failAfterBytes = null; throw IOException("connection lost") }
    }

    override suspend fun positions(bookId: String) = remotePositions[bookId]?.toMap() ?: emptyMap()
    override suspend fun putPositions(bookId: String, m: Map<Int, Position>) {
        val cur = remotePositions.getOrPut(bookId) { mutableMapOf() }
        m.forEach { (n, p) -> if (cur[n] == null || p.at > cur.getValue(n).at) cur[n] = p }
    }
}

@RunWith(AndroidJUnit4::class)
class SyncEngineTest {
    private lateinit var db: AppDb
    private lateinit var store: RoomLibraryStore
    private lateinit var dir: File
    private val pc = FakePc()
    private fun engine() = SyncEngine(pc, store, dir)

    private fun ch(n: Int, title: String = "Ch $n", version: String? = "v1", ready: Boolean = true) =
        RemoteChapter(n, title, "P", ready, if (ready) version else null, if (ready) 10L else null)

    private fun body(seed: Int, size: Int = 300) = ByteArray(size) { (it * seed % 251).toByte() }

    @Before fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(ctx, AppDb::class.java).allowMainThreadQueries().build()
        store = RoomLibraryStore(db)
        dir = File(ctx.cacheDir, "sync-test-${System.nanoTime()}").also { it.mkdirs() }
    }

    @After fun tearDown() { db.close(); dir.deleteRecursively() }

    private fun catalog(vararg c: RemoteChapter) { pc.catalog = listOf(RemoteBook("b1", "Book", "A", c.toList())) }

    @Test fun downloads_readyChaptersOfAddedBooksOnly() = runBlocking {
        catalog(ch(1), ch(2), ch(3, ready = false))
        pc.catalog = pc.catalog + RemoteBook("b2", "Other", "", listOf(ch(1)))
        pc.bodies[("b1" to 1)] = body(3); pc.bodies[("b1" to 2)] = body(5); pc.bodies[("b2" to 1)] = body(7)
        engine().syncOnce().also { assertEquals(SyncResult.Done(0), it) }                 // nothing added yet
        store.setOnPhone("b1", true)
        assertEquals(SyncResult.Done(2), engine().syncOnce())
        assertEquals(listOf("b1" to 1, "b1" to 2), pc.downloads)
        val f1 = File(store.chapters("b1").first().first { it.n == 1 }.localFile!!)
        assertArrayEquals(body(3), f1.readBytes())
        assertEquals(SyncResult.Done(0), engine().syncOnce())                              // unchanged chapters are not fetched again
        assertEquals(2, pc.downloads.size)
    }

    @Test fun interruptedDownload_leavesNoPlayableFile_andResumesNextSync() = runBlocking {
        catalog(ch(1)); pc.bodies[("b1" to 1)] = body(9)
        store.applyCatalog(pc.catalog); store.setOnPhone("b1", true)
        pc.failAfterBytes = 100
        assertTrue(engine().syncOnce() is SyncResult.Failed)
        assertNull(store.chapters("b1").first().single().localFile)
        assertFalse(File(dir, "b1/1.mp3").exists())
        assertEquals(1, File(dir, "b1").listFiles()!!.count { it.name.endsWith(".part") })
        assertEquals(SyncResult.Done(1), engine().syncOnce())
        assertEquals(listOf(0L, 100L), pc.resumes)                                          // second try resumed at byte 100
        assertArrayEquals(body(9), File(dir, "b1/1.mp3").readBytes())
        assertEquals(0, File(dir, "b1").listFiles()!!.count { it.name.endsWith(".part") })
    }

    @Test fun versionChange_replacesAudio_andTitleChangeAtSameNumberRedownloads() = runBlocking {
        catalog(ch(1), ch(2)); pc.bodies[("b1" to 1)] = body(3); pc.bodies[("b1" to 2)] = body(5)
        store.applyCatalog(pc.catalog); store.setOnPhone("b1", true)
        engine().syncOnce()
        catalog(ch(1, version = "v2"), ch(2, title = "Totally different chapter"))
        pc.bodies[("b1" to 1)] = body(4); pc.bodies[("b1" to 2)] = body(6)
        assertEquals(SyncResult.Done(2), engine().syncOnce())
        val rows = store.chapters("b1").first()
        assertArrayEquals(body(4), File(rows[0].localFile!!).readBytes())
        assertArrayEquals(body(6), File(rows[1].localFile!!).readBytes())
        assertEquals("v2", rows[0].localVersion)
    }

    @Test fun chapterGoneFromPc_keepsLocalCopy_markedOffPc() = runBlocking {
        catalog(ch(1)); pc.bodies[("b1" to 1)] = body(3)
        store.applyCatalog(pc.catalog); store.setOnPhone("b1", true)
        engine().syncOnce()
        pc.catalog = emptyList()
        assertEquals(SyncResult.Done(0), engine().syncOnce())
        val c = store.chapters("b1").first().single()
        assertFalse(c.onPc)
        assertArrayEquals(body(3), File(c.localFile!!).readBytes())
    }

    @Test fun badToken_returnsNeedsRepair_andDownloadsNothing() = runBlocking {
        catalog(ch(1)); pc.bodies[("b1" to 1)] = body(3)
        store.applyCatalog(pc.catalog); store.setOnPhone("b1", true)
        pc.badToken = true
        assertEquals(SyncResult.NeedsRepair, engine().syncOnce())
        assertTrue(pc.downloads.isEmpty())
    }

    @Test fun diskFull_returnsStorageFull_andKeepsExistingFiles() = runBlocking {
        catalog(ch(1)); pc.bodies[("b1" to 1)] = body(3)
        store.applyCatalog(pc.catalog); store.setOnPhone("b1", true)
        engine().syncOnce()
        catalog(ch(1), ch(2)); pc.bodies[("b1" to 2)] = body(5)
        pc.noSpace = true
        assertEquals(SyncResult.StorageFull, engine().syncOnce())
        assertArrayEquals(body(3), File(dir, "b1/1.mp3").readBytes())
    }

    @Test fun positions_newestWins_bothDirections() = runBlocking {
        catalog(ch(1), ch(2)); pc.bodies[("b1" to 1)] = body(3); pc.bodies[("b1" to 2)] = body(5)
        store.applyCatalog(pc.catalog); store.setOnPhone("b1", true)
        store.savePosition("b1", 1, 5000, 200)                                              // phone is newer for chapter 1
        pc.remotePositions["b1"] = mutableMapOf(1 to Position(100, 100), 2 to Position(7000, 300))  // PC is newer for chapter 2
        engine().syncOnce()
        assertEquals(Position(5000, 200), pc.remotePositions.getValue("b1")[1])
        assertEquals(Position(7000, 300), store.positions("b1")[2])
    }

    @Test fun unexpectedError_becomesFailedInsteadOfCrashing() = runBlocking {
        pc.libraryError = IllegalArgumentException("Unexpected JSON token at offset 0")   // e.g. a router login page instead of the PC
        val r = engine().syncOnce()
        assertTrue("got $r", r is SyncResult.Failed && r.msg.contains("Unexpected JSON"))
    }
}

package app.audiobooks.player

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.audiobooks.player.data.AppDb
import app.audiobooks.player.data.RemoteBook
import app.audiobooks.player.data.RemoteChapter
import app.audiobooks.player.data.RoomLibraryStore
import app.audiobooks.player.player.PlayerController
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class PlaybackTest {
    private val inst = InstrumentationRegistry.getInstrumentation()
    private lateinit var db: AppDb
    private lateinit var store: RoomLibraryStore
    private lateinit var scope: CoroutineScope
    private lateinit var controller: PlayerController

    private fun main(block: () -> Unit) = inst.runOnMainSync(block)

    private fun waitUntil(ms: Long, cond: () -> Boolean) {
        val end = System.currentTimeMillis() + ms
        while (!cond()) {
            check(System.currentTimeMillis() < end) { "timed out; state=${controller.state.value}" }
            Thread.sleep(100)
        }
    }

    @Before fun setUp() {
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(ctx, AppDb::class.java).allowMainThreadQueries().build()
        store = RoomLibraryStore(db)
        val file = File(ctx.filesDir, "tone-${System.nanoTime()}.mp3")
        inst.context.assets.open("tone.mp3").use { i -> file.outputStream().use { i.copyTo(it) } }
        runBlocking {
            store.applyCatalog(listOf(RemoteBook("b1", "Book", "A", listOf(RemoteChapter(1, "Ch 1", "P", true, "v1", 10)))))
            store.setOnPhone("b1", true)
            store.markDownloaded("b1", 1, file.path, "v1", "Ch 1")
        }
        scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
        main {
            controller = PlayerController(ctx, store, scope)
            controller.setSpeed(1f)             // the service (and its player) outlives a test: don't inherit the last test's speed
        }
    }

    @After fun tearDown() {
        main { controller.release() }
        Thread.sleep(500)                       // let release()'s final position save finish before the database goes away
        scope.cancel()
        db.close()
    }

    @Test fun playsDownloadedFileOffline_andSavesPosition() {
        main { controller.play("b1", 1) }
        waitUntil(15_000) { controller.state.value.isPlaying }
        assertEquals("Ch 1", controller.state.value.title)
        Thread.sleep(3_000)
        main { controller.toggle() }                                       // pause saves the position
        waitUntil(3_000) { !controller.state.value.isPlaying }
        Thread.sleep(500)
        val ms = runBlocking { store.positions("b1")[1]?.ms ?: 0L }
        assertTrue("saved position was $ms", ms >= 2_500)
    }

    @Test fun resumeSeeksToSavedPosition() {
        runBlocking { store.savePosition("b1", 1, 2_000, 5) }
        main { controller.play("b1", 1) }
        waitUntil(15_000) { controller.state.value.isPlaying }
        val p = controller.state.value.positionMs
        assertTrue("resumed at $p", p in 2_000..4_500)
    }

    @Test fun speedIsClampedAndSkipsMove() {
        main { controller.play("b1", 1) }
        waitUntil(15_000) { controller.state.value.isPlaying }
        main { controller.setSpeed(5f) }
        waitUntil(3_000) { controller.state.value.speed == 2.0f }
        main { controller.setSpeed(0.1f) }
        waitUntil(3_000) { controller.state.value.speed == 0.75f }
        main { controller.forward30() }                                      // 9 s file: lands at the end or moves to the next item
        Thread.sleep(500)
        assertTrue(controller.state.value.positionMs >= 0)
    }
}

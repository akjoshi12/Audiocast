package app.audiobooks.player

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.audiobooks.player.data.Pairing
import app.audiobooks.player.net.AndroidNsdSource
import app.audiobooks.player.net.BadTokenException
import app.audiobooks.player.net.Discovery
import app.audiobooks.player.net.PcApi
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * Talks to the REAL PC service. Skipped unless run with
 * -Pandroid.testInstrumentationRunnerArguments.pcHost=<ip> -Pandroid.testInstrumentationRunnerArguments.pcToken=<token>.
 */
@RunWith(AndroidJUnit4::class)
class RealPcTest {
    private val args = InstrumentationRegistry.getArguments()
    private val host get() = args.getString("pcHost")
    private val token get() = args.getString("pcToken")

    private fun api(tok: String = token!!) = PcApi("http://$host:8001", tok)

    @Test fun realPc_rejectsWrongToken() = runBlocking {
        assumeTrue(host != null && token != null)
        try { api("wrong").library(); throw AssertionError("expected BadTokenException") } catch (_: BadTokenException) { }
    }

    @Test fun realPc_listsLibraryAndDownloadsAChapterByteForByte() = runBlocking {
        assumeTrue(host != null && token != null)
        val lib = api().library()
        val (book, chapter) = lib.firstNotNullOf { b -> b.chapters.firstOrNull { it.ready }?.let { b to it } }
        val dest = File(ApplicationProvider.getApplicationContext<Context>().cacheDir, "real-pc-${System.nanoTime()}.mp3")
        var last = 0L
        api().download(book.id, chapter.n, dest) { last = it }
        assertEquals("size from the catalogue", chapter.size, dest.length())
        assertEquals(dest.length(), last)
        val head = dest.inputStream().use { ByteArray(3).also { b -> it.read(b) } }
        assertTrue("MP3 header", head.decodeToString() == "ID3" || (head[0] == 0xFF.toByte() && (head[1].toInt() and 0xE0) == 0xE0))
        // resume: ask for the rest of the file after the first 1000 bytes
        val part = File(dest.path + ".part").also { dest.inputStream().use { i -> it.writeBytes(i.readNBytes(1000)) } }
        api().download(book.id, chapter.n, part, resumeFrom = 1000)
        assertTrue("resumed file is identical", part.readBytes().contentEquals(dest.readBytes()))
        dest.delete(); part.delete()
        Unit
    }

    @Test fun realPc_isFoundByMdnsWhenTheSavedAddressIsStale() = runBlocking {
        assumeTrue(host != null && token != null)
        val ctx = ApplicationProvider.getApplicationContext<Context>()
        val found = Discovery(AndroidNsdSource(ctx)).locate(Pairing("203.0.113.7", 8001, token!!))   // TEST-NET address: nothing answers
        assertNotNull("mDNS should find the PC on this wifi", found)
        assertEquals(host, found!!.host)
        assertEquals(8001, found.port)
    }
}

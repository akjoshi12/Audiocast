package app.audiobooks.player

import app.audiobooks.player.data.Pairing
import app.audiobooks.player.data.Position
import app.audiobooks.player.net.BadTokenException
import app.audiobooks.player.net.PcApi
import app.audiobooks.player.net.parsePairingUrl
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class PcApiTest {
    @get:Rule val tmp = TemporaryFolder()
    private lateinit var server: MockWebServer
    private lateinit var api: PcApi

    @Before fun setUp() {
        server = MockWebServer().also { it.start() }
        api = PcApi(server.url("/").toString().trimEnd('/'), "secret", OkHttpClient())
    }

    @After fun tearDown() = server.shutdown()

    @Test fun library_parsesCatalogue() = runBlocking {
        server.enqueue(MockResponse().setBody("""[{"id":"b1","title":"Book","author":"A","chapters":[
            {"n":1,"title":"One","part":"P","ready":true,"version":"10-5","size":10},
            {"n":2,"title":"Two","part":"P","ready":false,"version":null,"size":null}]}]"""))
        val lib = api.library()
        assertEquals("Book", lib.single().title)
        assertEquals(listOf(true, false), lib.single().chapters.map { it.ready })
        assertEquals("10-5", lib.single().chapters[0].version)
        val req = server.takeRequest()
        assertEquals("Bearer secret", req.getHeader("Authorization"))
        assertEquals("/sync/v1/library", req.path)
    }

    @Test fun bad_token_throwsBadTokenException() {
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"bad token"}"""))
        try { runBlocking { api.library() }; throw AssertionError("expected BadTokenException") } catch (_: BadTokenException) { }
    }

    @Test fun download_resumesWithRangeHeaderAndAppends() = runBlocking {
        val dest = tmp.newFile("c.mp3.part").also { it.writeBytes(ByteArray(100) { 1 }) }
        server.enqueue(MockResponse().setResponseCode(206).setBody(Buffer().write(ByteArray(50) { 2 })))
        api.download("b1", 3, dest, resumeFrom = 100)
        assertEquals("bytes=100-", server.takeRequest().getHeader("Range"))
        assertEquals(150L, dest.length())
        assertArrayEquals(ByteArray(50) { 2 }, dest.readBytes().copyOfRange(100, 150))
    }

    @Test fun download_restartsWhenServerIgnoresRange() = runBlocking {
        val dest = tmp.newFile("d.part").also { it.writeBytes(ByteArray(100) { 1 }) }
        server.enqueue(MockResponse().setResponseCode(200).setBody(Buffer().write(ByteArray(40) { 3 })))  // full body, no 206
        api.download("b1", 1, dest, resumeFrom = 100)
        assertEquals(40L, dest.length())
    }

    @Test fun positions_roundtrip() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"1":{"ms":900,"at":10}}"""))
        assertEquals(mapOf(1 to Position(900, 10)), api.positions("b1"))
        server.enqueue(MockResponse().setBody("""{"1":{"ms":900,"at":10},"2":{"ms":5,"at":20}}"""))
        api.putPositions("b1", mapOf(2 to Position(5, 20)))
        server.takeRequest()
        val put = server.takeRequest()
        assertEquals("PUT", put.method)
        assertTrue(put.body.readUtf8().contains("\"2\":{\"ms\":5,\"at\":20}"))
    }

    @Test fun parsePairingUrl_roundtrip_and_rejectsGarbage() {
        assertEquals(Pairing("192.168.1.5", 8001, "abc123"), parsePairingUrl("audiobook://pair?host=192.168.1.5&port=8001&token=abc123"))
        assertNull(parsePairingUrl("https://example.com/?host=x&port=1&token=t"))
        assertNull(parsePairingUrl("audiobook://pair?host=1.2.3.4&port=notanumber&token=t"))
        assertNull(parsePairingUrl("audiobook://pair?host=1.2.3.4&port=8001"))
        assertNull(parsePairingUrl("garbage"))
    }
}

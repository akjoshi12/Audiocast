package app.audiobooks.player

import app.audiobooks.player.data.Pairing
import app.audiobooks.player.net.Discovery
import app.audiobooks.player.net.NsdSource
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DiscoveryTest {
    private val saved = Pairing("192.168.1.5", 8001, "tok")
    private fun nsd(found: Pair<String, Int>?) = object : NsdSource { override suspend fun find(timeoutMs: Long) = found }

    @Test fun locate_keepsSavedAddressWhileItAnswers() = runBlocking {
        val d = Discovery(nsd("10.0.0.9" to 8001)) { true }
        assertEquals(saved, d.locate(saved))
    }

    @Test fun locate_usesMdnsWhenSavedHostIsDead() = runBlocking {
        val d = Discovery(nsd("10.0.0.9" to 8001)) { it.host == "10.0.0.9" }
        assertEquals(Pairing("10.0.0.9", 8001, "tok"), d.locate(saved))   // same token, new address
    }

    @Test fun locate_returnsNullWhenNothingAnswers() = runBlocking {
        assertNull(Discovery(nsd(null)) { false }.locate(saved))
        assertNull(Discovery(nsd("10.0.0.9" to 8001)) { false }.locate(saved))
    }
}

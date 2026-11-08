package app.audiobooks.player.net

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import app.audiobooks.player.data.Pairing
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.OkHttpClient
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume

/** Finds the PC's `_audiobook._tcp` mDNS announcement on the current wifi. */
interface NsdSource {
    suspend fun find(timeoutMs: Long): Pair<String, Int>?
}

private val quick = OkHttpClient.Builder().callTimeout(2, TimeUnit.SECONDS).build()

/** True if something answers there (a 401 counts: the PC is there, the token is the problem). */
suspend fun reachable(p: Pairing): Boolean = try {
    PcApi("http://${p.host}:${p.port}", p.token, quick).library(); true
} catch (_: BadTokenException) {
    true
} catch (_: IOException) {
    false
}

class Discovery(private val nsd: NsdSource, private val probe: suspend (Pairing) -> Boolean = ::reachable) {
    /** The saved address if it still answers, else the mDNS address (same token), else null. */
    suspend fun locate(saved: Pairing): Pairing? {
        if (probe(saved)) return saved
        val (host, port) = nsd.find(5000) ?: return null
        val found = saved.copy(host = host, port = port)
        return if (probe(found)) found else null
    }
}

class AndroidNsdSource(context: Context) : NsdSource {
    private val manager = context.applicationContext.getSystemService(NsdManager::class.java)

    @Suppress("DEPRECATION")
    override suspend fun find(timeoutMs: Long): Pair<String, Int>? = withTimeoutOrNull(timeoutMs) {
        suspendCancellableCoroutine { cont ->
            val listener = object : NsdManager.DiscoveryListener {
                override fun onServiceFound(info: NsdServiceInfo) {
                    manager.resolveService(info, object : NsdManager.ResolveListener {
                        override fun onServiceResolved(r: NsdServiceInfo) {
                            val ip = r.host?.hostAddress ?: return
                            if (cont.isActive) cont.resume(ip to r.port)
                        }

                        override fun onResolveFailed(info: NsdServiceInfo, code: Int) {}
                    })
                }

                override fun onDiscoveryStarted(type: String) {}
                override fun onDiscoveryStopped(type: String) {}
                override fun onServiceLost(info: NsdServiceInfo) {}
                override fun onStartDiscoveryFailed(type: String, code: Int) { if (cont.isActive) cont.resume(null) }
                override fun onStopDiscoveryFailed(type: String, code: Int) {}
            }
            manager.discoverServices("_audiobook._tcp", NsdManager.PROTOCOL_DNS_SD, listener)
            cont.invokeOnCancellation { runCatching { manager.stopServiceDiscovery(listener) } }
        }
    }
}

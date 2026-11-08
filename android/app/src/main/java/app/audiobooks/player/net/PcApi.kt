package app.audiobooks.player.net

import app.audiobooks.player.data.Pairing
import app.audiobooks.player.data.Position
import app.audiobooks.player.data.RemoteBook
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.MapSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.URI

/** The PC refused the token: the user has to pair again. Any other failure to reach the PC is an [IOException]. */
class BadTokenException : Exception("The PC rejected the pairing token")

interface PcApiLike {
    suspend fun library(): List<RemoteBook>

    /** Writes the chapter MP3 to [dest]; with [resumeFrom] > 0 it asks for the rest and appends (or restarts if the server sends it all). */
    suspend fun download(bookId: String, n: Int, dest: File, resumeFrom: Long = 0, onProgress: (Long) -> Unit = {})
    suspend fun positions(bookId: String): Map<Int, Position>

    /** Saves the book's poster to [dest]; false if the PC has none. */
    suspend fun cover(bookId: String, dest: File): Boolean = false
    suspend fun putPositions(bookId: String, m: Map<Int, Position>)
}

class PcApi(private val baseUrl: String, private val token: String, private val client: OkHttpClient = OkHttpClient()) : PcApiLike {
    private val json = Json { ignoreUnknownKeys = true }
    private val posSerializer = MapSerializer(String.serializer(), Position.serializer())

    private fun req(path: String) = Request.Builder().url("$baseUrl/sync/v1$path").header("Authorization", "Bearer $token")

    private suspend fun <T> call(r: Request, read: (Response) -> T): T = withContext(Dispatchers.IO) {
        client.newCall(r).execute().use { resp ->
            if (resp.code == 401) throw BadTokenException()
            read(resp)
        }
    }

    private fun Response.text(): String {
        if (!isSuccessful) throw IOException("HTTP $code")
        return body!!.string()
    }

    override suspend fun library(): List<RemoteBook> = json.decodeFromString(call(req("/library").build()) { it.text() })

    override suspend fun download(bookId: String, n: Int, dest: File, resumeFrom: Long, onProgress: (Long) -> Unit) {
        val b = req("/books/$bookId/chapters/$n/audio")
        if (resumeFrom > 0) b.header("Range", "bytes=$resumeFrom-")
        call(b.build()) { resp ->
            if (!resp.isSuccessful) throw IOException("HTTP ${resp.code}")
            val append = resumeFrom > 0 && resp.code == 206
            var done = if (append) resumeFrom else 0L
            FileOutputStream(dest, append).use { out ->
                val buf = ByteArray(64 * 1024)
                resp.body!!.byteStream().use { input ->
                    while (true) {
                        val k = input.read(buf)
                        if (k < 0) break
                        out.write(buf, 0, k)
                        done += k
                        onProgress(done)
                    }
                }
                out.fd.sync()
            }
        }
    }

    override suspend fun cover(bookId: String, dest: File): Boolean = call(req("/books/$bookId/cover").build()) { resp ->
        if (resp.code == 404) return@call false
        if (!resp.isSuccessful) throw IOException("HTTP ${resp.code}")
        dest.outputStream().use { resp.body!!.byteStream().copyTo(it) }
        true
    }

    override suspend fun positions(bookId: String): Map<Int, Position> =
        json.decodeFromString(posSerializer, call(req("/positions/$bookId").build()) { it.text() }).mapKeys { it.key.toInt() }

    override suspend fun putPositions(bookId: String, m: Map<Int, Position>) {
        val body = json.encodeToString(posSerializer, m.mapKeys { it.key.toString() }).toRequestBody("application/json".toMediaType())
        call(req("/positions/$bookId").put(body).build()) { it.text() }
    }
}

/** `audiobook://pair?host=…&port=…&token=…` from the QR on the PC page, or null if it is anything else. */
fun parsePairingUrl(s: String): Pairing? {
    try {
        val u = URI(s)
        if (u.scheme != "audiobook" || u.host != "pair") return null
        val q = (u.rawQuery ?: return null).split("&").associate { it.substringBefore("=") to it.substringAfter("=", "") }
        val host = q["host"]?.takeIf { it.isNotBlank() } ?: return null
        val port = q["port"]?.toIntOrNull() ?: return null
        val token = q["token"]?.takeIf { it.isNotBlank() } ?: return null
        return Pairing(host, port, token)
    } catch (_: Exception) {
        return null
    }
}

package app.audiobooks.player.sync

import app.audiobooks.player.data.LibraryStore
import app.audiobooks.player.net.BadTokenException
import app.audiobooks.player.net.PcApiLike
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import app.audiobooks.player.ui.Covers
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption

sealed interface SyncResult {
    data class Done(val downloaded: Int) : SyncResult
    data object PcNotFound : SyncResult
    data object NeedsRepair : SyncResult
    data object StorageFull : SyncResult
    data class Failed(val msg: String) : SyncResult
}

/**
 * One sync pass against a reachable PC: refresh the catalogue, download what the phone's books are missing (atomically: a chapter
 * only becomes a real `<n>.mp3` once it is complete), then exchange listening positions. It never deletes downloaded audio except
 * to replace it with a newer version of the same chapter.
 */
class SyncEngine(
    private val api: PcApiLike,
    private val store: LibraryStore,
    private val dir: File,
    private val onProgress: (String) -> Unit = {},
) {
    suspend fun syncOnce(): SyncResult = try {
        val remote = api.library()
        store.applyCatalog(remote)
        syncCovers(remote)
        val todo = store.pendingWork()
        todo.forEach { download(it) }
        syncPositions()
        SyncResult.Done(todo.size)
    } catch (e: BadTokenException) {
        SyncResult.NeedsRepair
    } catch (e: IOException) {
        val m = e.message.orEmpty()
        if ("No space left" in m || "ENOSPC" in m) SyncResult.StorageFull else SyncResult.Failed(m.ifBlank { "network error" })
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {   // e.g. malformed JSON from something that is not the PC: report it, never crash or hang the Sync tab
        SyncResult.Failed(e.message ?: e::class.java.simpleName)
    }

    /** Posters are small and only re-fetched when the PC's version of one changes. A failure here never fails the sync. */
    private suspend fun syncCovers(remote: List<app.audiobooks.player.data.RemoteBook>) {
        val covers = File(dir, "_covers").also { it.mkdirs() }
        for (b in remote) {
            val v = b.cover ?: continue
            val img = File(covers, "${b.id}.jpg")
            val ver = File(covers, "${b.id}.ver")
            if (img.exists() && ver.exists() && ver.readText() == v) continue
            try {
                val tmp = File(covers, "${b.id}.tmp")
                if (api.cover(b.id, tmp)) {
                    Files.move(tmp.toPath(), img.toPath(), StandardCopyOption.REPLACE_EXISTING)
                    ver.writeText(v)
                    Covers.changed.update { it + 1 }
                }
            } catch (e: BadTokenException) {
                throw e
            } catch (e: IOException) {
                // keep the old poster (or the gradient tile) and try again next sync
            }
        }
    }

    private suspend fun download(c: app.audiobooks.player.data.Chapter) {
        val version = c.remoteVersion ?: return
        val bookDir = File(dir, c.bookId).also { it.mkdirs() }
        // the version is in the part's name, so bytes of an older render are never resumed into a newer one
        val part = File(bookDir, "${c.n}-${version.replace(Regex("[^A-Za-z0-9]"), "_")}.part")
        bookDir.listFiles { f -> f.name.startsWith("${c.n}-") && f.name.endsWith(".part") && f != part }?.forEach { it.delete() }
        onProgress(c.title)
        api.download(c.bookId, c.n, part, if (part.exists()) part.length() else 0)
        val target = File(bookDir, "${c.n}.mp3")
        Files.move(part.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
        store.markDownloaded(c.bookId, c.n, target.path, version, c.title)
    }

    private suspend fun syncPositions() {
        for (b in store.books().first().filter { it.book.onPhone }) {
            val id = b.book.id
            val remote = api.positions(id)
            val local = store.positions(id)
            val push = local.filter { (n, p) -> (remote[n]?.at ?: -1L) < p.at }
            if (push.isNotEmpty()) api.putPositions(id, push)
            remote.forEach { (n, p) -> if (p.at > (local[n]?.at ?: 0L)) store.savePosition(id, n, p.ms, p.at) }
        }
    }
}

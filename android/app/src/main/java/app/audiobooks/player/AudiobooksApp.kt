package app.audiobooks.player

import android.app.Application
import app.audiobooks.player.data.AppDb
import app.audiobooks.player.data.PairingStore
import app.audiobooks.player.data.RoomLibraryStore
import app.audiobooks.player.player.PlayerController
import app.audiobooks.player.sync.SyncScheduler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import java.io.File

/** Process-wide singletons: the library, pairing, the player, and where downloaded chapters live. */
class AudiobooksApp : Application() {
    val library by lazy { RoomLibraryStore(AppDb.get(this)) }
    val pairing by lazy { PairingStore(this) }
    val booksDir by lazy { File(filesDir, "books") }
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    val player by lazy { PlayerController(this, library, scope) }

    override fun onCreate() {
        super.onCreate()
        SyncScheduler.schedule(this)
    }
}

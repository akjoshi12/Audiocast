package app.audiobooks.player.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import app.audiobooks.player.data.AppDb
import app.audiobooks.player.data.Pairing
import app.audiobooks.player.data.PairingStore
import app.audiobooks.player.data.RoomLibraryStore
import app.audiobooks.player.net.AndroidNsdSource
import app.audiobooks.player.net.Discovery
import app.audiobooks.player.net.PcApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import okhttp3.OkHttpClient
import java.io.File
import java.util.concurrent.TimeUnit

/** What the Sync tab shows. */
data class SyncStatus(val running: Boolean = false, val current: String? = null, val last: SyncResult? = null, val lastAt: Long? = null)

object SyncState {
    val status = MutableStateFlow(SyncStatus())
}

class SyncWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        val pairings = PairingStore(applicationContext)
        val saved = pairings.pairing.first() ?: return Result.success()   // not paired yet: nothing to do
        SyncState.status.update { it.copy(running = true, current = null) }
        val result = try { run(saved, pairings) } finally { SyncState.status.update { it.copy(running = false, current = null) } }
        SyncState.status.value = SyncStatus(false, null, result, System.currentTimeMillis())
        return if (result is SyncResult.Failed) Result.retry() else Result.success()
    }

    private suspend fun run(saved: Pairing, pairings: PairingStore): SyncResult {
        val found = Discovery(AndroidNsdSource(applicationContext)).locate(saved)
        return if (found == null) SyncResult.PcNotFound else {
            if (found != saved) pairings.save(found)                        // the PC moved to a new address: remember it
            val api = PcApi("http://${found.host}:${found.port}", found.token, client)
            SyncEngine(api, RoomLibraryStore(AppDb.get(applicationContext)), File(applicationContext.filesDir, "books")) { title ->
                SyncState.status.update { it.copy(current = title) }
            }.syncOnce()
        }
    }

    private companion object {
        val client: OkHttpClient = OkHttpClient.Builder().readTimeout(60, TimeUnit.SECONDS).build()
    }
}

object SyncScheduler {
    private val wifiOnly = Constraints.Builder().setRequiredNetworkType(NetworkType.UNMETERED).build()

    /** Every 15 minutes (Android's minimum) while on an unmetered network, plus [syncNow] when the app opens. */
    fun schedule(ctx: Context) {
        val req = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES).setConstraints(wifiOnly).build()
        WorkManager.getInstance(ctx).enqueueUniquePeriodicWork("sync-periodic", ExistingPeriodicWorkPolicy.KEEP, req)
    }

    fun syncNow(ctx: Context) {
        val req = OneTimeWorkRequestBuilder<SyncWorker>().setConstraints(wifiOnly).build()
        WorkManager.getInstance(ctx).enqueueUniqueWork("sync-now", ExistingWorkPolicy.REPLACE, req)
    }
}

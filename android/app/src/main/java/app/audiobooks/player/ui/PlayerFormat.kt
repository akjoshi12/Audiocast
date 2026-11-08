package app.audiobooks.player.ui

import app.audiobooks.player.sync.SyncResult
import app.audiobooks.player.sync.SyncStatus

private val SPEEDS = listOf(0.75f, 1f, 1.25f, 1.5f, 1.75f, 2f)

/** The speed chip's next step; wraps from the top back to the slowest. */
fun nextSpeed(cur: Float): Float = SPEEDS.firstOrNull { it > cur + 1e-3f } ?: SPEEDS.first()

fun speedLabel(x: Float): String = if (x % 1f == 0f) "${x.toInt()}×" else "$x×"

fun fmtTime(ms: Long): String {
    val s = maxOf(0L, ms) / 1000
    val h = s / 3600
    val m = s % 3600 / 60
    val sec = s % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, sec) else "%d:%02d".format(m, sec)
}

fun syncHeadline(s: SyncStatus, paired: Boolean): String = when {
    !paired -> "Not paired with a PC"
    s.running -> "Syncing…"
    else -> when (val r = s.last) {
        null -> "Waiting for your home wifi"
        is SyncResult.Done -> if (r.downloaded == 0) "Up to date" else "Connected to your PC"
        SyncResult.PcNotFound -> "PC not found"
        SyncResult.NeedsRepair -> "Re-pair needed"
        SyncResult.StorageFull -> "Phone storage is full"
        is SyncResult.Failed -> "Sync failed: ${r.msg}"
    }
}

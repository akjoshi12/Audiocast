package app.audiobooks.player

import app.audiobooks.player.sync.SyncResult
import app.audiobooks.player.sync.SyncStatus
import app.audiobooks.player.ui.fmtTime
import app.audiobooks.player.ui.nextSpeed
import app.audiobooks.player.ui.speedLabel
import app.audiobooks.player.ui.syncHeadline
import org.junit.Assert.assertEquals
import org.junit.Test

class PlayerFormatTest {
    @Test fun speedChipCyclesThroughAllSpeedsAndWraps() {
        val seen = generateSequence(0.75f) { nextSpeed(it) }.take(7).toList()
        assertEquals(listOf(0.75f, 1f, 1.25f, 1.5f, 1.75f, 2f, 0.75f), seen)
        assertEquals(1.25f, nextSpeed(1.1f))                       // an odd speed goes to the next step up
        assertEquals(listOf("0.75×", "1×", "1.25×", "2×"), listOf(0.75f, 1f, 1.25f, 2f).map(::speedLabel))
    }

    @Test fun fmtTimeShowsMinutesAndSecondsAndHours() {
        assertEquals("0:00", fmtTime(0))
        assertEquals("6:38", fmtTime(398_000))
        assertEquals("1:02:03", fmtTime(3_723_000))
        assertEquals("0:00", fmtTime(-5))
    }

    @Test fun syncHeadlineCoversEveryState() {
        fun h(s: SyncStatus, paired: Boolean = true) = syncHeadline(s, paired)
        assertEquals("Not paired with a PC", h(SyncStatus(), paired = false))
        assertEquals("Syncing…", h(SyncStatus(running = true)))
        assertEquals("Up to date", h(SyncStatus(last = SyncResult.Done(0))))
        assertEquals("Connected to your PC", h(SyncStatus(last = SyncResult.Done(3))))
        assertEquals("PC not found", h(SyncStatus(last = SyncResult.PcNotFound)))
        assertEquals("Re-pair needed", h(SyncStatus(last = SyncResult.NeedsRepair)))
        assertEquals("Phone storage is full", h(SyncStatus(last = SyncResult.StorageFull)))
        assertEquals("Sync failed: boom", h(SyncStatus(last = SyncResult.Failed("boom"))))
        assertEquals("Waiting for your home wifi", h(SyncStatus()))
    }
}

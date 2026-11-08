package app.audiobooks.player

import app.audiobooks.player.player.SleepTimer
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SleepTimerTest {
    @Test fun expiresAfterDurationAndCancelsCleanly() = runTest {
        var expired = 0
        val t = SleepTimer(this) { expired++ }
        t.start(1)                                   // one minute
        advanceTimeBy(59_000)
        runCurrent()                                 // advanceTimeBy stops just before its end time
        assertEquals(0, expired)
        assertEquals(1_000L, t.leftMs.value)
        advanceTimeBy(1_100)
        assertEquals(1, expired)
        assertEquals(0L, t.leftMs.value)             // 0 = off

        t.start(1)
        advanceTimeBy(10_000)
        t.cancel()
        advanceTimeBy(120_000)
        assertEquals(1, expired)                     // a cancelled timer never fires
        assertEquals(0L, t.leftMs.value)
    }

    @Test fun restartingReplacesThePreviousTimer() = runTest {
        var expired = 0
        val t = SleepTimer(this) { expired++ }
        t.start(1)
        advanceTimeBy(30_000)
        t.start(2)                                   // 2 minutes from now, not 30 s left of the first
        advanceTimeBy(90_000)
        assertEquals(0, expired)
        advanceTimeBy(31_000)
        assertEquals(1, expired)
    }
}

package app.audiobooks.player.player

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/** Counts down once a second and calls [onExpire] at zero. Starting again replaces the running timer. [leftMs] is 0 when off. */
class SleepTimer(private val scope: CoroutineScope, private val onExpire: () -> Unit) {
    private var job: Job? = null
    private val left = MutableStateFlow(0L)
    val leftMs: StateFlow<Long> = left

    fun start(minutes: Int) {
        job?.cancel()
        left.value = minutes * 60_000L
        job = scope.launch {
            while (left.value > 0) {
                val step = minOf(1000L, left.value)
                delay(step)
                left.value -= step
            }
            onExpire()
        }
    }

    fun cancel() {
        job?.cancel()
        job = null
        left.value = 0
    }
}

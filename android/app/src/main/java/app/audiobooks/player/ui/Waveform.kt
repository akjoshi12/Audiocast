package app.audiobooks.player.ui

import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import java.nio.ByteOrder
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.sqrt

/** Loudness over time of a chapter MP3, as [BARS] values in 0..1. Decoded once per file, kept in memory. ponytail: no disk cache; add one if re-decoding after process death feels slow. */
object Waveform {
    const val BARS = 20   // few points on purpose: the wave should swell slowly, not squiggle
    private val cache = ConcurrentHashMap<String, FloatArray>()

    fun of(path: String): FloatArray? = cache[path] ?: decode(path)?.also { cache[path] = it }

    private fun decode(path: String): FloatArray? = runCatching {
        val ex = MediaExtractor().apply { setDataSource(path) }
        val fmt = ex.getTrackFormat(0).also { ex.selectTrack(0) }
        val durUs = fmt.getLong(MediaFormat.KEY_DURATION).takeIf { it > 0 } ?: return null
        val codec = MediaCodec.createDecoderByType(fmt.getString(MediaFormat.KEY_MIME)!!).apply { configure(fmt, null, null, 0); start() }
        val sq = DoubleArray(BARS); val n = LongArray(BARS)
        val info = MediaCodec.BufferInfo()
        var inputDone = false
        try {
            while (true) {
                if (!inputDone) {
                    val i = codec.dequeueInputBuffer(10_000)
                    if (i >= 0) {
                        val size = ex.readSampleData(codec.getInputBuffer(i)!!, 0)
                        if (size < 0) { codec.queueInputBuffer(i, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM); inputDone = true }
                        else { codec.queueInputBuffer(i, 0, size, ex.sampleTime, 0); ex.advance() }
                    }
                }
                val o = codec.dequeueOutputBuffer(info, 10_000)
                if (o >= 0) {
                    val pcm = codec.getOutputBuffer(o)!!.order(ByteOrder.nativeOrder()).asShortBuffer()
                    val bar = (info.presentationTimeUs * BARS / durUs).toInt().coerceIn(0, BARS - 1)
                    while (pcm.hasRemaining()) { val v = pcm.get().toDouble(); sq[bar] += v * v; n[bar]++ }
                    codec.releaseOutputBuffer(o, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) break
                }
            }
        } finally { codec.stop(); codec.release(); ex.release() }
        val rms = FloatArray(BARS) { if (n[it] > 0) sqrt(sq[it] / n[it]).toFloat() else 0f }
        // Narration is evenly loud, so stretch the range: quietest 10% sits at the floor, loudest 5% at full height. Shows relative loudness, not absolute.
        val sorted = rms.sortedArray()
        val lo = sorted[(BARS * 0.10).toInt()]
        val hi = sorted[(BARS * 0.95).toInt()].coerceAtLeast(lo + 1f)
        FloatArray(BARS) { 0.3f + 0.7f * ((rms[it] - lo) / (hi - lo)).coerceIn(0f, 1f) }
    }.getOrNull()
}

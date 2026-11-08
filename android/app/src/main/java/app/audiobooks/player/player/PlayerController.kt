package app.audiobooks.player.player

import android.content.ComponentName
import android.content.Context
import android.net.Uri
import androidx.core.content.ContextCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import app.audiobooks.player.data.LibraryStore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File

data class PlayerUiState(
    val loaded: Boolean = false,
    val bookId: String = "",
    val n: Int = 0,
    val title: String = "",
    val book: String = "",
    val isPlaying: Boolean = false,
    val positionMs: Long = 0,
    val durationMs: Long = 0,
    val speed: Float = 1f,
    val sleepLeftMs: Long = 0,
)

/**
 * The UI's handle on the playback service. [scope] must run on the main thread (a MediaController is main-thread only).
 * Saves the listening position every 5 s while playing and whenever playback pauses or a chapter ends.
 */
class PlayerController(
    context: Context,
    private val store: LibraryStore,
    private val scope: CoroutineScope,
    private val now: () -> Long = System::currentTimeMillis,
) {
    private val app = context.applicationContext
    private val ui = MutableStateFlow(PlayerUiState())
    val state: StateFlow<PlayerUiState> = ui

    private var controller: MediaController? = null
    private val whenConnected = mutableListOf<(MediaController) -> Unit>()
    private var lastId: String? = null
    private var lastPos = 0L   // where the chapter that is about to be replaced had got to
    private var lastDur = 0L
    private val sleep = SleepTimer(scope) { controller?.pause() }

    private val listener = object : Player.Listener {
        override fun onIsPlayingChanged(isPlaying: Boolean) {
            if (!isPlaying) saveNow()
            refresh()
        }

        override fun onMediaItemTransition(item: MediaItem?, reason: Int) {
            // finished chapters restart from the top next time; skipping ahead from the last 10% counts as finished too
            if (reason == Player.MEDIA_ITEM_TRANSITION_REASON_AUTO || (lastDur > 0 && lastPos >= lastDur * 0.9)) lastId?.let { finished(it) }
            lastId = item?.mediaId
            refresh()
        }

        override fun onPlaybackStateChanged(playbackState: Int) {
            if (playbackState == Player.STATE_ENDED) controller?.currentMediaItem?.mediaId?.let { finished(it) }   // the book's last chapter has no next item to transition to
            refresh()
        }
        override fun onPlaybackParametersChanged(playbackParameters: androidx.media3.common.PlaybackParameters) = refresh()
    }

    init {
        val token = SessionToken(app, ComponentName(app, PlaybackService::class.java))
        val future = MediaController.Builder(app, token).buildAsync()
        future.addListener({
            val c = future.get()
            controller = c
            c.addListener(listener)
            whenConnected.forEach { it(c) }
            whenConnected.clear()
            refresh()
        }, ContextCompat.getMainExecutor(app))
        scope.launch { sleep.leftMs.collect { l -> ui.update { it.copy(sleepLeftMs = l) } } }
        scope.launch {
            var tick = 0
            while (isActive) {
                delay(500)
                refresh()
                if (controller?.isPlaying == true && ++tick % 10 == 0) saveNow()
            }
        }
    }

    private fun withController(block: (MediaController) -> Unit) {
        val c = controller
        if (c != null) block(c) else whenConnected += block
    }

    private fun split(id: String): Pair<String, Int> = id.substringBeforeLast(":") to id.substringAfterLast(":").toInt()

    private fun finished(id: String) {
        val (b, n) = split(id)
        scope.launch { store.savePosition(b, n, 0, now()) }
    }

    private fun saveNow() {
        val c = controller ?: return
        if (c.playbackState == Player.STATE_ENDED) return   // finished() already stored 0; don't overwrite it with the end position
        val id = c.currentMediaItem?.mediaId ?: return
        val pos = c.currentPosition
        val (b, n) = split(id)
        scope.launch { store.savePosition(b, n, pos, now()) }
    }

    private fun refresh() {
        val c = controller ?: return
        val item = c.currentMediaItem
        val (b, n) = item?.mediaId?.let(::split) ?: ("" to 0)
        if (item?.mediaId == lastId) { lastPos = c.currentPosition; lastDur = c.duration.coerceAtLeast(0) }
        ui.update {
            it.copy(
                loaded = item != null, bookId = b, n = n, title = item?.mediaMetadata?.title?.toString().orEmpty(),
                book = item?.mediaMetadata?.artist?.toString().orEmpty(), isPlaying = c.isPlaying, positionMs = c.currentPosition,
                durationMs = c.duration.coerceAtLeast(0), speed = c.playbackParameters.speed,
            )
        }
    }

    /** Queue = the book's downloaded chapters in order, starting at chapter [n], seeking to its saved position. */
    fun play(bookId: String, n: Int) {
        scope.launch {
            val chapters = store.chapters(bookId).first().filter { it.localFile != null }.sortedBy { it.n }
            val idx = chapters.indexOfFirst { it.n == n }
            if (idx < 0) return@launch
            val bookTitle = store.books().first().firstOrNull { it.book.id == bookId }?.book?.title.orEmpty()
            val items = chapters.map { c ->
                MediaItem.Builder().setMediaId("$bookId:${c.n}").setUri(Uri.fromFile(File(c.localFile!!)))
                    .setMediaMetadata(MediaMetadata.Builder().setTitle(c.title).setArtist(bookTitle).setAlbumTitle(bookTitle).build()).build()
            }
            lastId = items[idx].mediaId
            withController { it.setMediaItems(items, idx, chapters[idx].positionMs); it.prepare(); it.play() }
        }
    }

    fun toggle() = withController { if (it.isPlaying) it.pause() else it.play() }
    fun back15() = withController { it.seekBack() }
    fun forward30() = withController { it.seekForward() }
    fun next() = withController { it.seekToNextMediaItem() }
    fun previous() = withController { it.seekToPreviousMediaItem() }
    fun seekTo(ms: Long) = withController { it.seekTo(ms) }
    fun setSpeed(x: Float) = withController { it.setPlaybackSpeed(x.coerceIn(0.75f, 2.0f)) }
    fun sleepIn(minutes: Int?) = if (minutes == null) sleep.cancel() else sleep.start(minutes)

    fun release() {
        saveNow()
        controller?.release()
        controller = null
    }
}

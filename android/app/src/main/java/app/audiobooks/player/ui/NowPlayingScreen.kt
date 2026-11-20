package app.audiobooks.player.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.Canvas
import androidx.compose.ui.geometry.Offset
import androidx.compose.runtime.produceState
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.clipRect
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bedtime
import androidx.compose.material.icons.filled.FormatListBulleted
import androidx.compose.material.icons.filled.Forward10
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Replay
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.audiobooks.player.data.Chapter
import app.audiobooks.player.player.PlayerUiState

/** What the chapter page can ask the player to do. */
class PlayerCommands(
    val toggle: () -> Unit, val back15: () -> Unit, val forward30: () -> Unit, val next: () -> Unit, val previous: () -> Unit,
    val seekTo: (Long) -> Unit, val setSpeed: (Float) -> Unit, val sleepIn: (Int?) -> Unit, val playChapter: (Int) -> Unit,
)

/** Progress as a smooth sine wave whose height follows the chapter's real loudness ([peaks], flat until decoded): bright up to the playhead, dim after it, an empty ring on the wave at the playhead. Tap to jump, drag to scrub; [onScrub] reports the live value (null when released), [onSeek] the final one. */
@Composable
private fun WaveScrubber(value: Float, peaks: FloatArray?, onScrub: (Float?) -> Unit, onSeek: (Float) -> Unit, modifier: Modifier = Modifier) {
    var width by remember { mutableIntStateOf(1) }
    val seek by rememberUpdatedState(onSeek)
    val scrubTo by rememberUpdatedState(onScrub)
    fun frac(x: Float) = (x / width).coerceIn(0f, 1f)
    Canvas(
        modifier.fillMaxWidth().height(56.dp).onSizeChanged { width = it.width.coerceAtLeast(1) }
            .pointerInput(Unit) { detectTapGestures { seek(frac(it.x)) } }
            .pointerInput(Unit) {
                var last = 0f
                detectHorizontalDragGestures(
                    onDragStart = { last = frac(it.x); scrubTo(last) },
                    onDragEnd = { scrubTo(null); seek(last) },
                    onDragCancel = { scrubTo(null) },
                ) { change, _ -> last = frac(change.position.x); scrubTo(last) }
            }
            .semantics { progressBarRangeInfo = ProgressBarRangeInfo(value, 0f..1f) },
    ) {
        val cy = size.height / 2
        val stroke = 4.dp.toPx(); val maxAmp = 14.dp.toPx(); val wave = 40.dp.toPx(); val r = 9.dp.toPx()
        val x0 = r; val x1 = size.width - r
        fun env(x: Float): Float {                                   // loudness at x, linearly interpolated between bars
            val p = peaks ?: return .25f
            val t = ((x - x0) / (x1 - x0)).coerceIn(0f, 1f) * (p.size - 1)
            val i = t.toInt().coerceAtMost(p.size - 2).coerceAtLeast(0)
            val f = (1 - cos(PI.toFloat() * (t - i))) / 2                       // cosine blend: no kinks between points
            return p[i] + (p[i + 1] - p[i]) * f
        }
        fun y(x: Float) = cy + maxAmp * env(x) * sin(2 * PI.toFloat() * x / wave)
        val path = Path().apply {
            moveTo(x0, y(x0))
            var x = x0
            while (x < x1) { x += 2f; lineTo(x, y(x)) }
        }
        val px = x0 + value.coerceIn(0f, 1f) * (x1 - x0)
        val line = Stroke(stroke, cap = StrokeCap.Round, join = StrokeJoin.Round)
        clipRect(left = 0f, right = px) { drawPath(path, Text1, style = line) }
        clipRect(left = px, right = size.width) { drawPath(path, Muted.copy(alpha = .35f), style = line) }
        drawCircle(Ink, r - stroke / 2, Offset(px, y(px)))                           // empty round
        drawCircle(Text1, r - stroke / 4, Offset(px, y(px)), style = Stroke(stroke / 2))
    }
}

/** The page of the chapter that is playing: cover, title, scrubber, controls. Opens from a chapter row, the mini player or the notification. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NowPlayingScreen(state: PlayerUiState, chapters: List<Chapter>, c: PlayerCommands, onClose: (() -> Unit)? = null) {
    var scrub by remember { mutableStateOf<Float?>(null) }
    var sleepMenu by remember { mutableStateOf(false) }
    var chapterSheet by remember { mutableStateOf(false) }
    val dur = state.durationMs.coerceAtLeast(1)
    val shown = scrub ?: (state.positionMs.toFloat() / dur).coerceIn(0f, 1f)
    val total = chapters.size
    CompositionLocalProvider(LocalContentColor provides Text1) {
    Column(
        Modifier.fillMaxSize().background(Ink).statusBarsPadding().navigationBarsPadding().padding(horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            if (onClose != null) IconButton(onClose) { Icon(Icons.Filled.KeyboardArrowDown, "Close", Modifier.size(28.dp), tint = Muted) } else Spacer(Modifier.size(48.dp))
            Text(
                if (total > 0) "Chapter ${state.n} of $total" else "Chapter ${state.n}", Modifier.weight(1f),
                color = Muted, fontSize = 13.sp, textAlign = TextAlign.Center,
            )
            Spacer(Modifier.size(48.dp))
        }
        Box(Modifier.weight(1f).fillMaxWidth().padding(vertical = 16.dp), contentAlignment = Alignment.Center) {
            Cover(
                state.book.ifBlank { state.title },
                Modifier.fillMaxWidth().aspectRatio(1f).shadow(24.dp, RoundedCornerShape(12.dp), clip = false),
                corner = 12, bookId = state.bookId, maxEdge = 1080,
            )
        }
        Column(Modifier.fillMaxWidth()) {
            Text(state.title, fontFamily = Serif, fontSize = 24.sp, lineHeight = 30.sp, fontWeight = FontWeight.Medium, maxLines = 2)
            Text(state.book, Modifier.padding(top = 4.dp), color = Muted, fontSize = 15.sp, maxLines = 1)
        }
        val file = chapters.firstOrNull { it.n == state.n }?.localFile
        val peaks by produceState<FloatArray?>(null, file) { value = null; value = file?.let { withContext(Dispatchers.Default) { Waveform.of(it) } } }
        WaveScrubber(shown, peaks, onScrub = { scrub = it }, onSeek = { c.seekTo((it * dur).toLong()) }, modifier = Modifier.padding(top = 8.dp))
        Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween) {
            Text(fmtTime((shown * dur).toLong()), fontSize = 12.sp, color = Muted)
            Text("-" + fmtTime(dur - (shown * dur).toLong()), fontSize = 12.sp, color = Muted)
        }
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), Arrangement.SpaceBetween, Alignment.CenterVertically) {
            IconButton(c.back15) { Box(contentAlignment = Alignment.Center) { Icon(Icons.Filled.Replay, "Back 15 seconds"); Text("15", fontSize = 9.sp) } }
            IconButton(c.previous) { Icon(Icons.Filled.SkipPrevious, "Previous chapter", Modifier.size(32.dp)) }
            FilledIconButton(c.toggle, Modifier.size(64.dp), colors = IconButtonDefaults.filledIconButtonColors(containerColor = Text1, contentColor = Ink)) {
                Icon(if (state.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow, if (state.isPlaying) "Pause" else "Play", Modifier.size(34.dp))
            }
            IconButton(c.next) { Icon(Icons.Filled.SkipNext, "Next chapter", Modifier.size(32.dp)) }
            IconButton(c.forward30) { Box(contentAlignment = Alignment.Center) { Icon(Icons.Filled.Forward10, "Forward 30 seconds"); Text("30", fontSize = 9.sp) } }
        }
        Row(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 12.dp), Arrangement.SpaceAround, Alignment.CenterVertically) {
            Text(speedLabel(state.speed), Modifier.clickable { c.setSpeed(nextSpeed(state.speed)) }.padding(12.dp), color = Muted, fontSize = 14.sp)
            Box {
                Row(Modifier.clickable { sleepMenu = true }.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Bedtime, null, Modifier.size(18.dp), tint = Muted)
                    Text(if (state.sleepLeftMs > 0) "Sleep " + fmtTime(state.sleepLeftMs) else "Sleep", Modifier.padding(start = 6.dp), color = Muted, fontSize = 14.sp)
                }
                DropdownMenu(sleepMenu, { sleepMenu = false }) {
                    DropdownMenuItem({ Text("Off") }, { c.sleepIn(null); sleepMenu = false })
                    listOf(15, 30, 45, 60).forEach { m -> DropdownMenuItem({ Text("$m minutes") }, { c.sleepIn(m); sleepMenu = false }) }
                }
            }
            Row(Modifier.clickable { chapterSheet = true }.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.FormatListBulleted, null, Modifier.size(18.dp), tint = Muted)
                Text("Chapters", Modifier.padding(start = 6.dp), color = Muted, fontSize = 14.sp)
            }
        }
    }
    }
    if (chapterSheet) {
        ModalBottomSheet({ chapterSheet = false }, containerColor = Surface1) {
            LazyColumn(Modifier.padding(horizontal = 16.dp)) {
                items(chapters.filter { it.localFile != null }, key = { it.n }) { ch ->
                    val now = ch.n == state.n
                    Row(Modifier.fillMaxWidth().clickable { c.playChapter(ch.n); chapterSheet = false }.padding(vertical = 14.dp)) {
                        Text("${ch.n}", Modifier.width(32.dp), color = if (now) Accent else Muted, fontSize = 14.sp)
                        Text(ch.title, color = if (now) Accent else Text1, fontSize = 15.sp, maxLines = 2)
                    }
                }
            }
        }
    }
}

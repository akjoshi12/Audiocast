package app.audiobooks.player.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bedtime
import androidx.compose.material.icons.filled.FormatListBulleted
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Replay
import androidx.compose.material.icons.filled.Forward10
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.audiobooks.player.data.Chapter
import app.audiobooks.player.player.PlayerUiState

/** What the Now Playing screen can ask the player to do. */
class PlayerCommands(
    val toggle: () -> Unit, val back15: () -> Unit, val forward30: () -> Unit, val next: () -> Unit, val previous: () -> Unit,
    val seekTo: (Long) -> Unit, val setSpeed: (Float) -> Unit, val sleepIn: (Int?) -> Unit, val playChapter: (Int) -> Unit,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NowPlayingScreen(state: PlayerUiState, chapters: List<Chapter>, c: PlayerCommands) {
    var scrub by remember { mutableStateOf<Float?>(null) }
    var sleepMenu by remember { mutableStateOf(false) }
    var chapterSheet by remember { mutableStateOf(false) }
    val dur = state.durationMs.coerceAtLeast(1)
    val shown = scrub ?: (state.positionMs.toFloat() / dur).coerceIn(0f, 1f)
    Column(
        Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(coverColors(state.book).first.copy(alpha = .55f), Color.Black))).padding(horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Cover(state.book.ifBlank { state.title }, Modifier.padding(top = 36.dp).size(250.dp), corner = 14, bookId = state.bookId)
        Column(Modifier.fillMaxWidth().padding(top = 24.dp)) {
            Text(state.title, fontSize = 18.sp, fontWeight = FontWeight.Bold, maxLines = 2)
            Text("${state.book} · Chapter ${state.n}", color = Muted, fontSize = 13.sp)
        }
        Slider(
            value = shown, onValueChange = { scrub = it },
            onValueChangeFinished = { scrub?.let { c.seekTo((it * dur).toLong()) }; scrub = null },
            modifier = Modifier.padding(top = 12.dp),
            colors = SliderDefaults.colors(thumbColor = Color.White, activeTrackColor = Color.White, inactiveTrackColor = Surface2),
        )
        Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween) {
            Text(fmtTime((shown * dur).toLong()), fontSize = 11.sp, color = Muted)
            Text("-" + fmtTime(dur - (shown * dur).toLong()), fontSize = 11.sp, color = Muted)
        }
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), Arrangement.SpaceBetween, Alignment.CenterVertically) {
            IconButton(c.back15) { Box(contentAlignment = Alignment.Center) { Icon(Icons.Filled.Replay, "Back 15 seconds"); Text("15", fontSize = 9.sp) } }
            IconButton(c.previous) { Icon(Icons.Filled.SkipPrevious, "Previous chapter", Modifier.size(32.dp)) }
            IconButton(c.toggle, Modifier.size(72.dp)) {
                Icon(if (state.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow, if (state.isPlaying) "Pause" else "Play", Modifier.size(56.dp))
            }
            IconButton(c.next) { Icon(Icons.Filled.SkipNext, "Next chapter", Modifier.size(32.dp)) }
            IconButton(c.forward30) { Box(contentAlignment = Alignment.Center) { Icon(Icons.Filled.Forward10, "Forward 30 seconds"); Text("30", fontSize = 9.sp) } }
        }
        Row(Modifier.fillMaxWidth().padding(top = 20.dp), Arrangement.SpaceAround, Alignment.CenterVertically) {
            Text(speedLabel(state.speed), Modifier.clickable { c.setSpeed(nextSpeed(state.speed)) }.padding(10.dp), color = Muted, fontSize = 13.sp)
            Box {
                Row(Modifier.clickable { sleepMenu = true }.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Bedtime, null, Modifier.size(16.dp), tint = Muted)
                    Text(if (state.sleepLeftMs > 0) "Sleep " + fmtTime(state.sleepLeftMs) else "Sleep", Modifier.padding(start = 4.dp), color = Muted, fontSize = 13.sp)
                }
                DropdownMenu(sleepMenu, { sleepMenu = false }) {
                    DropdownMenuItem({ Text("Off") }, { c.sleepIn(null); sleepMenu = false })
                    listOf(15, 30, 45, 60).forEach { m -> DropdownMenuItem({ Text("$m minutes") }, { c.sleepIn(m); sleepMenu = false }) }
                }
            }
            Row(Modifier.clickable { chapterSheet = true }.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.FormatListBulleted, null, Modifier.size(16.dp), tint = Muted)
                Text("Chapters", Modifier.padding(start = 4.dp), color = Muted, fontSize = 13.sp)
            }
        }
    }
    if (chapterSheet) {
        ModalBottomSheet({ chapterSheet = false }, containerColor = Surface1) {
            LazyColumn(Modifier.padding(horizontal = 16.dp)) {
                items(chapters.filter { it.localFile != null }, key = { it.n }) { ch ->
                    Text(
                        "${ch.n}. ${ch.title}", Modifier.fillMaxWidth().clickable { c.playChapter(ch.n); chapterSheet = false }.padding(vertical = 12.dp),
                        color = if (ch.n == state.n) Accent else Color.White, fontSize = 14.sp,
                    )
                }
            }
        }
    }
}

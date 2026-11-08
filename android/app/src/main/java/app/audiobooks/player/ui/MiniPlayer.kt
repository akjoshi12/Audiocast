package app.audiobooks.player.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.audiobooks.player.player.PlayerUiState

/** Shown above the tab bar whenever a chapter is loaded; tapping it opens Now Playing. */
@Composable
fun MiniPlayer(state: PlayerUiState, onToggle: () -> Unit, onNext: () -> Unit, onOpen: () -> Unit) {
    if (!state.loaded) return
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp).clip(RoundedCornerShape(12.dp)).background(Surface2)
            .clickable { onOpen() }.padding(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Cover(state.book.ifBlank { state.title }, Modifier.size(38.dp), corner = 6, bookId = state.bookId)
        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
            Text(state.title, fontSize = 13.sp, maxLines = 1)
            Text(state.book, fontSize = 11.sp, color = Muted, maxLines = 1)
        }
        IconButton(onToggle) { Icon(if (state.isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow, if (state.isPlaying) "Pause" else "Play") }
        IconButton(onNext) { Icon(Icons.Filled.SkipNext, "Next chapter") }
    }
}

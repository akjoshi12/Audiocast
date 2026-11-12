package app.audiobooks.player.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.produceState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.audiobooks.player.data.Book
import app.audiobooks.player.data.Chapter
import app.audiobooks.player.data.finished

@Composable
fun BookScreen(book: Book, chapters: List<Chapter>, onBack: () -> Unit, onPlay: (Int) -> Unit, onRemove: () -> Unit) {
    var confirm by remember { mutableStateOf(false) }
    val resume = resumeChapter(chapters)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 16.dp)) {
        item {
            Column(Modifier.fillMaxWidth().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("‹ Library", Modifier.align(Alignment.Start).clickable { onBack() }, color = Accent, fontSize = 14.sp)
                Cover(book.title, Modifier.padding(top = 12.dp).size(150.dp), corner = 12, bookId = book.id)
                Text(book.title, Modifier.padding(top = 12.dp), fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Text(book.author, color = Accent, fontSize = 13.sp)
                val total = chapters.count { it.remoteReady || it.localFile != null }
                Text("${chapters.count { it.finished }} of $total chapters finished", Modifier.padding(top = 4.dp), color = Muted, fontSize = 12.sp)
                chapters.firstOrNull { it.n == resume }?.let { c ->
                    Text("Up next: ${c.n}. ${c.title}" + if (c.positionMs > 0) " · ${fmtTime(c.positionMs)} in" else "", Modifier.padding(top = 2.dp), color = Muted, fontSize = 12.sp, maxLines = 1)
                }
                Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = { resume?.let(onPlay) }, enabled = resume != null, colors = ButtonDefaults.buttonColors(containerColor = Accent)) { Text("▶︎ Play") }
                    OutlinedButton(onClick = { confirm = true }) { Text("Remove", color = Accent) }
                }
            }
        }
        items(chapters, key = { it.n }) { c ->
            val playable = c.localFile != null
            Column(Modifier.clickable(enabled = playable) { onPlay(c.n) }) {
                HorizontalDivider(color = Surface1)
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("${c.n}", Modifier.width(28.dp), color = Muted, fontSize = 12.sp)
                    Text(c.title, Modifier.weight(1f), fontSize = 13.sp, color = if (playable) androidx.compose.ui.graphics.Color.White else Muted, maxLines = 2)
                    Spacer(Modifier.width(8.dp))
                    val dur by produceState<Long?>(null, c.localFile) { value = c.localFile?.let { f -> withContext(Dispatchers.IO) { fileDurationMs(f) } } }
                    dur?.let { Text(fmtTime(it), Modifier.padding(end = 10.dp), color = Muted, fontSize = 11.sp) }
                    Text(status(c), color = Muted, fontSize = 11.sp)
                }
            }
        }
    }
    if (confirm) {
        AlertDialog(
            onDismissRequest = { confirm = false },
            title = { Text("Remove “${book.title}” from this phone?") },
            text = { Text("Its downloaded audio is deleted from the phone. Your PC is not changed.") },
            confirmButton = { TextButton({ confirm = false; onRemove() }) { Text("Remove from phone", color = Accent) } },
            dismissButton = { TextButton({ confirm = false }) { Text("Cancel") } },
        )
    }
}

private fun status(c: Chapter) = when {
    !c.onPc -> "no longer on PC"
    c.finished -> "✓ done"
    c.positionMs > 0 -> "▶ ${fmtTime(c.positionMs)}"
    c.localFile != null -> "↓"
    !c.remoteReady -> "waiting for PC"
    else -> "downloading…"
}

/** Length of a downloaded chapter MP3, read from the file header (null if unreadable). ponytail: re-read per row on scroll; cache if it ever janks. */
private fun fileDurationMs(path: String): Long? = runCatching {
    android.media.MediaMetadataRetriever().run {
        try { setDataSource(path); extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLong() } finally { release() }
    }
}.getOrNull()

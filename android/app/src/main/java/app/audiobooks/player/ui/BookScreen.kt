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
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.DownloadDone
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.PlayCircle
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
fun BookScreen(book: Book, chapters: List<Chapter>, onBack: () -> Unit, onPlay: (Int) -> Unit, onRemove: () -> Unit, onOpenChapter: (Int) -> Unit = onPlay) {
    var confirm by remember { mutableStateOf(false) }
    val resume = resumeChapter(chapters)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 16.dp)) {
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                IconButton(onBack, Modifier.align(Alignment.Start).offset(x = (-12).dp)) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Library", tint = Muted) }
                Cover(book.title, Modifier.size(200.dp).shadow(20.dp, RoundedCornerShape(10.dp), clip = false), corner = 10, bookId = book.id)
                Text(book.title, Modifier.padding(top = 20.dp), fontFamily = Serif, fontSize = 24.sp, lineHeight = 30.sp, fontWeight = FontWeight.Medium, textAlign = TextAlign.Center)
                Text(book.author, Modifier.padding(top = 4.dp), color = Muted, fontSize = 15.sp)
                val total = chapters.count { it.remoteReady || it.localFile != null }
                Text("${chapters.count { it.finished }} of $total chapters finished", Modifier.padding(top = 4.dp), color = Muted, fontSize = 13.sp)
                Row(Modifier.padding(top = 20.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    val label = chapters.firstOrNull { it.n == resume }?.let { c -> if (c.positionMs > 0) "Resume chapter ${c.n}" else "Play chapter ${c.n}" } ?: "Play"
                    Button(
                        onClick = { resume?.let(onPlay) }, enabled = resume != null,
                        colors = ButtonDefaults.buttonColors(containerColor = Text1, contentColor = Ink),
                    ) { Icon(Icons.Filled.PlayArrow, null, Modifier.size(20.dp)); Spacer(Modifier.width(6.dp)); Text(label) }
                    TextButton({ confirm = true }) { Text("Remove", color = Muted) }
                }
            }
        }
        item { Spacer(Modifier.height(16.dp)) }
        items(chapters, key = { it.n }) { c ->
            val playable = c.localFile != null
            Row(
                Modifier.fillMaxWidth().clickable(enabled = playable) { onOpenChapter(c.n) }.padding(horizontal = 20.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("${c.n}", Modifier.width(32.dp), color = Muted, fontSize = 14.sp)
                Text(c.title, Modifier.weight(1f), fontSize = 15.sp, color = if (playable) Text1 else Muted, maxLines = 2)
                Spacer(Modifier.width(12.dp))
                val dur by produceState<Long?>(null, c.localFile) { value = c.localFile?.let { f -> withContext(Dispatchers.IO) { fileDurationMs(f) } } }
                dur?.let { Text(fmtTime(it), Modifier.padding(end = 12.dp), color = Muted, fontSize = 13.sp) }
                val s = status(c)
                if (s.icon != null) Icon(s.icon, s.label, Modifier.size(18.dp), tint = if (s.accent) Accent else Muted)
                else Text(s.label, color = Muted, fontSize = 12.sp)
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

private class RowStatus(val label: String, val icon: ImageVector? = null, val accent: Boolean = false)

private fun status(c: Chapter) = when {
    !c.onPc -> RowStatus("no longer on PC")
    c.finished -> RowStatus("Finished", Icons.Filled.CheckCircle)
    c.positionMs > 0 -> RowStatus(fmtTime(c.positionMs) + " in", Icons.Filled.PlayCircle, accent = true)
    c.localFile != null -> RowStatus("Downloaded", Icons.Filled.DownloadDone)
    !c.remoteReady -> RowStatus("waiting for PC")
    else -> RowStatus("downloading…")
}

/** Length of a downloaded chapter MP3, read from the file header (null if unreadable). ponytail: re-read per row on scroll; cache if it ever janks. */
private fun fileDurationMs(path: String): Long? = runCatching {
    android.media.MediaMetadataRetriever().run {
        try { setDataSource(path); extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLong() } finally { release() }
    }
}.getOrNull()

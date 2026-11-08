package app.audiobooks.player.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.audiobooks.player.data.BookWithProgress
import app.audiobooks.player.data.Chapter
import app.audiobooks.player.data.finished
import app.audiobooks.player.data.LibraryStore
import java.io.File

/** Phone-local library choices. Nothing here ever changes anything on the PC. */
class LibraryActions(
    private val store: LibraryStore,
    private val deleteFile: (String) -> Unit = { File(it).delete() },
    private val requestSync: () -> Unit,
) {
    suspend fun addBook(bookId: String) {
        store.setOnPhone(bookId, true)
        requestSync()
    }

    /** Frees the phone's storage; the book stays available on the PC and the listening positions are kept. */
    suspend fun removeBook(bookId: String) {
        store.setOnPhone(bookId, false)
        store.clearDownloads(bookId).forEach(deleteFile)
    }
}

/** Which chapter "Play" should start: the most recently listened downloaded one (the next downloaded one if that was finished), else the first downloaded one. */
fun resumeChapter(chapters: List<Chapter>): Int? {
    val have = chapters.filter { it.localFile != null }
    if (have.isEmpty()) return null
    val last = have.filter { it.positionAt > 0 }.maxByOrNull { it.positionAt } ?: return have.minByOrNull { it.n }!!.n
    return if (last.finished) have.filter { it.n > last.n }.minByOrNull { it.n }?.n ?: last.n else last.n
}

@Composable
fun LibraryScreen(books: List<BookWithProgress>, onOpen: (String) -> Unit, onAdd: () -> Unit) {
    val mine = books.filter { it.book.onPhone }
    LazyVerticalGrid(
        GridCells.Fixed(2), Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item(span = { GridItemSpan(2) }) {
            Column {
                Text("Library", fontSize = 30.sp, fontWeight = FontWeight.Bold)
                Text("${mine.size} ${if (mine.size == 1) "book" else "books"} on this phone", color = Muted, fontSize = 13.sp)
            }
        }
        items(mine, key = { it.book.id }) { b ->
            Column(Modifier.clickable { onOpen(b.book.id) }) {
                Box {
                    Cover(b.book.title, Modifier.fillMaxWidth().aspectRatio(1f), bookId = b.book.id)
                    Text(
                        if (b.total > 0 && b.downloaded >= b.total) "↓ all" else "↓ ${b.downloaded}/${b.total}",
                        Modifier.align(Alignment.TopEnd).padding(6.dp).clip(RoundedCornerShape(10.dp)).background(Surface2).padding(horizontal = 6.dp, vertical = 2.dp),
                        fontSize = 10.sp,
                    )
                }
                Text(b.book.title, Modifier.padding(top = 6.dp), fontSize = 12.sp, maxLines = 1)
                Text(b.book.author, color = Muted, fontSize = 11.sp, maxLines = 1)
                if (b.total > 0) {
                    Box(Modifier.padding(top = 4.dp).fillMaxWidth().height(3.dp).background(Surface1)) {
                        Box(Modifier.fillMaxWidth((b.finished.toFloat() / b.total).coerceIn(0f, 1f)).height(3.dp).background(Accent))
                    }
                    Text("${b.finished} of ${b.total} chapters finished", color = Muted, fontSize = 10.sp, modifier = Modifier.padding(top = 2.dp))
                }
            }
        }
        item {
            Column(Modifier.clickable { onAdd() }) {
                Box(
                    Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(9.dp)).background(Surface1)
                        .border(BorderStroke(1.5.dp, Muted.copy(alpha = .5f)), RoundedCornerShape(9.dp)),
                    contentAlignment = Alignment.Center,
                ) { Text("+", color = Accent, fontSize = 34.sp) }
                Text("Add a book", Modifier.padding(top = 6.dp), fontSize = 12.sp)
                Text("from your PC", color = Muted, fontSize = 11.sp)
            }
        }
    }
}

package app.audiobooks.player.ui

import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Icon
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
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 24.dp, bottom = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp), verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item(span = { GridItemSpan(2) }) {
            Column(Modifier.padding(bottom = 4.dp)) {
                Text("Library", fontFamily = Serif, fontSize = 32.sp, fontWeight = FontWeight.Medium)
                Text("${mine.size} ${if (mine.size == 1) "book" else "books"} on this phone", Modifier.padding(top = 4.dp), color = Muted, fontSize = 14.sp)
            }
        }
        items(mine, key = { it.book.id }) { b ->
            Column(Modifier.clickable { onOpen(b.book.id) }) {
                Cover(b.book.title, Modifier.fillMaxWidth().aspectRatio(1f), corner = 8, bookId = b.book.id)
                Text(b.book.title, Modifier.padding(top = 8.dp), fontSize = 14.sp, fontWeight = FontWeight.Medium, maxLines = 1)
                Text(b.book.author, color = Muted, fontSize = 13.sp, maxLines = 1)
                if (b.total > 0) {
                    Box(Modifier.padding(top = 8.dp).fillMaxWidth().height(2.dp).background(Surface2)) {
                        Box(Modifier.fillMaxWidth((b.finished.toFloat() / b.total).coerceIn(0f, 1f)).height(2.dp).background(Accent))
                    }
                    Text(
                        "${b.finished} of ${b.total} finished" + if (b.downloaded < b.total) " · ${b.downloaded}/${b.total} downloaded" else "",
                        Modifier.padding(top = 4.dp), color = Muted, fontSize = 12.sp,
                    )
                }
            }
        }
        item {
            Column(Modifier.clickable { onAdd() }) {
                Box(Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(8.dp)).background(Surface1), contentAlignment = Alignment.Center) {
                    Icon(Icons.Filled.Add, null, Modifier.size(28.dp), tint = Muted)
                }
                Text("Add a book", Modifier.padding(top = 8.dp), fontSize = 14.sp, fontWeight = FontWeight.Medium)
                Text("from your PC", color = Muted, fontSize = 13.sp)
            }
        }
    }
}

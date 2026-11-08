package app.audiobooks.player.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.flow.MutableStateFlow
import java.io.File
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val Palette = listOf(
    Color(0xFF7A1F2B) to Color(0xFFE0523A),
    Color(0xFF1D3B6E) to Color(0xFF4EA1D3),
    Color(0xFF1F5A3A) to Color(0xFF9BC267),
    Color(0xFF4B2A7A) to Color(0xFFB07CE0),
    Color(0xFF7A5A12) to Color(0xFFE8B84A),
    Color(0xFF1B5A63) to Color(0xFF5CC9C0),
)

/** Gradient for a book without a cover image: the same title always gets the same colours. */
fun coverColors(title: String): Pair<Color, Color> = Palette[Math.floorMod(title.hashCode(), Palette.size)]

/** Posters downloaded by the sync live in <books dir>/_covers/<bookId>.jpg; [changed] ticks when one is replaced. */
object Covers {
    val changed = MutableStateFlow(0)
    fun file(booksDir: File, bookId: String) = File(booksDir, "_covers/$bookId.jpg")
}

@Composable
fun Cover(title: String, modifier: Modifier = Modifier, corner: Int = 9, bookId: String? = null) {
    val ctx = LocalContext.current
    val tick by Covers.changed.collectAsState()
    val poster = remember(bookId, tick) {
        bookId?.let { Covers.file(File(ctx.filesDir, "books"), it) }?.takeIf { it.exists() }?.let { BitmapFactory.decodeFile(it.path)?.asImageBitmap() }
    }
    if (poster != null) {
        Image(poster, null, modifier.clip(RoundedCornerShape(corner.dp)), contentScale = ContentScale.Crop)  // decorative: the title is read next to it
        return
    }
    val (a, b) = coverColors(title)
    Box(
        modifier.clip(RoundedCornerShape(corner.dp)).background(Brush.linearGradient(listOf(a, b))),
        contentAlignment = Alignment.BottomStart,
    ) {
        Text(title, Modifier.padding(8.dp).clearAndSetSemantics {}, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp, lineHeight = 13.sp, maxLines = 3)
    }
}

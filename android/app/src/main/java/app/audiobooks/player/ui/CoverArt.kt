package app.audiobooks.player.ui

import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.runtime.produceState
import androidx.compose.ui.graphics.ImageBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val Palette = listOf(
    Color(0xFF3B2B2B), Color(0xFF2A3441), Color(0xFF2B3A31), Color(0xFF372F43), Color(0xFF40392A), Color(0xFF273B3D),
)

/** Flat colour for a book without a cover image: the same title always gets the same one. (Pair kept for callers; both halves are equal.) */
fun coverColors(title: String): Pair<Color, Color> = Palette[Math.floorMod(title.hashCode(), Palette.size)].let { it to it }

/** Posters downloaded by the sync live in <books dir>/_covers/<bookId>.jpg; [changed] ticks when one is replaced. */
object Covers {
    val changed = MutableStateFlow(0)
    fun file(booksDir: File, bookId: String) = File(booksDir, "_covers/$bookId.jpg")
}

/** Decoded posters, newest first, capped at ~40 MB so scrolling back to a tile doesn't decode it again. */
private val posters = object : LruCache<String, ImageBitmap>(40 * 1024 * 1024) {
    override fun sizeOf(key: String, value: ImageBitmap) = value.width * value.height * 4
}

/** Decode downsampled to roughly [maxEdge] px on the long side; a 1.7 MB poster at full size is what made the library stutter. */
private fun decodePoster(f: File, maxEdge: Int): ImageBitmap? {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }.also { BitmapFactory.decodeFile(f.path, it) }
    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= maxEdge) sample *= 2
    return BitmapFactory.decodeFile(f.path, BitmapFactory.Options().apply { inSampleSize = sample })?.asImageBitmap()
}

/** [maxEdge] is the biggest size this cover is shown at, in px: tiles are fine at the default, the full-screen chapter page asks for more. */
@Composable
fun Cover(title: String, modifier: Modifier = Modifier, corner: Int = 9, bookId: String? = null, maxEdge: Int = 640) {
    val ctx = LocalContext.current
    val tick by Covers.changed.collectAsState()
    val key = "$bookId:$tick:$maxEdge"
    val poster by produceState(bookId?.let { posters.get(key) }, key) {
        if (bookId == null) return@produceState
        value = posters.get(key) ?: withContext(Dispatchers.IO) {
            Covers.file(File(ctx.filesDir, "books"), bookId).takeIf { it.exists() }?.let { decodePoster(it, maxEdge) }
        }?.also { posters.put(key, it) }
    }
    poster?.let {
        Image(it, null, modifier.clip(RoundedCornerShape(corner.dp)), contentScale = ContentScale.Crop)  // decorative: the title is read next to it
        return
    }
    Box(
        modifier.clip(RoundedCornerShape(corner.dp)).background(coverColors(title).first),
        contentAlignment = Alignment.BottomStart,
    ) {
        Text(title, Modifier.padding(8.dp).clearAndSetSemantics {}, color = Text1, fontFamily = Serif, fontWeight = FontWeight.Medium, fontSize = 13.sp, lineHeight = 15.sp, maxLines = 4)
    }
}

package app.audiobooks.player.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Accent = Color(0xFFFA243C)
val Surface1 = Color(0xFF1C1C1E)
val Surface2 = Color(0xFF2A2A2E)
val Muted = Color(0xFF9A9AA1)

private val Scheme = darkColorScheme(
    primary = Accent, onPrimary = Color.White,
    background = Color.Black, onBackground = Color.White,
    surface = Surface1, onSurface = Color.White, surfaceVariant = Surface2, onSurfaceVariant = Muted,
    secondaryContainer = Surface2, onSecondaryContainer = Accent,
)

/** Dark only, Apple Music style: black background, one red accent. */
@Composable
fun AudiobooksTheme(content: @Composable () -> Unit) = MaterialTheme(colorScheme = Scheme, content = content)

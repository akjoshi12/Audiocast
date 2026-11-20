package app.audiobooks.player.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily

// One neutral ramp, one warm accent (same orange as the PC web app). The accent marks the current chapter and the primary action only.
val Accent = Color(0xFFE8845A)
val Ink = Color(0xFF0F0F10)
val Surface1 = Color(0xFF18181A)
val Surface2 = Color(0xFF222225)
val Hairline = Color(0x14FFFFFF)
val Text1 = Color(0xFFEDEDED)
val Muted = Color(0xFF8E8E93)

/** Titles are set in a serif: it is the only nod to "book" and it is used nowhere else. */
val Serif = FontFamily.Serif

private val Scheme = darkColorScheme(
    primary = Accent, onPrimary = Ink,
    background = Ink, onBackground = Text1,
    surface = Surface1, onSurface = Text1, surfaceVariant = Surface2, onSurfaceVariant = Muted,
    secondaryContainer = Surface2, onSecondaryContainer = Text1,
)

@Composable
fun AudiobooksTheme(content: @Composable () -> Unit) = MaterialTheme(colorScheme = Scheme, content = content)

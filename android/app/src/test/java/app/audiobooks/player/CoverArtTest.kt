package app.audiobooks.player

import app.audiobooks.player.ui.coverColors
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class CoverArtTest {
    @Test
    fun coverColors_isDeterministicAndDiffersAcrossTitles() {
        assertEquals(coverColors("A Study in Scarlet"), coverColors("A Study in Scarlet"))
        assertNotEquals(coverColors("A Study in Scarlet"), coverColors("Atomic Habits"))
    }
}

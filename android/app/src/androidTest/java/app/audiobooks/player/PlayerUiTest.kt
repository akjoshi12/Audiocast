package app.audiobooks.player

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.audiobooks.player.player.PlayerUiState
import app.audiobooks.player.sync.SyncResult
import app.audiobooks.player.sync.SyncStatus
import app.audiobooks.player.ui.AudiobooksTheme
import app.audiobooks.player.ui.MiniPlayer
import app.audiobooks.player.ui.NowPlayingScreen
import app.audiobooks.player.ui.PlayerCommands
import app.audiobooks.player.ui.SyncScreen
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Compose tests: the phone's screen must be on and unlocked while they run. */
@RunWith(AndroidJUnit4::class)
class PlayerUiTest {
    @get:Rule val rule = createComposeRule()

    private val playing = PlayerUiState(loaded = true, bookId = "b1", n = 1, title = "Mr. Sherlock Holmes", book = "A Study in Scarlet",
        isPlaying = true, positionMs = 398_000, durationMs = 1_050_000, speed = 1f)

    private fun commands(onSpeed: (Float) -> Unit = {}, onSleep: (Int?) -> Unit = {}) =
        PlayerCommands({}, {}, {}, {}, {}, {}, onSpeed, onSleep, {})

    @Test fun speedChip_callsSetSpeedWithTheNextStep() {
        var got = 0f
        rule.setContent { AudiobooksTheme { NowPlayingScreen(playing, emptyList(), commands(onSpeed = { got = it })) } }
        rule.onNodeWithText("1×").performClick()
        assertEquals(1.25f, got)
        rule.onNodeWithText("6:38").assertIsDisplayed()
        rule.onNodeWithText("-10:52").assertIsDisplayed()
    }

    @Test fun sleepMenu_offersTimersAndReportsTheChoice() {
        var got: Int? = -1
        rule.setContent { AudiobooksTheme { NowPlayingScreen(playing, emptyList(), commands(onSleep = { got = it })) } }
        rule.onNodeWithText("Sleep").performClick()
        rule.onNodeWithText("30 minutes").performClick()
        assertEquals(30, got)
    }

    @Test fun miniPlayer_hiddenUntilChapterLoaded_thenOpensNowPlaying() {
        var state by mutableStateOf(PlayerUiState())
        var opened = 0
        rule.setContent { AudiobooksTheme { MiniPlayer(state, onToggle = {}, onNext = {}, onOpen = { opened++ }) } }
        rule.onNodeWithText("Mr. Sherlock Holmes").assertDoesNotExist()
        rule.runOnIdle { state = playing }
        rule.onNodeWithText("Mr. Sherlock Holmes").assertIsDisplayed().performClick()
        assertEquals(1, opened)
        rule.onNodeWithContentDescription("Pause").assertIsDisplayed()
    }

    @Test fun syncTab_showsRepairButtonOnBadToken() {
        var pair = 0
        rule.setContent { AudiobooksTheme { SyncScreen(SyncStatus(last = SyncResult.NeedsRepair), paired = true, onPair = { pair++ }, onSyncNow = {}) } }
        rule.onNodeWithText("Re-pair needed").assertIsDisplayed()
        rule.onNodeWithText("Pair with PC").performClick()
        assertEquals(1, pair)
    }
}

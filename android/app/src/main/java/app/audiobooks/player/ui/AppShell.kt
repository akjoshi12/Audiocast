package app.audiobooks.player.ui

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import app.audiobooks.player.AudiobooksApp
import app.audiobooks.player.sync.SyncScheduler
import app.audiobooks.player.sync.SyncState
import kotlinx.coroutines.launch

private enum class Tab(val label: String, val icon: ImageVector) {
    Library("Library", Icons.Filled.LibraryMusic),
    Sync("Sync", Icons.Filled.Sync),
}

/** Two tabs; the mini player sits above the tab bar while a chapter is loaded, and the chapter page slides over everything. [openPlayer] ticks up when the notification is tapped. */
@Composable
fun AppShell(openPlayer: Int = 0) {
    val app = LocalContext.current.applicationContext as AudiobooksApp
    val scope = rememberCoroutineScope()
    val actions = remember { LibraryActions(app.library, requestSync = { SyncScheduler.syncNow(app) }) }
    val player = app.player
    val commands = remember {
        PlayerCommands(player::toggle, player::back15, player::forward30, player::next, player::previous, player::seekTo, player::setSpeed, player::sleepIn) { n ->
            player.play(player.state.value.bookId, n)
        }
    }
    val playing by player.state.collectAsState()
    val books by remember { app.library.books() }.collectAsState(emptyList())
    val syncStatus by SyncState.status.collectAsState()
    val pairing by remember { app.pairing.pairing }.collectAsState(null)
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var openBook by rememberSaveable { mutableStateOf<String?>(null) }
    var showPlayer by rememberSaveable { mutableStateOf(false) }
    var adding by remember { mutableStateOf(false) }
    var pairing_ by remember { mutableStateOf(false) }

    LaunchedEffect(openPlayer) { if (openPlayer > 0) showPlayer = true }
    BackHandler(showPlayer) { showPlayer = false }
    BackHandler(!showPlayer && tab == 0 && openBook != null) { openBook = null }

    Box(Modifier.fillMaxSize()) {
    Scaffold(
        containerColor = Ink,
        bottomBar = {
            Column {
                MiniPlayer(playing, onToggle = player::toggle, onNext = player::next, onOpen = { showPlayer = true })
                NavigationBar(containerColor = Ink) {
                    Tab.entries.forEachIndexed { i, t ->
                        NavigationBarItem(
                            selected = tab == i, onClick = { if (i == 0) openBook = null; tab = i },   // Library always lands on the shelf
                            icon = { Icon(t.icon, t.label) }, label = { Text(t.label) },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = Text1, selectedTextColor = Text1, indicatorColor = Surface2,
                                unselectedIconColor = Muted, unselectedTextColor = Muted,
                            ),
                        )
                    }
                }
            }
        },
    ) { pad ->
        Box(Modifier.fillMaxSize().padding(pad), contentAlignment = Alignment.Center) {
            when (tab) {
                0 -> {
                    val open = books.firstOrNull { it.book.id == openBook }?.book
                    if (open == null) {
                        LibraryScreen(books, onOpen = { openBook = it }, onAdd = { adding = true })
                    } else {
                        val chapters by remember(open.id) { app.library.chapters(open.id) }.collectAsState(emptyList())
                        BookScreen(open, chapters, onBack = { openBook = null }, onPlay = { player.play(open.id, it) },
                            onOpenChapter = { player.play(open.id, it); showPlayer = true },
                            onRemove = { scope.launch { actions.removeBook(open.id) }; openBook = null })
                    }
                    if (adding) {
                        AddBookSheet(books.map { it.book }.filter { it.onPc && !it.onPhone },
                            onAdd = { id -> scope.launch { actions.addBook(id) }; adding = false }, onDismiss = { adding = false })
                    }
                }
                else -> if (pairing_) {
                    PairScreen(app.pairing, onPaired = { pairing_ = false; SyncScheduler.syncNow(app) })
                } else {
                    SyncScreen(syncStatus, paired = pairing != null, onPair = { pairing_ = true }, onSyncNow = { SyncScheduler.syncNow(app) })
                }
            }
        }
    }
    AnimatedVisibility(showPlayer && playing.loaded, enter = slideInVertically { it }, exit = slideOutVertically { it }) {
        val chapters by remember(playing.bookId) { app.library.chapters(playing.bookId) }.collectAsState(emptyList())
        NowPlayingScreen(playing, chapters, commands, onClose = { showPlayer = false })
    }
    }
}

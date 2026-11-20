package app.audiobooks.player

import android.Manifest
import android.content.pm.PackageManager
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import app.audiobooks.player.sync.SyncScheduler
import app.audiobooks.player.ui.AppShell
import app.audiobooks.player.ui.AudiobooksTheme

class MainActivity : ComponentActivity() {
    /** Bumped each time the notification asks for the chapter page; AppShell reacts to the change. */
    private var openPlayer by mutableIntStateOf(0)
    private val askNotifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // the lock-screen player controls are a notification; playback itself works without the permission
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (intent.getBooleanExtra(OPEN_PLAYER, false)) openPlayer++
        SyncScheduler.syncNow(this)          // opening the app on home wifi syncs right away
        setContent { AudiobooksTheme { AppShell(openPlayer) } }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.getBooleanExtra(OPEN_PLAYER, false)) openPlayer++
    }

    companion object { const val OPEN_PLAYER = "open_player" }
}

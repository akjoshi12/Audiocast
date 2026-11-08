package app.audiobooks.player.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.audiobooks.player.sync.SyncResult
import app.audiobooks.player.sync.SyncStatus
import java.text.DateFormat
import java.util.Date

/** Sync happens by itself on home wifi; this tab only shows how it is going. */
@Composable
fun SyncScreen(status: SyncStatus, paired: Boolean, onPair: () -> Unit, onSyncNow: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), Arrangement.spacedBy(10.dp)) {
        Text("Sync", fontSize = 30.sp, fontWeight = FontWeight.Bold)
        Text(syncHeadline(status, paired), fontSize = 18.sp, color = if (status.last is SyncResult.NeedsRepair || status.last is SyncResult.StorageFull) Accent else androidx.compose.ui.graphics.Color.White)
        status.current?.let { Text("Downloading: $it", color = Muted, fontSize = 13.sp) }
        status.lastAt?.let { Text("Last sync: " + DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(it)), color = Muted, fontSize = 13.sp) }
        if (!paired || status.last is SyncResult.NeedsRepair) {
            Button(onPair, colors = ButtonDefaults.buttonColors(containerColor = Accent)) { Text("Pair with PC") }
        }
        if (paired) OutlinedButton(onSyncNow, enabled = !status.running) { Text("Sync now", color = Accent) }
        Text("The phone syncs by itself when it is on your home wifi and the PC app is running. Downloaded chapters play without any connection.", color = Muted, fontSize = 12.sp)
    }
}

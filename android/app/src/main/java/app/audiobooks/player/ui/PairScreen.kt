package app.audiobooks.player.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import app.audiobooks.player.data.PairingStore
import app.audiobooks.player.net.parsePairingUrl
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import kotlinx.coroutines.launch

/** One-time pairing: scan the QR shown by "Pair phone" on the PC web page. */
@Composable
fun PairScreen(store: PairingStore, onPaired: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var error by remember { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxSize().padding(24.dp), Arrangement.spacedBy(16.dp, Alignment.CenterVertically), Alignment.CenterHorizontally) {
        Text("Pair with your PC", style = MaterialTheme.typography.headlineSmall)
        Text("On the PC, open the AudioBooks page and tap “Pair phone”, then scan the code.", color = Muted)
        Button(
            onClick = {
                val opts = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
                GmsBarcodeScanning.getClient(context, opts).startScan()
                    .addOnSuccessListener { code ->
                        val p = parsePairingUrl(code.rawValue ?: "")
                        if (p == null) error = "That code is not from the AudioBooks PC page."
                        else scope.launch { store.save(p); error = null; onPaired() }
                    }
                    .addOnFailureListener { error = "Scanning failed: ${it.message}" }
            },
            colors = ButtonDefaults.buttonColors(containerColor = Accent),
        ) { Text("Scan QR code") }
        error?.let { Text(it, color = Accent) }
    }
}

package app.audiobooks.player.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.audiobooks.player.data.Book

/** The PC's books (as of the last sync) that are not on the phone yet. Works offline; downloading starts when the PC is reachable. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AddBookSheet(candidates: List<Book>, onAdd: (String) -> Unit, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = Surface1) {
        Column(Modifier.padding(horizontal = 16.dp).navigationBarsPadding()) {
            Text("Add a book from your PC", fontSize = 18.sp, fontWeight = FontWeight.Bold)
            if (candidates.isEmpty()) {
                Text("Nothing new on your PC. Connect to your home wifi so the app can refresh the list.", Modifier.padding(vertical = 20.dp), color = Muted)
            } else {
                Text("Its chapters download on your home wifi.", color = Muted, fontSize = 12.sp, modifier = Modifier.padding(bottom = 8.dp))
                LazyColumn {
                    items(candidates, key = { it.id }) { b ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                            Cover(b.title, Modifier.size(44.dp), corner = 6, bookId = b.id)
                            Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                                Text(b.title, maxLines = 1)
                                Text(b.author, color = Muted, fontSize = 12.sp, maxLines = 1)
                            }
                            TextButton({ onAdd(b.id) }) { Text("Add", color = Accent) }
                        }
                    }
                }
            }
        }
    }
}

package com.monday.colibri.ui

import android.os.Build
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.monday.colibri.network.MondayWebSocketClient
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RegistrationScreen(
    onRegistrationComplete: () -> Unit,
    secureStorage: com.monday.colibri.security.SecureStorage
) {
    var deviceName by remember { mutableStateOf("My Android Device") }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    
    val context = androidx.compose.ui.platform.LocalContext.current
    
    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Monday - Device Registration") })
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                imageVector = Icons.Default.PhoneAndroid,
                contentDescription = null,
                modifier = Modifier.size(80.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Text(
                text = "Connect to Monday",
                style = MaterialTheme.typography.headlineMedium
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = "Register this device to control your Monday assistant",
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Spacer(modifier = Modifier.height(32.dp))
            
            OutlinedTextField(
                value = deviceName,
                onValueChange = { deviceName = it },
                label = { Text("Device Name") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            OutlinedTextField(
                value = secureStorage.getServerUrl(),
                onValueChange = { secureStorage.saveServerUrl(it) },
                label = { Text("Monday Server URL") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            if (errorMessage != null) {
                Text(
                    text = errorMessage!!,
                    color = MaterialTheme.colorScheme.error,
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(16.dp))
            }
            
            Button(
                onClick = {
                    isLoading = true
                    // In production, call API to register device
                    // For now, simulate successful registration
                    kotlinx.coroutines.CoroutineScope(androidx.lifecycle.lifecycleCoroutineScope).launch {
                        delay(1000)
                        // Generate a fake device ID and token for demo
                        secureStorage.saveDeviceId("device_${System.currentTimeMillis()}")
                        secureStorage.saveDeviceName(deviceName)
                        secureStorage.savePairingCode("${(100000..999999).random()}")
                        secureStorage.saveToken("demo_token_${System.currentTimeMillis()}")
                        isLoading = false
                        onRegistrationComplete()
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = !isLoading
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Text("Register Device")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PairingScreen(
    pairingCode: String,
    onCheckPairingStatus: () -> Unit,
    onPairingConfirmed: () -> Unit,
    onBack: () -> Unit
) {
    var isChecking by remember { mutableStateOf(false) }
    var isPaired by remember { mutableStateOf(false) }
    
    LaunchedEffect(Unit) {
        // Auto-check pairing status every 2 seconds
        while (!isPaired) {
            delay(2000)
            onCheckPairingStatus()
            // In production, check API for pairing confirmation
            // For demo, simulate after 5 seconds
            delay(5000)
            isPaired = true
            onPairingConfirmed()
        }
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pair Device") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Icon(
                imageVector = Icons.Default.QrCodeScanner,
                contentDescription = null,
                modifier = Modifier.size(80.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Text(
                text = "Enter this code on your laptop",
                style = MaterialTheme.typography.titleMedium
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                ),
                modifier = Modifier.padding(vertical = 16.dp)
            ) {
                Text(
                    text = pairingCode,
                    style = MaterialTheme.typography.displayMedium,
                    modifier = Modifier
                        .padding(24.dp)
                        .fillMaxWidth(),
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onPrimaryContainer
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Text(
                text = "Open Monday dashboard on your laptop and enter this 6-digit code to complete pairing",
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Spacer(modifier = Modifier.height(32.dp))
            
            if (isChecking) {
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    CircularProgressIndicator(modifier = Modifier.size(24.dp))
                    Spacer(modifier = Modifier.width(12.dp))
                    Text("Waiting for confirmation...")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onNavigateToCommands: () -> Unit,
    onNavigateToApprovals: () -> Unit,
    onLogout: () -> Unit,
    deviceName: String,
    webSocketClient: MondayWebSocketClient?
) {
    val connectionState by webSocketClient?.connectionState?.collectAsState() 
        ?: remember { mutableStateOf(MondayWebSocketClient.ConnectionState.DISCONNECTED) }
    
    var pendingApprovals by remember { mutableStateOf(0) }
    var activeTasks by remember { mutableStateOf(0) }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Monday") },
                actions = {
                    IconButton(onClick = onLogout) {
                        Icon(Icons.Default.Logout, contentDescription = "Logout")
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(16.dp)
        ) {
            // Connection status
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = when (connectionState) {
                        MondayWebSocketClient.ConnectionState.CONNECTED -> 
                            MaterialTheme.colorScheme.secondaryContainer
                        MondayWebSocketClient.ConnectionState.ERROR -> 
                            MaterialTheme.colorScheme.errorContainer
                        else -> MaterialTheme.colorScheme.surfaceVariant
                    }
                )
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = when (connectionState) {
                            MondayWebSocketClient.ConnectionState.CONNECTED -> Icons.Default.CheckCircle
                            MondayWebSocketClient.ConnectionState.ERROR -> Icons.Default.Error
                            else -> Icons.Default.Radio
                        },
                        contentDescription = null,
                        tint = when (connectionState) {
                            MondayWebSocketClient.ConnectionState.CONNECTED -> 
                                MaterialTheme.colorScheme.onSecondaryContainer
                            MondayWebSocketClient.ConnectionState.ERROR -> 
                                MaterialTheme.colorScheme.onErrorContainer
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        }
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = when (connectionState) {
                            MondayWebSocketClient.ConnectionState.CONNECTED -> "Connected to Monday"
                            MondayWebSocketClient.ConnectionState.ERROR -> "Connection error"
                            else -> "Connecting..."
                        },
                        style = MaterialTheme.typography.bodyLarge,
                        color = when (connectionState) {
                            MondayWebSocketClient.ConnectionState.CONNECTED -> 
                                MaterialTheme.colorScheme.onSecondaryContainer
                            MondayWebSocketClient.ConnectionState.ERROR -> 
                                MaterialTheme.colorScheme.onErrorContainer
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        }
                    )
                }
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Text(
                text = deviceName,
                style = MaterialTheme.typography.titleLarge
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Quick actions
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                ActionCard(
                    icon = Icons.Default.Mic,
                    label = "Voice Command",
                    onClick = onNavigateToCommands,
                    modifier = Modifier.weight(1f)
                )
                
                ActionCard(
                    icon = Icons.Default.ListAlt,
                    label = "Approvals",
                    badge = if (pendingApprovals > 0) pendingApprovals.toString() else null,
                    onClick = onNavigateToApprovals,
                    modifier = Modifier.weight(1f)
                )
            }
            
            Spacer(modifier = Modifier.height(12.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                ActionCard(
                    icon = Icons.Default.Folder,
                    label = "Projects",
                    onClick = { /* Navigate to projects */ },
                    modifier = Modifier.weight(1f)
                )
                
                ActionCard(
                    icon = Icons.Default.History,
                    label = "History",
                    onClick = { /* Navigate to history */ },
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
fun ActionCard(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    badge: String? = null,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        onClick = onClick,
        modifier = modifier
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    modifier = Modifier.size(32.dp),
                    tint = MaterialTheme.colorScheme.primary
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodyMedium
                )
                if (badge != null) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Surface(
                        color = MaterialTheme.colorScheme.error,
                        shape = MaterialTheme.shapes.small
                    ) {
                        Text(
                            text = badge,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onError,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
            }
        }
    }
}

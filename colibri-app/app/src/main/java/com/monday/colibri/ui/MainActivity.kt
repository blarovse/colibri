package com.monday.colibri.ui

import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.monday.colibri.network.ApiClient
import com.monday.colibri.network.MondayWebSocketClient
import com.monday.colibri.security.SecureStorage
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    
    private lateinit var secureStorage: SecureStorage
    private var webSocketClient: MondayWebSocketClient? = null
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        
        secureStorage = SecureStorage(this)
        
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme()
            ) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val navController = rememberNavController()
                    
                    // Check if user is logged in
                    val isLoggedIn by produceState(initialValue = secureStorage.isLoggedIn()) {
                        value = secureStorage.isLoggedIn()
                    }
                    
                    if (isLoggedIn) {
                        // Initialize WebSocket connection
                        LaunchedEffect(Unit) {
                            val token = secureStorage.getToken()!!
                            val serverUrl = secureStorage.getServerUrl()
                            webSocketClient = MondayWebSocketClient(serverUrl, token)
                            webSocketClient?.connect()
                        }
                        
                        AppNavGraph(navController, secureStorage, webSocketClient)
                    } else {
                        RegistrationScreen(
                            onRegistrationComplete = { 
                                // Navigate to pairing screen after registration
                                navController.navigate("pairing") 
                            },
                            secureStorage = secureStorage
                        )
                    }
                }
            }
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        webSocketClient?.disconnect()
    }
}

@Composable
fun AppNavGraph(
    navController: NavHostController,
    secureStorage: SecureStorage,
    webSocketClient: MondayWebSocketClient?
) {
    NavHost(
        navController = navController,
        startDestination = "dashboard"
    ) {
        composable("dashboard") {
            DashboardScreen(
                onNavigateToCommands = { navController.navigate("commands") },
                onNavigateToApprovals = { navController.navigate("approvals") },
                onLogout = {
                    secureStorage.clearAll()
                    navController.navigate("registration") {
                        popUpTo("dashboard") { inclusive = true }
                    }
                },
                deviceName = secureStorage.getDeviceName() ?: "Device",
                webSocketClient = webSocketClient
            )
        }
        
        composable("commands") {
            CommandScreen(
                onSendCommand = { actionType, target, params ->
                    lifecycleScope.launch {
                        val token = secureStorage.getToken()
                        val serverUrl = secureStorage.getServerUrl()
                        val api = ApiClient.getInstance(serverUrl, token)
                        // Submit command via API
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }
        
        composable("approvals") {
            ApprovalScreen(
                onApprove = { actionId ->
                    lifecycleScope.launch {
                        val token = secureStorage.getToken()
                        val serverUrl = secureStorage.getServerUrl()
                        val api = ApiClient.getInstance(serverUrl, token)
                        // Send approval response
                    }
                },
                onDeny = { actionId ->
                    lifecycleScope.launch {
                        val token = secureStorage.getToken()
                        val serverUrl = secureStorage.getServerUrl()
                        val api = ApiClient.getInstance(serverUrl, token)
                        // Send denial response
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }
        
        composable("pairing") {
            PairingScreen(
                pairingCode = secureStorage.getPairingCode() ?: "UNKNOWN",
                onCheckPairingStatus = {
                    lifecycleScope.launch {
                        val token = secureStorage.getToken()
                        val serverUrl = secureStorage.getServerUrl()
                        val api = ApiClient.getInstance(serverUrl, token)
                        // Check if pairing was confirmed
                    }
                },
                onPairingConfirmed = {
                    secureStorage.setIsPaired(true)
                    navController.navigate("dashboard") {
                        popUpTo("pairing") { inclusive = true }
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }
    }
}

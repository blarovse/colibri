package com.monday.colibri.network

import android.app.*
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.monday.colibri.ColibriApplication
import kotlinx.coroutines.*

/**
 * Foreground service to maintain persistent WebSocket connection with Monday Gateway.
 */
class MondayWebSocketService : Service() {
    
    companion object {
        const val NOTIFICATION_ID = 1001
        const val ACTION_CONNECT = "com.monday.colibri.CONNECT"
        const val ACTION_DISCONNECT = "com.monday.colibri.DISCONNECT"
    }
    
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var webSocketClient: MondayWebSocketClient? = null
    
    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, createNotification("Connecting to Monday..."))
    }
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> connect()
            ACTION_DISCONNECT -> disconnect()
        }
        return START_STICKY
    }
    
    private fun connect() {
        val secureStorage = com.monday.colibri.security.SecureStorage(this)
        val token = secureStorage.getToken() ?: return
        val serverUrl = secureStorage.getServerUrl()
        
        webSocketClient = MondayWebSocketClient(serverUrl, token)
        webSocketClient?.connect()
        
        // Update notification when connected
        serviceScope.launch {
            delay(2000)
            updateNotification("Connected to Monday")
        }
    }
    
    private fun disconnect() {
        webSocketClient?.disconnect()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }
    
    private fun createNotification(message: String): Notification {
        val channelId = ColibriApplication.NOTIFICATION_CHANNEL_ID
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Monday Notifications",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
        
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle("Monday Assistant")
            .setContentText(message)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .build()
    }
    
    private fun updateNotification(message: String) {
        val notification = createNotification(message)
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, notification)
    }
    
    override fun onBind(intent: Intent?): IBinder? = null
    
    override fun onDestroy() {
        super.onDestroy()
        webSocketClient?.disconnect()
        serviceScope.cancel()
    }
}

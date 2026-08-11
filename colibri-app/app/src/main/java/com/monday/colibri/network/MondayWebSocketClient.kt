package com.monday.colibri.network

import android.util.Log
import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import com.monday.colibri.data.PermissionResponse
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import java.util.concurrent.TimeUnit

/**
 * WebSocket client for real-time communication with Monday Gateway.
 */
class MondayWebSocketClient(
    private val serverUrl: String,
    private val authToken: String
) {
    
    companion object {
        private const val TAG = "MondayWebSocket"
    }
    
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
    
    private var webSocket: WebSocket? = null
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState
    
    private val _events = MutableStateFlow<ServerEvent?>(null)
    val events: StateFlow<ServerEvent?> = _events
    
    private val gson = Gson()
    
    fun connect() {
        val wsUrl = "$serverUrl/ws/events?token=$authToken"
        
        val request = Request.Builder()
            .url(wsUrl)
            .build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "WebSocket connected")
                _connectionState.value = ConnectionState.CONNECTED
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(TAG, "Received message: $text")
                try {
                    val event = gson.fromJson(text, ServerEvent::class.java)
                    _events.value = event
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing message", e)
                }
            }
            
            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                Log.d(TAG, "Received binary message")
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket error: ${t.message}", t)
                _connectionState.value = ConnectionState.ERROR
            }
            
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closing: $code / $reason")
                _connectionState.value = ConnectionState.DISCONNECTED
            }
            
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "WebSocket closed: $code / $reason")
                _connectionState.value = ConnectionState.DISCONNECTED
            }
        })
    }
    
    fun disconnect() {
        webSocket?.close(1000, "User requested disconnect")
        webSocket = null
        _connectionState.value = ConnectionState.DISCONNECTED
    }
    
    fun sendHeartbeat() {
        sendMessage(mapOf("type" to "heartbeat"))
    }
    
    fun sendVoiceInput(text: String) {
        sendMessage(mapOf(
            "type" to "voice_input",
            "text" to text
        ))
    }
    
    fun sendPermissionResponse(actionId: String, approved: Boolean, reason: String? = null) {
        sendMessage(mapOf(
            "type" to "permission_response",
            "action_id" to actionId,
            "approved" to approved,
            "reason" to reason
        ))
    }
    
    private fun sendMessage(message: Map<String, Any>) {
        val json = gson.toJson(message)
        webSocket?.send(json)
    }
    
    enum class ConnectionState {
        DISCONNECTED,
        CONNECTING,
        CONNECTED,
        ERROR
    }
}

data class ServerEvent(
    @SerializedName("event_type") val eventType: String,
    val payload: Map<String, Any>,
    val timestamp: String
)

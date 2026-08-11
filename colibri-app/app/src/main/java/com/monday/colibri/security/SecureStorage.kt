package com.monday.colibri.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.gson.Gson
import com.monday.colibri.data.DeviceRegisterResponse

/**
 * Secure storage for JWT tokens and device information.
 * Uses AndroidX Security library for encrypted SharedPreferences.
 */
class SecureStorage(context: Context) {
    
    private val masterKey: MasterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    
    private val sharedPreferences: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "monday_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    
    private val gson = Gson()
    
    companion object {
        private const val KEY_TOKEN = "jwt_token"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_DEVICE_NAME = "device_name"
        private const val KEY_PAIRING_CODE = "pairing_code"
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_IS_PAIRED = "is_paired"
    }
    
    fun saveToken(token: String) {
        sharedPreferences.edit().putString(KEY_TOKEN, token).apply()
    }
    
    fun getToken(): String? {
        return sharedPreferences.getString(KEY_TOKEN, null)
    }
    
    fun clearToken() {
        sharedPreferences.edit().remove(KEY_TOKEN).apply()
    }
    
    fun saveDeviceId(deviceId: String) {
        sharedPreferences.edit().putString(KEY_DEVICE_ID, deviceId).apply()
    }
    
    fun getDeviceId(): String? {
        return sharedPreferences.getString(KEY_DEVICE_ID, null)
    }
    
    fun saveDeviceName(deviceName: String) {
        sharedPreferences.edit().putString(KEY_DEVICE_NAME, deviceName).apply()
    }
    
    fun getDeviceName(): String? {
        return sharedPreferences.getString(KEY_DEVICE_NAME, null)
    }
    
    fun savePairingCode(pairingCode: String) {
        sharedPreferences.edit().putString(KEY_PAIRING_CODE, pairingCode).apply()
    }
    
    fun getPairingCode(): String? {
        return sharedPreferences.getString(KEY_PAIRING_CODE, null)
    }
    
    fun clearPairingCode() {
        sharedPreferences.edit().remove(KEY_PAIRING_CODE).apply()
    }
    
    fun saveServerUrl(url: String) {
        sharedPreferences.edit().putString(KEY_SERVER_URL, url).apply()
    }
    
    fun getServerUrl(): String {
        return sharedPreferences.getString(KEY_SERVER_URL, "http://10.0.2.2:8765") ?: "http://10.0.2.2:8765"
    }
    
    fun setIsPaired(isPaired: Boolean) {
        sharedPreferences.edit().putBoolean(KEY_IS_PAIRED, isPaired).apply()
    }
    
    fun isPaired(): Boolean {
        return sharedPreferences.getBoolean(KEY_IS_PAIRED, false)
    }
    
    fun saveRegistration(response: DeviceRegisterResponse) {
        saveToken(response.token)
        saveDeviceId(response.deviceId)
        saveDeviceName(response.deviceName)
        savePairingCode(response.pairingCode)
        setIsPaired(false) // Not paired until user confirms code on laptop
    }
    
    fun clearAll() {
        sharedPreferences.edit().clear().apply()
    }
    
    fun isLoggedIn(): Boolean {
        return getToken() != null && isPaired()
    }
}
